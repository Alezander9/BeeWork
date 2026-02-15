"""Shared OpenCode -> Laminar tracing.

Parses OpenCode's --format json JSONL stream and creates Laminar spans.
Tracing is best-effort -- failures never kill the agent run.
"""

import json

from lmnr import Laminar

from shared import telemetry


def parse_jsonl(proc):
    """Yield parsed JSON objects from a PTY-backed JSONL stream.

    PTY can split long JSON lines across multiple reads. We accumulate
    partial content until we get valid JSON, then yield it.
    """
    buf = ""
    for line in proc.stdout:
        line = line.replace("\r", "")
        for fragment in line.split("\n"):
            fragment = fragment.strip()
            if not fragment:
                continue
            buf += fragment
            try:
                obj = json.loads(buf)
                buf = ""
                yield obj
            except json.JSONDecodeError:
                continue
    if buf.strip():
        print(f"[unparsed] {buf[:200]}")


def _tool_summary(tool_name: str, tool_input) -> str:
    """Return a short detail string for a tool call, or empty string."""
    if not isinstance(tool_input, dict):
        return ""
    if tool_name in ("write", "edit"):
        path = tool_input.get("filePath") or tool_input.get("file_path") or tool_input.get("path", "")
        content = tool_input.get("content") or tool_input.get("value") or ""
        first_line = content.split("\n", 1)[0][:80] if content else ""
        if path:
            return f" {path}" + (f" -- {first_line}" if first_line else "")
    if tool_name == "read":
        path = tool_input.get("filePath") or tool_input.get("file_path") or tool_input.get("path", "")
        if path:
            return f" {path}"
    if tool_name == "bash":
        cmd = tool_input.get("command") or tool_input.get("cmd") or ""
        if cmd:
            return f" {cmd[:120]}"
    return ""


def observe_agent_events(proc, model_id, agent_name="agent_run", metadata=None, label="agent"):
    """Parse OpenCode JSONL stream and create Laminar spans for each event."""
    step_stack = []
    provider = model_id.split("/")[0] if "/" in model_id else "unknown"
    tag = f"{label}:" if label else ""

    try:
        span_input = {"model": model_id}
        if metadata:
            span_input["metadata"] = metadata
        with Laminar.start_as_current_span(
            name=agent_name, input=span_input, span_type="DEFAULT",
        ) as span:
            if metadata:
                span.set_attributes({f"beework.{k}": v for k, v in metadata.items()})
            for event in parse_jsonl(proc):
                etype = event.get("type")
                part = event.get("part", {})

                if etype == "step_start":
                    span = Laminar.start_span(name="llm_step", span_type="LLM")
                    span.set_attributes({
                        "gen_ai.request.model": model_id,
                        "gen_ai.system": provider,
                    })
                    step_stack.append(span)

                elif etype == "step_finish":
                    tokens = part.get("tokens", {})
                    cost = part.get("cost", 0)
                    if step_stack:
                        span = step_stack.pop()
                        span.set_attributes({
                            "gen_ai.usage.input_tokens": tokens.get("input", 0),
                            "gen_ai.usage.output_tokens": tokens.get("output", 0),
                            "gen_ai.usage.reasoning_tokens": tokens.get("reasoning", 0),
                            "gen_ai.usage.cache_read_tokens": tokens.get("cache", {}).get("read", 0),
                            "gen_ai.usage.cache_write_tokens": tokens.get("cache", {}).get("write", 0),
                            "gen_ai.usage.cost": cost,
                        })
                        span.end()
                    msg = f"[{tag}step] tokens={tokens} cost={cost}"
                    print(msg)
                    telemetry.log(msg)

                elif etype == "tool_use":
                    state = part.get("state", {})
                    tool_name = part.get("tool", "unknown")
                    tool_input = state.get("input", {})
                    with Laminar.start_as_current_span(
                        name=tool_name, input=tool_input, span_type="TOOL",
                    ):
                        Laminar.set_span_output(state.get("output", ""))
                    detail = _tool_summary(tool_name, tool_input)
                    msg = f"[{tag}tool] {tool_name}{detail}"
                    print(msg)
                    telemetry.log(msg)

                elif etype == "text":
                    text = part.get("text", "")
                    with Laminar.start_as_current_span(
                        name="text", input={"text": text}, span_type="TOOL",
                    ):
                        Laminar.set_span_output(text)
                    msg = f"[{tag}text] {text[:200]}"
                    print(msg)
                    telemetry.log(msg)

                elif etype == "error":
                    msg = f"[{tag}error] {event.get('error', {})}"
                    print(msg)
                    telemetry.log(msg)

            for span in step_stack:
                span.end()
    except Exception as e:
        print(f"[{tag}trace error] {e}")

    proc.wait()
    return proc.returncode
