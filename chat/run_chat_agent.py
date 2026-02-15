import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

AGENT_DIR = Path(__file__).parent


def setup_workspace(repo, use_kb=True):
    owner, name = repo.split("/")
    suffix = f"{owner}-{name}" if use_kb else f"{owner}-{name}-no-kb"
    workspace = Path.home() / ".beework" / suffix

    workspace.mkdir(parents=True, exist_ok=True)

    config = json.loads((AGENT_DIR / "opencode.json").read_text())
    if not use_kb:
        config["agent"]["build"]["tools"]["bash"] = False
    (workspace / "opencode.json").write_text(json.dumps(config, indent=2))

    if use_kb:
        shutil.copy(AGENT_DIR / "AGENTS.md", workspace / "AGENTS.md")
        kb_dir = workspace / "knowledgebase"
        if (kb_dir / ".git").exists():
            print(f"Updating {repo}...")
            subprocess.run(["git", "-C", str(kb_dir), "pull", "--ff-only"], check=False)
        else:
            print(f"Cloning {repo}...")
            pat = os.environ.get("GITHUB_PAT", "")
            url = f"https://x-access-token:{pat}@github.com/{repo}.git"
            subprocess.run(["git", "clone", url, str(kb_dir)], check=True)

    return workspace


def parse_events(proc):
    buf = ""
    response_parts = []
    first_event = True
    line_count = 0

    while True:
        line = proc.stdout.readline()
        if not line:
            stderr_output = proc.stderr.read()
            if stderr_output:
                print(f"\n[stderr]\n{stderr_output}", flush=True)
            break

        line_count += 1
        if line_count == 1:
            print(f"[got first line, length={len(line)}]", flush=True)

        line = line.replace("\r", "")
        for fragment in line.split("\n"):
            fragment = fragment.strip()
            if not fragment:
                continue
            buf += fragment
            try:
                event = json.loads(buf)
                buf = ""
            except json.JSONDecodeError:
                continue

            if first_event:
                print("[agent started]", flush=True)
                first_event = False

            etype = event.get("type")
            part = event.get("part", {})

            if etype == "text":
                text = part.get("text", "")
                response_parts.append(text)
                print(text, end="", flush=True)
            elif etype == "tool_use":
                state = part.get("state", {})
                tool = part.get("tool", "unknown")
                inp = state.get("input", {})
                out = state.get("output", "")
                print(f"\n[{tool}]", flush=True)
                if isinstance(inp, dict) and inp.get("command"):
                    print(f"$ {inp['command']}")
                elif isinstance(inp, str):
                    print(inp[:500])
                if out:
                    out_str = out if isinstance(out, str) else json.dumps(out)
                    if len(out_str) > 1000:
                        out_str = out_str[:1000] + "..."
                    print(out_str)
            elif etype == "step_start":
                print("[thinking...]", flush=True)
            elif etype == "step_finish":
                tokens = part.get("tokens", {})
                cost = part.get("cost", 0)
                print(f"[step done: in={tokens.get('input', 0)} out={tokens.get('output', 0)} ${cost:.4f}]", flush=True)
            elif etype == "error":
                print(f"[error] {event.get('error', {})}", flush=True)

    if buf.strip():
        print(f"[unparsed] {buf[:200]}")

    print(f"[total lines read: {line_count}]", flush=True)
    proc.wait()
    return "\n".join(response_parts)


def build_prompt(question, history, use_kb=True):
    parts = []
    if use_kb:
        parts.append("Follow the instructions in AGENTS.md.")
    if history:
        parts.append("\n## Previous conversation:")
        for turn in history:
            parts.append(f"User: {turn['question']}")
            answer = turn["answer"]
            if len(answer) > 500:
                answer = answer[:500] + "..."
            parts.append(f"Assistant: {answer}")
        parts.append("")
    parts.append(f"## Current question:\n{question}")
    return "\n".join(parts)


def run_turn(workspace, question, history, use_kb=True):
    prompt = build_prompt(question, history, use_kb)
    env = os.environ.copy()
    env["GOOGLE_GENERATIVE_AI_API_KEY"] = os.environ["GEMINI_API_KEY_4"]
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "true"
    env["OPENCODE_DISABLE_LSP_DOWNLOAD"] = "true"

    print("[starting opencode...]", flush=True)
    result = subprocess.run(
        ["opencode", "run", prompt],
        cwd=str(workspace),
        env=env,
        capture_output=False,
        text=True,
    )
    print(f"\n[opencode exited with code {result.returncode}]", flush=True)
    return ""


def main():
    parser = argparse.ArgumentParser(description="BeeWork KB chatbot")
    parser.add_argument("--repo", required=True, help="GitHub repo as owner/repo")
    parser.add_argument("--no-kb", action="store_true", help="Run without knowledgebase (model only)")
    args = parser.parse_args()
    use_kb = not args.no_kb

    if not os.environ.get("GEMINI_API_KEY_0"):
        print("Set GEMINI_API_KEY_0 in .env")
        sys.exit(1)

    workspace = setup_workspace(args.repo, use_kb)
    history = []

    mode = "with KB" if use_kb else "no KB (model only)"
    print(f"\nBeeWork chat -- {args.repo} [{mode}]")
    print("Type your question. 'q' to quit.\n")

    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            break
        if not question:
            continue
        if question.lower() in ("q", "quit", "exit"):
            print("bye")
            break

        print()
        answer = run_turn(workspace, question, history, use_kb)
        history.append({"question": question, "answer": answer})
        print()


if __name__ == "__main__":
    main()
