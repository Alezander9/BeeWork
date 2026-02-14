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

# Container image: Debian + OpenCode + agent dir
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
    parser.add_argument("--repo", required=True, help="Knowledgebase GitHub repo as owner/repo")
    parser.add_argument("--question", required=True, help="Question to answer from the knowledgebase")
    args = parser.parse_args()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        raise EnvironmentError("Set GEMINI_API_KEY")
    github_pat = os.environ.get("GITHUB_PAT")
    if not github_pat:
        raise EnvironmentError("Set GITHUB_PAT")
    lmnr_key = os.environ.get("LMNR_PROJECT_API_KEY")
    if not lmnr_key:
        raise EnvironmentError("Set LMNR_PROJECT_API_KEY")

    Laminar.initialize(project_api_key=lmnr_key)

    app = modal.App.lookup("chat-gbt", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "GOOGLE_GENERATIVE_AI_API_KEY": gemini_key,
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

    prompt = f"Question: {args.question}. Follow the instructions in AGENTS.md."
    print(f"Running agent (model: {MODEL_ID})...")
    proc = sb.exec("bash", "-c",
        f"opencode run --format json {shlex.quote(prompt)}",
        pty=True)
    rc = observe_agent_events(proc, MODEL_ID)

    sb.terminate()
    print(f"exit code: {rc}")


if __name__ == "__main__":
    main()
