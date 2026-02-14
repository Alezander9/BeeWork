"""
BeeWork full pipeline — runs orchestrator then parallel researcher agents.

Usage:
    uv run python shared/full_pipeline.py <repo_name> [--prompt "..."] [--max-parallel 3] [--start-from orchestrator|research]

State is persisted to pipeline_runs/{repo_name}.json for resumability.
Only "completed" tasks are skipped; pending, failed, and stale in_progress
are all retried on re-run.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is on sys.path so sibling packages resolve
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

PIPELINE_DIR = PROJECT_ROOT / "pipeline_runs"
STAGE_ORDER = ["orchestrator", "research"]

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _state_path(repo_name: str) -> Path:
    return PIPELINE_DIR / f"{repo_name}.json"


def load_state(repo_name: str) -> dict:
    path = _state_path(repo_name)
    if path.exists():
        return json.loads(path.read_text())
    return {
        "repo_name": repo_name,
        "owner": None,
        "full_repo": None,
        "stages": {},
    }


def save_state(state: dict) -> None:
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    path = _state_path(state["repo_name"])
    path.write_text(json.dumps(state, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY",
    "GITHUB_PAT",
    "ANTHROPIC_API_KEY",
    "PARALLEL_API_KEY",
    "BROWSER_USE_API_KEY",
    "LMNR_PROJECT_API_KEY",
]


def validate_env() -> None:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


# ---------------------------------------------------------------------------
# GitHub owner resolution
# ---------------------------------------------------------------------------

def resolve_owner(state: dict) -> str:
    if state.get("owner"):
        return state["owner"]
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to resolve GitHub user: {result.stderr.strip()}")
    owner = result.stdout.strip()
    state["owner"] = owner
    state["full_repo"] = f"{owner}/{state['repo_name']}"
    save_state(state)
    return owner


# ---------------------------------------------------------------------------
# Stage: orchestrator
# ---------------------------------------------------------------------------

def run_orchestrator_stage(state: dict, prompt: str) -> None:
    stage = state["stages"].setdefault("orchestrator", {"status": "pending"})
    if stage["status"] == "completed":
        print("[orchestrator] Already completed, skipping.")
        return

    stage["status"] = "in_progress"
    save_state(state)

    print("[orchestrator] Running...")
    from orchestrator.run_orchestrator_agent import run as run_orchestrator

    research_tasks = run_orchestrator(state["repo_name"], prompt)

    stage["status"] = "completed"
    stage["result"] = {"research_tasks": research_tasks}
    save_state(state)
    print(f"[orchestrator] Completed — {len(research_tasks)} research task(s) created.")


# ---------------------------------------------------------------------------
# Stage: research (parallel)
# ---------------------------------------------------------------------------

def _topic_slug(topic: str) -> str:
    """Convert a topic string into a filesystem-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def _run_single_research(task: dict, full_repo: str) -> None:
    """Run a single researcher agent. Raises on failure."""
    from researcher.run_research_agent import run as run_researcher

    run_researcher(
        topic=task["topic"],
        prompt=task["prompt"],
        file_path=task["file_path"],
        websites=task["websites"],
        repo=full_repo,
    )


def run_research_stage(state: dict, max_parallel: int) -> None:
    orch_stage = state["stages"].get("orchestrator", {})
    if orch_stage.get("status") != "completed":
        raise RuntimeError("Cannot run research stage: orchestrator has not completed.")

    research_tasks = orch_stage.get("result", {}).get("research_tasks", [])
    if not research_tasks:
        print("[research] No research tasks to run.")
        state["stages"]["research"] = {"status": "completed", "tasks": {}}
        save_state(state)
        return

    stage = state["stages"].setdefault("research", {"status": "pending", "tasks": {}})
    stage["status"] = "in_progress"
    save_state(state)

    full_repo = state["full_repo"]

    # Build work list — skip completed tasks
    work = []
    for task in research_tasks:
        slug = _topic_slug(task.get("topic", "unknown"))
        task_state = stage["tasks"].get(slug, {})
        if task_state.get("status") == "completed":
            print(f"[research] Skipping completed task: {slug}")
            continue
        stage["tasks"].setdefault(slug, {"status": "pending"})
        work.append((slug, task))

    if not work:
        print("[research] All tasks already completed.")
        stage["status"] = "completed"
        save_state(state)
        return

    print(f"[research] Running {len(work)} task(s) with max_parallel={max_parallel}...")

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        future_to_slug = {}
        for slug, task in work:
            stage["tasks"][slug]["status"] = "in_progress"
            save_state(state)
            future = pool.submit(_run_single_research, task, full_repo)
            future_to_slug[future] = slug

        for future in as_completed(future_to_slug):
            slug = future_to_slug[future]
            try:
                future.result()
                stage["tasks"][slug] = {"status": "completed"}
                print(f"[research] Task '{slug}' completed.")
            except Exception as exc:
                stage["tasks"][slug] = {
                    "status": "failed",
                    "error": str(exc),
                }
                print(f"[research] Task '{slug}' failed: {exc}")
            save_state(state)

    # Mark stage completed only if every task succeeded
    all_done = all(
        t.get("status") == "completed" for t in stage["tasks"].values()
    )
    stage["status"] = "completed" if all_done else "failed"
    save_state(state)

    completed = sum(1 for t in stage["tasks"].values() if t["status"] == "completed")
    total = len(stage["tasks"])
    print(f"[research] Finished: {completed}/{total} tasks completed.")


# ---------------------------------------------------------------------------
# Stage registry
# ---------------------------------------------------------------------------

STAGE_RUNNERS = {
    "orchestrator": lambda state, **kw: run_orchestrator_stage(state, kw["prompt"]),
    "research": lambda state, **kw: run_research_stage(state, kw["max_parallel"]),
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pipeline(repo_name: str, prompt: str, max_parallel: int, start_from: str) -> None:
    validate_env()

    state = load_state(repo_name)
    resolve_owner(state)

    start_idx = STAGE_ORDER.index(start_from)
    stages_to_run = STAGE_ORDER[start_idx:]

    print(f"Pipeline: repo={state['full_repo']}, stages={stages_to_run}")
    print(f"State file: {_state_path(repo_name)}")

    t0 = time.time()
    for stage_name in stages_to_run:
        runner = STAGE_RUNNERS[stage_name]
        runner(state, prompt=prompt, max_parallel=max_parallel)

    elapsed = time.time() - t0
    print(f"\nPipeline finished in {elapsed:.0f}s.")


def main():
    parser = argparse.ArgumentParser(
        description="BeeWork full pipeline — orchestrator + parallel research"
    )
    parser.add_argument("repo_name", help="Name for the knowledge base GitHub repo")
    parser.add_argument(
        "--prompt",
        default="Follow the instructions in AGENTS.md",
        help="Prompt for the orchestrator agent",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=3,
        help="Max number of researcher agents to run in parallel (default: 3)",
    )
    parser.add_argument(
        "--start-from",
        choices=STAGE_ORDER,
        default="orchestrator",
        help="Resume pipeline from this stage (default: orchestrator)",
    )
    args = parser.parse_args()
    run_pipeline(args.repo_name, args.prompt, args.max_parallel, args.start_from)


if __name__ == "__main__":
    main()
