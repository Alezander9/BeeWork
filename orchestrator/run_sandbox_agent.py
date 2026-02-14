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

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # pip install tomli for Python <3.11

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MINUTES = 60
AGENT_DIR = Path(__file__).parent
KB_DIR = "/root/code/knowledgebase"

# Read sandbox Python dependencies from pyproject.toml
with open(AGENT_DIR / "pyproject.toml", "rb") as f:
    _pyproject = tomllib.load(f)
SANDBOX_DEPS = _pyproject["project"]["dependencies"]

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
    .pip_install(*SANDBOX_DEPS)
    .env({
        "PATH": "/root/.opencode/bin:/usr/local/bin:/usr/bin:/bin",
        "OPENCODE_DISABLE_AUTOUPDATE": "true",
        "OPENCODE_DISABLE_LSP_DOWNLOAD": "true",
    })
    .add_local_dir(str(AGENT_DIR), "/root/code", copy=True)
    # Trigger one-time DB migration at build time so it never runs at runtime
    .run_commands("cd /root/code && opencode session list || true")
)


def run(proc, show=False):
    if show:
        for line in proc.stdout:
            print(line, end="")
    proc.wait()
    return proc.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_name", help="Name for the new GitHub repository")
    parser.add_argument("--prompt", default="Follow the instructions in AGENTS.md")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Set ANTHROPIC_API_KEY")
    github_pat = os.environ.get("GITHUB_PAT")
    if not github_pat:
        raise EnvironmentError("Set GITHUB_PAT")
    parallel_api_key = os.environ.get("PARALLEL_API_KEY")
    if not parallel_api_key:
        raise EnvironmentError("Set PARALLEL_API_KEY")
    lmnr_key = os.environ.get("LMNR_PROJECT_API_KEY")
    if not lmnr_key:
        raise EnvironmentError("Set LMNR_PROJECT_API_KEY")

    Laminar.initialize(project_api_key=lmnr_key)

    app = modal.App.lookup("test-opencode", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "ANTHROPIC_API_KEY": api_key,
        "GITHUB_PAT": github_pat,
        "GH_TOKEN": github_pat,
        "PARALLEL_API_KEY": parallel_api_key,
    })

    print(f"Creating sandbox...")
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=5 * MINUTES,
        )

    # Check if the repo already exists, create if not, then clone
    repo_name = shlex.quote(args.repo_name)

    # gh repo view will succeed if the repo exists under the authenticated user
    check_rc = run(sb.exec("bash", "-c", f"gh repo view {repo_name} --json name"), show=False)

    if check_rc == 0:
        # Repo exists — just clone it
        print(f"Repo '{args.repo_name}' already exists, cloning...")
        rc = run(sb.exec("bash", "-c",
            f"gh repo clone {repo_name} {KB_DIR}"
        ), show=True)
    else:
        # Repo doesn't exist — create and clone
        print(f"Creating new GitHub repo '{args.repo_name}'...")
        create_cmd = (
            f"gh repo create {repo_name} --public --clone "
            f"--description 'Created by BeeWork Agent'"
        )
        rc = run(sb.exec("bash", "-c",
            f"cd /root && {create_cmd} && mv {repo_name} {KB_DIR}"
        ), show=True)

    if rc != 0:
        print("Failed to create/clone repo")
        sb.terminate()
        return

    # Configure git user in the knowledgebase repo so the agent can commit
    run(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name 'BeeWork Orchestrator' && git config user.email 'agent@beework.dev'"))

    # Set remote origin URL with embedded PAT so the agent can push without auth issues
    remote_cmd = (
        f"cd {KB_DIR} && "
        f"GH_USER=$(gh api user --jq .login) && "
        f"git remote set-url origin https://$GITHUB_PAT@github.com/$GH_USER/{repo_name}.git"
    )
    run(sb.exec("bash", "-c", remote_cmd))

    # Run agent with --format json for structured JSONL output
    # pty=True is required -- OpenCode hangs on Modal without a pseudo-terminal
    print(f"Running agent (model: {MODEL_ID})...")
    proc = sb.exec("bash", "-c",
        f"opencode run --format json {shlex.quote(args.prompt)}",
        pty=True)
    agent_rc = observe_agent_events(proc, MODEL_ID)

    # Save the agent's work back to the repo
    print("Committing and pushing changes...")
    push_rc = run(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git add -A && "
        f"git diff --cached --quiet || "
        f"(git commit -m 'Agent run' && git push)"),
        show=True)
    if push_rc != 0:
        print("Warning: failed to push changes")

    sb.terminate()
    print(f"exit code: {agent_rc}")


if __name__ == "__main__":
    main()
