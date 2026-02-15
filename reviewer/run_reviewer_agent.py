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

# Container image: Debian + OpenCode + gh CLI + agent dir
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


def run(repo, pr, agent_id=None, key_index=0):
    """Run a reviewer agent for a single PR. Called by pipeline or CLI."""
    gemini_env = f"GEMINI_API_KEY_{key_index}"
    required = [gemini_env, "GITHUB_PAT", "LMNR_PROJECT_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    github_pat = os.environ["GITHUB_PAT"]
    Laminar.initialize(project_api_key=os.environ["LMNR_PROJECT_API_KEY"])

    app = modal.App.lookup("beework-reviewer", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "GOOGLE_GENERATIVE_AI_API_KEY": os.environ[gemini_env],
        "GITHUB_PAT": github_pat,
        "GH_TOKEN": github_pat,
    })

    print(f"Creating sandbox...")
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=20 * MINUTES,
        )

    clone_url = f"https://x-access-token:$GITHUB_PAT@github.com/{repo}.git"
    print(f"Cloning {repo} into {KB_DIR}...")
    rc = run_cmd(sb.exec("bash", "-c", f"git clone {clone_url} {KB_DIR}"), show=True)
    if rc != 0:
        sb.terminate()
        raise RuntimeError(f"Failed to clone repo {repo}")

    # Configure git identity so commits work without agent intervention
    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name 'BeeWork' && git config user.email 'beework.buzz@gmail.com'"))

    prompt = f"Review PR #{pr} on repo {repo}. Follow the instructions in AGENTS.md."
    print(f"Running agent (model: {MODEL_ID}), reviewing PR #{pr}...")
    proc = sb.exec("bash", "-c",
        f"opencode run --format json {shlex.quote(prompt)}",
        pty=True)
    trace_meta = {"research_agent_id": agent_id, "pr": pr} if agent_id else {}
    rc = observe_agent_events(proc, MODEL_ID, "reviewer", metadata=trace_meta)

    sb.terminate()
    print(f"exit code: {rc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--key-index", type=int, default=0, help="Which GEMINI_API_KEY_N to use")
    args = parser.parse_args()
    run(args.repo, args.pr, key_index=args.key_index)


if __name__ == "__main__":
    main()
