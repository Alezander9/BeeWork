import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import base64
import json
import os
import shlex
from dotenv import load_dotenv
import modal
from lmnr import Laminar
from shared.tracing import observe_agent_events
from researcher.start_browser_agent import run_browser_agent

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MINUTES = 60
AGENT_DIR = Path(__file__).parent
KB_DIR = "/root/code/knowledgebase"
BROWSER_RESULT_PATH = "/root/code/browser_agent_output/result.json"

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


def run(topic, prompt, file_path, websites, repo, agent_id=None):
    """Run a researcher agent for a single research task."""
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

    # --- Step 1: Run browser agent locally ---
    print(f"Running browser agent for: {websites}")
    browser_result = run_browser_agent(task=prompt, website=websites)
    result_json = json.dumps(browser_result, indent=2)
    print(f"Browser agent finished (status: {browser_result.get('status', 'unknown')})")

    # --- Step 2: Create Modal sandbox ---
    app = modal.App.lookup("beework-worker", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "GOOGLE_GENERATIVE_AI_API_KEY": gemini_key,
        "GITHUB_PAT": github_pat,
        "GH_TOKEN": github_pat,
    })

    print(f"Creating sandbox...")
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=15 * MINUTES,
        )

    # Clone the knowledgebase repo
    clone_url = f"https://x-access-token:$GITHUB_PAT@github.com/{repo}.git"
    print(f"Cloning {repo} into {KB_DIR}...")
    rc = run_cmd(sb.exec("bash", "-c", f"git clone {clone_url} {KB_DIR}"), show=True)
    if rc != 0:
        sb.terminate()
        raise RuntimeError(f"Failed to clone repo {repo}")

    git_name = f"workerbee-{agent_id}" if agent_id else f"workerbee-{topic}"
    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name {shlex.quote(git_name)} && git config user.email 'beework.buzz@gmail.com'"))

    # --- Step 3: Write browser results into sandbox ---
    # Use base64 to safely transfer JSON that may contain special characters
    encoded = base64.b64encode(result_json.encode()).decode()
    run_cmd(sb.exec("bash", "-c",
        f"mkdir -p /root/code/browser_agent_output && "
        f"echo '{encoded}' | base64 -d > {BROWSER_RESULT_PATH}"))
    print(f"Browser results written to sandbox at {BROWSER_RESULT_PATH}")

    # --- Step 4: Run OpenCode agent ---
    agent_prompt = (
        f"Topic: {topic}\n"
        f"Your task: {prompt}\n"
        f"Target file: {file_path}\n"
        f"Browser research results are already available at browser_agent_output/result.json\n"
        f"Follow the instructions in AGENTS.md."
    )

    # Run agent with --format json for structured JSONL output
    # pty=True is required -- OpenCode hangs on Modal without a pseudo-terminal
    print(f"Running agent (model: {MODEL_ID})...")
    proc = sb.exec("bash", "-c",
        f"opencode run --format json {shlex.quote(agent_prompt)}",
        pty=True)
    trace_meta = {"research_agent_id": agent_id, "topic": topic} if agent_id else {}
    rc = observe_agent_events(proc, MODEL_ID, "researcher", metadata=trace_meta)

    # Capture the PR number created by the agent
    pr_proc = sb.exec("bash", "-c",
        f"cd {KB_DIR} && gh pr list --head $(git branch --show-current) --json number --jq '.[0].number'")
    pr_raw = "".join(pr_proc.stdout).strip()
    pr_proc.wait()
    pr_number = int(pr_raw) if pr_raw.isdigit() else None

    sb.terminate()
    print(f"exit code: {rc}, pr: {pr_number}")
    return pr_number


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="Topic of the research task")
    parser.add_argument("--prompt", required=True, help="Detailed instructions for the agent")
    parser.add_argument("--file-path", required=True, help="Path of the KB file to edit")
    parser.add_argument("--websites", required=True, help="Target website URL for research")
    parser.add_argument("--repo", required=True, help="Knowledgebase GitHub repo as owner/repo")
    args = parser.parse_args()
    run(args.topic, args.prompt, args.file_path, args.websites, args.repo)


if __name__ == "__main__":
    main()
