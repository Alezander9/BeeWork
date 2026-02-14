import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from dotenv import load_dotenv
import modal

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MINUTES = 60
AGENT_DIR = Path(__file__).parent
KB_DIR = "/root/code/knowledgebase"
WEB_SEARCHES_DIR = "/root/code/web_searches"
RESEARCH_TASKS_DIR = "/root/code/research_tasks"

# Container image: Debian + OpenCode + agent dir (AGENTS.MD, opencode.json, tools/)
image = (
    modal.Image.debian_slim()
    .apt_install("curl", "git", "tree")
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
    .pip_install("requests", "python-dotenv")
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


def run(repo_name, prompt="Follow the instructions in AGENTS.md"):
    """Run the orchestrator agent. Returns a list of research task dicts."""
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise EnvironmentError("Set ANTHROPIC_API_KEY")
    github_pat = os.environ.get("GITHUB_PAT")
    if not github_pat:
        raise EnvironmentError("Set GITHUB_PAT")
    parallel_api_key = os.environ.get("PARALLEL_API_KEY")
    if not parallel_api_key:
        raise EnvironmentError("Set PARALLEL_API_KEY")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise EnvironmentError("Set GEMINI_API_KEY")

    app = modal.App.lookup("test-opencode", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "ANTHROPIC_API_KEY": anthropic_api_key,
        "GOOGLE_GENERATIVE_AI_API_KEY": gemini_api_key,
        "GITHUB_PAT": github_pat,
        "GH_TOKEN": github_pat,
        "PARALLEL_API_KEY": parallel_api_key,
    })

    print(f"Creating sandbox...")
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=10 * MINUTES,
        )

    # Check if the repo already exists, create if not, then clone
    safe_repo_name = shlex.quote(repo_name)

    # gh repo view will succeed if the repo exists under the authenticated user
    check_rc = run_cmd(sb.exec("bash", "-c", f"gh repo view {safe_repo_name} --json name"), show=False)

    if check_rc == 0:
        # Repo exists — just clone it
        print(f"Repo '{repo_name}' already exists, cloning...")
        rc = run_cmd(sb.exec("bash", "-c",
            f"gh repo clone {safe_repo_name} {KB_DIR}"
        ), show=True)
    else:
        # Repo doesn't exist — create and clone
        print(f"Creating new GitHub repo '{repo_name}'...")
        create_cmd = (
            f"gh repo create {safe_repo_name} --public --clone "
            f"--description 'Created by BeeWork Agent'"
        )
        rc = run_cmd(sb.exec("bash", "-c",
            f"cd /root && {create_cmd} && mv {safe_repo_name} {KB_DIR}"
        ), show=True)

    if rc != 0:
        print("Failed to create/clone repo")
        sb.terminate()
        return []

    # Configure git user in the knowledgebase repo so the agent can commit
    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name 'BeeWork Orchestrator' && git config user.email 'agent@beework.dev'"))

    # Set remote origin URL with embedded PAT so the agent can push without auth issues
    remote_cmd = (
        f"cd {KB_DIR} && "
        f"GH_USER=$(gh api user --jq .login) && "
        f"git remote set-url origin https://$GITHUB_PAT@github.com/$GH_USER/{repo_name}.git"
    )
    run_cmd(sb.exec("bash", "-c", remote_cmd))

    # Create web searches directory (outside knowledgebase so results aren't pushed)
    run_cmd(sb.exec("bash", "-c", f"mkdir -p {WEB_SEARCHES_DIR}"))

    # Run the agent from /root/code (where opencode.json, AGENTS.MD, tools/ live)
    # pty=True is required -- OpenCode hangs without a pseudo-terminal
    print("Running agent...")
    proc = sb.exec("bash", "-c",
        f"opencode run {shlex.quote(prompt)}",
        pty=True)
    for line in proc.stdout:
        print(line, end="")

    proc.wait()
    agent_rc = proc.returncode

    # Collect research tasks created by create_research_task.py
    research_tasks = []
    try:
        # Use shell to list and read each JSON file — more reliable than sb.ls/sb.open
        list_proc = sb.exec("bash", "-c",
            f"find {RESEARCH_TASKS_DIR} -name '*.json' -type f 2>/dev/null")
        list_output = list_proc.stdout.read()
        list_proc.wait()
        file_paths = [p.strip() for p in list_output.splitlines() if p.strip()]
        for fpath in file_paths:
            cat_proc = sb.exec("bash", "-c", f"cat {shlex.quote(fpath)}")
            content = cat_proc.stdout.read()
            cat_proc.wait()
            try:
                task = json.loads(content)
                research_tasks.append(task)
            except json.JSONDecodeError as e:
                print(f"Warning: could not parse {fpath}: {e}")
    except Exception as e:
        print(f"Warning: failed to collect research tasks: {e}")

    if research_tasks:
        print(f"\nCollected {len(research_tasks)} research task(s):")
        for t in research_tasks:
            print(f"  - {t.get('topic', 'unknown')}: {t.get('file_path', '')}")

    # Save the agent's work back to the repo
    print("Committing and pushing changes...")
    push_rc = run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git add -A && "
        f"git diff --cached --quiet || "
        f"(git commit -m 'Agent run' && git push -u origin HEAD)"),
        show=True)
    if push_rc != 0:
        print("Warning: failed to push changes")

    sb.terminate()
    print(f"exit code: {agent_rc}")

    return research_tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_name", help="Name for the new GitHub repository")
    parser.add_argument("--prompt", default="Follow the instructions in AGENTS.md")
    args = parser.parse_args()
    run(args.repo_name, args.prompt)


if __name__ == "__main__":
    main()
