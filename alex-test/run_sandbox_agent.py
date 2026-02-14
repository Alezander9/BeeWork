import argparse
import os
import shlex
from pathlib import Path
from dotenv import load_dotenv
import modal

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MINUTES = 60
AGENT_DIR = Path(__file__).parent
KB_DIR = "/root/code/knowledgebase"

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


def run(proc, show=False):
    if show:
        for line in proc.stdout:
            print(line, end="")
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
    rc = run(sb.exec("bash", "-c", f"git clone {clone_url} {KB_DIR}"), show=True)
    if rc != 0:
        print("Failed to clone repo")
        sb.terminate()
        return

    # Configure git user in the knowledgebase repo so the agent can commit
    run(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name 'BeeWork Agent' && git config user.email 'agent@beework.dev'"))

    # Run the agent from /root/code (where opencode.json, AGENTS.MD, tools/ live)
    # pty=True is required -- OpenCode hangs without a pseudo-terminal
    print("Running agent...")
    proc = sb.exec("bash", "-c",
        f"opencode run {shlex.quote(args.prompt)}",
        pty=True)
    for line in proc.stdout:
        print(line, end="")

    proc.wait()
    sb.terminate()
    print(f"exit code: {proc.returncode}")


if __name__ == "__main__":
    main()
