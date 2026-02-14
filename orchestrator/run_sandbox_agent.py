import os
from pathlib import Path
from dotenv import load_dotenv
import modal

# Load .env from repo root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MINUTES = 60

# All file paths relative to this script's directory
AGENT_DIR = Path(__file__).parent

# Container image: Debian + OpenCode + project files
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


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("Set ANTHROPIC_API_KEY environment variable")

    app = modal.App.lookup("orchestrator-opencode", create_if_missing=True)

    # LLM key injected at runtime, not baked into image
    secret = modal.Secret.from_dict({"ANTHROPIC_API_KEY": api_key})

    # Start sandbox with idle process, then exec into it
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=5 * MINUTES,
        )

    # pty=True is required -- OpenCode hangs without a pseudo-terminal
    proc = sb.exec("bash", "-c",
        "opencode run 'Follow the instructions in AGENTS.md'",
        pty=True)

    for line in proc.stdout:
        print(line, end="")

    proc.wait()
    sb.terminate()
    print(f"exit code: {proc.returncode}")


if __name__ == "__main__":
    main()
