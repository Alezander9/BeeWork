import argparse
import json
import os
import shlex
from pathlib import Path
from dotenv import load_dotenv
import modal
from lmnr import Laminar

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MINUTES = 60
AGENT_DIR = Path(__file__).parent
KB_DIR = "/root/code/knowledgebase"

# Read model from opencode.json so we can tag LLM spans
OPENCODE_CONFIG = json.loads((AGENT_DIR / "opencode.json").read_text())
MODEL_ID = OPENCODE_CONFIG.get("agent", {}).get("build", {}).get("model", "unknown")

# Container image: Debian + OpenCode + agent dir (AGENTS.MD, opencode.json, tools/)
image = (
    modal.Image.debian_slim()
    .apt_install("curl", "git")
    .run_commands("curl -fsSL https://opencode.ai/install | bash")
    .env({
        "PATH": "/root/.opencode/bin:/usr/local/bin:/usr/bin:/bin",
        "OPENCODE_DISABLE_AUTOUPDATE": "true",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "true",
    })
    .add_local_dir(str(AGENT_DIR), "/root/code", copy=True)
)


def run_cmd(proc, show=False):
    if show:
        for line in proc.stdout:
            print(line, end="")
    proc.wait()
    return proc.returncode


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
                # Incomplete JSON -- keep accumulating
                continue
    if buf.strip():
        print(f"[unparsed] {buf[:200]}")


def observe_agent_events(proc):
    """Parse OpenCode JSONL stream and create Laminar spans for each event."""
    step_stack = []  # stack of LLM step spans (for matching start/finish)

    with Laminar.start_as_current_span(
        name="agent_run",
        input={"model": MODEL_ID},
        span_type="DEFAULT",
    ):
        for event in parse_jsonl(proc):
            etype = event.get("type")
            part = event.get("part", {})

            if etype == "step_start":
                span = Laminar.start_span(name="llm_step", span_type="LLM")
                span.set_attributes({
                    "gen_ai.request.model": MODEL_ID,
                    "gen_ai.system": MODEL_ID.split("/")[0] if "/" in MODEL_ID else "unknown",
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

    proc.wait()
    return proc.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="Knowledgebase GitHub repo as owner/repo")
    parser.add_argument("--prompt", default="Follow the instructions in AGENTS.md")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Set ANTHROPIC_API_KEY")
    github_pat = os.environ.get("GITHUB_PAT")
    if not github_pat:
        raise EnvironmentError("Set GITHUB_PAT")
    lmnr_key = os.environ.get("LMNR_PROJECT_API_KEY")
    if not lmnr_key:
        raise EnvironmentError("Set LMNR_PROJECT_API_KEY")

    Laminar.initialize(project_api_key=lmnr_key)

    app = modal.App.lookup("test-opencode", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "ANTHROPIC_API_KEY": api_key,
        "GITHUB_PAT": github_pat,
    })

    print(f"Creating sandbox...")
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=5 * MINUTES,
        )

    # Clone the knowledgebase repo
    clone_url = f"https://x-access-token:$GITHUB_PAT@github.com/{args.repo}.git"
    print(f"Cloning {args.repo} into {KB_DIR}...")
    rc = run_cmd(sb.exec("bash", "-c", f"git clone {clone_url} {KB_DIR}"), show=True)
    if rc != 0:
        print("Failed to clone repo")
        sb.terminate()
        return

    # Configure git user in the knowledgebase repo so the agent can commit
    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name 'BeeWork Agent' && git config user.email 'agent@beework.dev'"))

    # Run agent with --format json for structured JSONL output
    # pty=True is required -- OpenCode hangs on Modal without a pseudo-terminal
    print(f"Running agent (model: {MODEL_ID})...")
    proc = sb.exec("bash", "-c",
        f"opencode run --format json {shlex.quote(args.prompt)}",
        pty=True)
    rc = observe_agent_events(proc)

    sb.terminate()
    print(f"exit code: {rc}")


if __name__ == "__main__":
    main()
