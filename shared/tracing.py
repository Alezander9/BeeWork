"""Shared OpenCode -> Laminar tracing.

Parses OpenCode's --format json JSONL stream and creates Laminar spans.
Tracing is best-effort -- failures never kill the agent run.
"""

import json

from lmnr import Laminar


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


def observe_agent_events(proc, model_id, agent_name="agent_run"):
    """Parse OpenCode JSONL stream and create Laminar spans for each event."""
    step_stack = []
    provider = model_id.split("/")[0] if "/" in model_id else "unknown"

    try:
        with Laminar.start_as_current_span(
            name=agent_name, input={"model": model_id}, span_type="DEFAULT",
        ):
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
                    print(f"[step] tokens={tokens} cost={cost}")

                elif etype == "tool_use":
                    state = part.get("state", {})
                    tool_name = part.get("tool", "unknown")
                    with Laminar.start_as_current_span(
                        name=tool_name, input=state.get("input", {}), span_type="TOOL",
                    ):
                        Laminar.set_span_output(state.get("output", ""))
                    print(f"[tool] {tool_name}")

                elif etype == "text":
                    text = part.get("text", "")
                    with Laminar.start_as_current_span(
                        name="text", input={"text": text}, span_type="TOOL",
                    ):
                        Laminar.set_span_output(text)
                    print(f"[text] {text[:200]}")

                elif etype == "error":
                    print(f"[error] {event.get('error', {})}")

            for span in step_stack:
                span.end()
    except Exception as e:
        print(f"[trace error] {e}")

    proc.wait()
    return proc.returncode
