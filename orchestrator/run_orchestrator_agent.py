import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
import shlex
import time
from dotenv import load_dotenv
import modal
from lmnr import Laminar
from shared import telemetry
from shared.tracing import observe_agent_events

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MINUTES = 60
AGENT_DIR = Path(__file__).parent
KB_DIR = "/root/code/knowledgebase"
WEB_SEARCHES_DIR = "/root/code/web_searches"
RESEARCH_TASKS_DIR = "/root/code/research_tasks"

OPENCODE_CONFIG = json.loads((AGENT_DIR / "opencode.json").read_text())
MODEL_ID = OPENCODE_CONFIG.get("agent", {}).get("build", {}).get("model", "unknown")

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
    # Trigger one-time DB migration at build time so it never runs at runtime
    .run_commands("cd /root/code && opencode session list || true")
)


def run_cmd(proc, show=False):
    if show:
        for line in proc.stdout:
            print(line, end="")
    proc.wait()
    return proc.returncode


OWNER = "workerbee-gbt"


def _parse_token_value(s):
    """Convert suffixed token values like '159.4K' or '2.8M' to integers."""
    s = s.strip().replace(',', '')
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}
    if s and s[-1] in multipliers:
        return int(float(s[:-1]) * multipliers[s[-1]])
    return int(float(s))


def _extract_token_usage(sb):
    """Extract token usage by running 'opencode stats' and parsing the output."""
    import re
    proc = sb.exec("bash", "-c", "opencode stats 2>&1")
    output = ""
    for line in proc.stdout:
        output += line
    proc.wait()
    # Try JSON first (in case future versions support it)
    try:
        stats = json.loads(output.strip())
        total_tokens = stats.get("totalTokens", stats)
        inp = total_tokens.get("input", total_tokens.get("input_tokens", 0))
        out = total_tokens.get("output", total_tokens.get("output_tokens", 0))
        return {"input_tokens": inp, "output_tokens": out}
    except (json.JSONDecodeError, ValueError):
        pass

    # Parse box-drawing table output like: │Input                  159.4K │
    inp = 0
    out = 0
    input_match = re.search(r'│\s*Input\s+([\d.,]+[KMB]?)\s*│', output)
    output_match = re.search(r'│\s*Output\s+([\d.,]+[KMB]?)\s*│', output)
    if input_match:
        inp = _parse_token_value(input_match.group(1))
    if output_match:
        out = _parse_token_value(output_match.group(1))

    if inp == 0 and out == 0:
        msg = "[orchestrator] Warning: could not extract token counts from opencode stats"
        print(msg); telemetry.log(msg)
        return {"input_tokens": None, "output_tokens": None}

    return {"input_tokens": inp, "output_tokens": out}


def run(repo_name, project_path, key_index=0):
    """Run the orchestrator agent. Returns dict with research_tasks and total_tokens."""
    tag = "orchestrator"
    project_content = Path(project_path).read_text()

    gemini_env = f"GEMINI_API_KEY_{key_index}"
    required = ["ANTHROPIC_API_KEY", "GITHUB_PAT", "PARALLEL_API_KEY", gemini_env, "LMNR_PROJECT_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    github_pat = os.environ["GITHUB_PAT"]
    Laminar.initialize(project_api_key=os.environ["LMNR_PROJECT_API_KEY"])

    app = modal.App.lookup("beework-orchestrator", create_if_missing=True)
    secret = modal.Secret.from_dict({
        "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
        "GOOGLE_GENERATIVE_AI_API_KEY": os.environ[gemini_env],
        "GITHUB_PAT": github_pat,
        "GH_TOKEN": github_pat,
        "PARALLEL_API_KEY": os.environ["PARALLEL_API_KEY"],
    })

    msg = f"[{tag}] Creating sandbox..."
    print(msg); telemetry.log(msg)
    t0 = time.time()
    with modal.enable_output():
        sb = modal.Sandbox.create(
            "sleep", "infinity",
            image=image, secrets=[secret], app=app,
            workdir="/root/code", timeout=30 * MINUTES,
        )
    msg = f"[{tag}] Sandbox ready ({time.time() - t0:.1f}s)"
    print(msg); telemetry.log(msg)
    telemetry.event("sandbox_created")

    # Check if the repo already exists, create if not, then clone
    safe_repo_name = shlex.quote(repo_name)

    # gh repo view will succeed if the repo exists under the authenticated user
    check_rc = run_cmd(sb.exec("bash", "-c", f"gh repo view {safe_repo_name} --json name"), show=False)

    if check_rc == 0:
        msg = f"[{tag}] Repo '{repo_name}' already exists, cloning..."
        print(msg); telemetry.log(msg)
        rc = run_cmd(sb.exec("bash", "-c",
            f"gh repo clone {safe_repo_name} {KB_DIR}"
        ), show=True)
    else:
        msg = f"[{tag}] Creating new GitHub repo '{repo_name}'..."
        print(msg); telemetry.log(msg)
        create_cmd = (
            f"gh repo create {safe_repo_name} --public --clone "
            f"--description 'Created by BeeWork Agent'"
        )
        rc = run_cmd(sb.exec("bash", "-c",
            f"cd /root && {create_cmd} && mv {safe_repo_name} {KB_DIR}"
        ), show=True)

    if rc != 0:
        msg = f"[{tag}] Failed to create/clone repo"
        print(msg); telemetry.log(msg)
        sb.terminate()
        return {"research_tasks": [], "input_tokens": None, "output_tokens": None}

    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git config user.name 'BeeWork' && git config user.email 'beework.buzz@gmail.com'"))

    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git remote set-url origin "
        f"https://$GITHUB_PAT@github.com/{OWNER}/{repo_name}.git"))
    telemetry.event("repo_created", {"repo": repo_name})

    # Write PROJECT.MD into the repo and commit as the initial content
    with sb.open(f"{KB_DIR}/PROJECT.MD", "w") as f:
        f.write(project_content)
    run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git add PROJECT.MD && "
        f"git commit -m 'Add project requirements' && git push -u origin HEAD"),
        show=True)
    telemetry.event("project_read")

    # Also place PROJECT.MD at the agent workdir so AGENTS.MD can reference it
    with sb.open("/root/code/PROJECT.MD", "w") as f:
        f.write(project_content)

    run_cmd(sb.exec("bash", "-c", f"mkdir -p {WEB_SEARCHES_DIR}"))

    # Run the agent from /root/code (where opencode.json, AGENTS.MD, tools/ live)
    # pty=True is required -- OpenCode hangs without a pseudo-terminal
    msg = f"[{tag}] Running agent (model: {MODEL_ID})..."
    print(msg); telemetry.log(msg)
    proc = sb.exec("bash", "-c",
        "opencode run --format json 'Follow the instructions in AGENTS.md'",
        pty=True)
    agent_rc = observe_agent_events(proc, MODEL_ID, "orchestrator", label=tag)
    telemetry.event("structure_built")

    # Extract token usage from OpenCode session DB
    token_info = _extract_token_usage(sb)
    input_tokens = token_info.get("input_tokens")
    output_tokens = token_info.get("output_tokens")
    msg = f"[{tag}] Token usage -- input: {input_tokens}, output: {output_tokens}"
    print(msg); telemetry.log(msg)

    # Collect research tasks created by create_research_task.py
    TASKS_FILE = "/tmp/all_tasks.json"
    run_cmd(sb.exec("bash", "-c",
        f"python3 -c \""
        f"import json, glob; "
        f"tasks = [json.load(open(f)) for f in sorted(glob.glob('{RESEARCH_TASKS_DIR}/*.json'))]; "
        f"open('{TASKS_FILE}','w').write(json.dumps(tasks))"
        f"\""))
    with sb.open(TASKS_FILE, "r") as f:
        research_tasks = json.loads(f.read())
    msg = f"[{tag}] Collected {len(research_tasks)} research task(s)"
    print(msg); telemetry.log(msg)
    telemetry.event("research_tasks_created", {"count": len(research_tasks)})

    # Save the agent's work back to the repo
    msg = f"[{tag}] Committing and pushing changes..."
    print(msg); telemetry.log(msg)
    push_rc = run_cmd(sb.exec("bash", "-c",
        f"cd {KB_DIR} && git add -A && "
        f"git diff --cached --quiet || "
        f"(git commit -m 'Agent run' && git push -u origin HEAD)"),
        show=True)
    if push_rc != 0:
        msg = f"[{tag}] Warning: failed to push changes"
        print(msg); telemetry.log(msg)
    telemetry.event("changes_pushed", {"success": push_rc == 0})

    sb.terminate()
    msg = f"[{tag}] exit code: {agent_rc}"
    print(msg); telemetry.log(msg)

    return {"research_tasks": research_tasks, "input_tokens": input_tokens, "output_tokens": output_tokens}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_name", help="Name for the new GitHub repository")
    parser.add_argument("project_path", help="Path to the project requirements .md file")
    args = parser.parse_args()
    run(args.repo_name, args.project_path)


if __name__ == "__main__":
    main()
