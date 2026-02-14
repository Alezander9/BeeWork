import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
import shlex
from dotenv import load_dotenv
import modal
from lmnr import Laminar
from shared.tracing import observe_agent_events

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
    .run_commands(
        "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg "
        "| dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg",
        'echo "deb [arch=$(dpkg --print-architecture) '
        'signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] '
        'https://cli.github.com/packages stable main" '
        '| tee /etc/apt/sources.list.d/github-cli.list > /dev/null',
        "apt-get update && apt-get install -y gh",
    )
    .run_commands("curl -fsSL https://opencode.ai/install | bash")
    .pip_install("requests")
    .env({
        "PATH": "/root/.opencode/bin:/usr/local/bin:/usr/bin:/bin",
        "OPENCODE_DISABLE_AUTOUPDATE": "true",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "true",
    })
    .add_local_dir(str(AGENT_DIR), "/root/code", copy=True)
    # Trigger one-time DB migration at build time so it never runs at runtime
    .run_commands("cd /root/code && opencode session list || true")
)


def run_cmd(proc, show=False):
    if show:
        for line in proc.stdout:
            print(line, end="")
    proc.wait()
    return proc.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Topic of the research task")
    parser.add_argument("--prompt", required=True, help="Detailed instructions for the agent")
    parser.add_argument("--file-path", required=True, help="Path of the KB file to edit")
    parser.add_argument("--websites", required=True, help="Target website URL for research")
    parser.add_argument("--repo", required=True, help="Knowledgebase GitHub repo as owner/repo")
    args = parser.parse_args()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise EnvironmentError("Set GEMINI_API_KEY")
    github_pat = os.environ.get("GITHUB_PAT")
    if not github_pat:
        raise EnvironmentError("Set GITHUB_PAT")
    browser_use_key = os.environ.get("BROWSER_USE_API_KEY")
    if not browser_use_key:
        raise EnvironmentError("Set BROWSER_USE_API_KEY")
    lmnr_key = os.environ.get("LMNR_PROJECT_API_KEY")
    if not lmnr_key:
        raise EnvironmentError("Set LMNR_PROJECT_API_KEY")

    Laminar.initialize(project_api_key=lmnr_key)

    app = modal.App.lookup("beework-worker", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "GOOGLE_GENERATIVE_AI_API_KEY": gemini_key,
        "GITHUB_PAT": github_pat,
        "GH_TOKEN": github_pat,
        "BROWSER_USE_API_KEY": browser_use_key,
    })

    print(f"Creating sandbox...")
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=15 * MINUTES,
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
        f"cd {KB_DIR} && git config user.name 'workerbee-gbt' && git config user.email 'beework.buzz@gmail.com'"))

    # Build the prompt from task fields
    prompt = (
        f"Topic: {args.topic}\n"
        f"Your task: {args.prompt}\n"
        f"Target file: {args.file_path}\n"
        f"Target website: {args.websites}\n"
        f"Follow the instructions in AGENTS.md."
    )

    # Run agent with --format json for structured JSONL output
    # pty=True is required -- OpenCode hangs on Modal without a pseudo-terminal
    print(f"Running agent (model: {MODEL_ID})...")
    proc = sb.exec("bash", "-c",
        f"opencode run --format json {shlex.quote(prompt)}",
        pty=True)
    rc = observe_agent_events(proc, MODEL_ID)

    sb.terminate()
    print(f"exit code: {rc}")


if __name__ == "__main__":
    main()
