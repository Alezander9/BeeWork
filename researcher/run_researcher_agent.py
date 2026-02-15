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
BROWSER_RESULT_DIR = "/root/code/browser_agent_output"
BROWSER_RESULT_PATH = f"{BROWSER_RESULT_DIR}/result.json"
BROWSER_OUTPUT_PATH = f"{BROWSER_RESULT_DIR}/research.md"

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


def run(topic, prompt, file_path, websites, repo, agent_id=None, key_index=0):
    """Run a researcher agent for a single research task."""
    gemini_key = os.environ.get(f"GEMINI_API_KEY_{key_index}")
    if not gemini_key:
        raise EnvironmentError(f"Set GEMINI_API_KEY_{key_index}")
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
            workdir="/root/code", timeout=20 * MINUTES,
        )

    # Clone the knowledgebase repo
    clone_url = f"https://x-access-token:$GITHUB_PAT@github.com/{repo}.git"
    print(f"Cloning {repo} into {KB_DIR}...")
    rc = run_cmd(sb.exec("bash", "-c", f"git clone {clone_url} {KB_DIR}"), show=True)
    if rc != 0:
        sb.terminate()
        raise RuntimeError(f"Failed to clone repo {repo}")

    # Configure git identity so commits work without agent intervention
    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name 'BeeWork' && git config user.email 'beework.buzz@gmail.com'"))

    # --- Step 3: Write browser results into sandbox ---
    # Write full JSON for reference, plus a clean markdown file with just the output
    run_cmd(sb.exec("bash", "-c", f"mkdir -p {BROWSER_RESULT_DIR}"))
    encoded = base64.b64encode(result_json.encode()).decode()
    run_cmd(sb.exec("bash", "-c",
        f"echo '{encoded}' | base64 -d > {BROWSER_RESULT_PATH}"))
    output_text = browser_result.get("output", "")
    encoded_output = base64.b64encode(output_text.encode()).decode()
    run_cmd(sb.exec("bash", "-c",
        f"echo '{encoded_output}' | base64 -d > {BROWSER_OUTPUT_PATH}"))
    print(f"Browser results written to sandbox")

    # --- Step 4: Run OpenCode agent ---
    agent_prompt = (
        f"Topic: {topic}\n"
        f"Your task: {prompt}\n"
        f"Target file: {file_path}\n"
        f"Browser research output is at browser_agent_output/research.md\n"
        f"Full browser results (with steps/URLs) are at browser_agent_output/result.json if needed.\n"
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

    # --- Step 5: Create branch, commit, push, and open PR ---
    branch = f"research/{agent_id or 'unknown'}"
    pr_title = f"Research: {topic}"
    pr_body = f"Research on {topic} with citations"
    git_cmd = (
        f"cd {KB_DIR} && "
        f"git checkout -b {shlex.quote(branch)} && "
        f"git add -A && "
        f"git diff --cached --quiet || "
        f"(git commit -m {shlex.quote(topic)} && "
        f"git push -u origin HEAD && "
        f"gh pr create --title {shlex.quote(pr_title)} "
        f"--body {shlex.quote(pr_body)})"
    )
    run_cmd(sb.exec("bash", "-c", git_cmd), show=True)

    pr_proc = sb.exec("bash", "-c",
        f"cd {KB_DIR} && gh pr list --head {shlex.quote(branch)} --json number --jq '.[0].number'")
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
    parser.add_argument("--key-index", type=int, default=0, help="Which GEMINI_API_KEY_N to use")
    args = parser.parse_args()
    run(args.topic, args.prompt, args.file_path, args.websites, args.repo, key_index=args.key_index)


if __name__ == "__main__":
    main()
