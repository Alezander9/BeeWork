"""
BeeWork full pipeline -- orchestrator -> parallel research -> parallel review.

Usage:
    uv run python shared/full_pipeline.py --repo <name> --project <path/to/requirements.md> [--max-research 5] [--max-review 1] [--start-from orchestrator|research|review]

State is persisted to pipeline_runs/{repo_name}.json for resumability.
Only "completed" tasks are skipped; pending, failed, and stale in_progress
are all retried on re-run.
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

OWNER = "workerbee-gbt"
PIPELINE_DIR = PROJECT_ROOT / "pipeline_runs"
STAGES = ["orchestrator", "research", "review"]
NUM_GEMINI_KEYS = 5

REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY_0",
    "GITHUB_PAT",
    "ANTHROPIC_API_KEY",
    "PARALLEL_API_KEY",
    "BROWSER_USE_API_KEY",
    "LMNR_PROJECT_API_KEY",
]

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _state_path(repo_name: str) -> Path:
    return PIPELINE_DIR / f"{repo_name}.json"


def load_state(repo_name: str) -> dict:
    path = _state_path(repo_name)
    if path.exists():
        return json.loads(path.read_text())
    return {"repo_name": repo_name, "full_repo": f"{OWNER}/{repo_name}", "stages": {}}


def save_state(state: dict) -> None:
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(state["repo_name"]).write_text(json.dumps(state, indent=2) + "\n")


@contextmanager
def track_stage(state: dict, name: str):
    """Track stage status: skip if completed, mark in_progress/completed/failed."""
    stage = state["stages"].setdefault(name, {"status": "pending"})
    if stage["status"] == "completed":
        print(f"[{name}] Already completed, skipping.")
        return
    stage["status"] = "in_progress"
    save_state(state)
    yield stage
    stage["status"] = "completed"
    save_state(state)


# ---------------------------------------------------------------------------
# Stage: orchestrator
# ---------------------------------------------------------------------------

def run_orchestrator(state: dict, project_path: str) -> None:
    with track_stage(state, "orchestrator") as stage:
        if stage is None:
            return
        from orchestrator.run_orchestrator_agent import run as orchestrate
        tasks = orchestrate(state["repo_name"], project_path)
        for task in tasks:
            task["research_agent_id"] = _topic_slug(task.get("topic", "unknown"))
        stage["result"] = {"research_tasks": tasks}
        print(f"[orchestrator] Done -- {len(tasks)} research task(s) created.")


# ---------------------------------------------------------------------------
# Stage: research (parallel)
# ---------------------------------------------------------------------------

def _topic_slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def _run_single_research(task: dict, full_repo: str, key_index: int = 0) -> int | None:
    from researcher.run_researcher_agent import run as research
    return research(
        topic=task["topic"],
        prompt=task["prompt"],
        file_path=task["file_path"],
        websites=task["websites"],
        repo=full_repo,
        agent_id=task.get("research_agent_id"),
        key_index=key_index,
    )


def run_research(state: dict, max_parallel: int) -> None:
    research_tasks = state["stages"].get("orchestrator", {}).get("result", {}).get("research_tasks", [])
    if not research_tasks:
        print("[research] No research tasks to run.")
        return

    stage = state["stages"].setdefault("research", {"status": "pending", "tasks": {}})
    stage["status"] = "in_progress"
    save_state(state)

    # Build work list -- skip completed tasks
    work = []
    for task in research_tasks:
        slug = _topic_slug(task.get("topic", "unknown"))
        if stage["tasks"].get(slug, {}).get("status") == "completed":
            print(f"[research] Skipping completed: {slug}")
            continue
        stage["tasks"].setdefault(slug, {"status": "pending"})
        work.append((slug, task))

    if not work:
        print("[research] All tasks already completed.")
        stage["status"] = "completed"
        save_state(state)
        return

    print(f"[research] Running {len(work)} task(s), max_parallel={max_parallel}")

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {}
        for i, (slug, task) in enumerate(work):
            stage["tasks"][slug]["status"] = "in_progress"
            save_state(state)
            key_index = i % NUM_GEMINI_KEYS
            futures[pool.submit(_run_single_research, task, state["full_repo"], key_index)] = slug

        for future in as_completed(futures):
            slug = futures[future]
            try:
                pr_number = future.result()
                stage["tasks"][slug] = {"status": "completed", "pr": pr_number, "research_agent_id": slug}
                print(f"[research] Completed: {slug} (PR #{pr_number})")
            except Exception as exc:
                stage["tasks"][slug] = {"status": "failed", "error": str(exc)}
                print(f"[research] Failed: {slug} -- {exc}")
            save_state(state)

    all_ok = all(t.get("status") == "completed" for t in stage["tasks"].values())
    stage["status"] = "completed" if all_ok else "failed"
    save_state(state)

    done = sum(1 for t in stage["tasks"].values() if t["status"] == "completed")
    print(f"[research] Finished: {done}/{len(stage['tasks'])} tasks completed.")


# ---------------------------------------------------------------------------
# Stage: review (parallel)
# ---------------------------------------------------------------------------

def _run_single_review(repo: str, pr: int, agent_id: str = None, key_index: int = 0) -> None:
    from reviewer.run_reviewer_agent import run as review
    review(repo=repo, pr=pr, agent_id=agent_id, key_index=key_index)


def run_review(state: dict, max_parallel: int) -> None:
    research_stage = state["stages"].get("research", {})
    research_tasks = research_stage.get("tasks", {})

    # Collect PRs and agent IDs from completed research tasks
    pr_tasks = {slug: {"pr": t["pr"], "agent_id": t.get("research_agent_id", slug)}
                for slug, t in research_tasks.items()
                if t.get("status") == "completed" and t.get("pr")}
    if not pr_tasks:
        print("[review] No PRs to review.")
        return

    stage = state["stages"].setdefault("review", {"status": "pending", "tasks": {}})
    stage["status"] = "in_progress"
    save_state(state)

    full_repo = state["full_repo"]

    # Build work list -- skip completed reviews
    work = []
    for slug, info in pr_tasks.items():
        if stage["tasks"].get(slug, {}).get("status") == "completed":
            print(f"[review] Skipping completed: {slug}")
            continue
        stage["tasks"].setdefault(slug, {"status": "pending", "pr": info["pr"], "research_agent_id": info["agent_id"]})
        work.append((slug, info["pr"], info["agent_id"]))

    if not work:
        print("[review] All reviews already completed.")
        stage["status"] = "completed"
        save_state(state)
        return

    print(f"[review] Running {len(work)} review(s), max_parallel={max_parallel}")

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {}
        for i, (slug, pr, agent_id) in enumerate(work):
            stage["tasks"][slug]["status"] = "in_progress"
            save_state(state)
            key_index = i % NUM_GEMINI_KEYS
            futures[pool.submit(_run_single_review, full_repo, pr, agent_id, key_index)] = slug

        for future in as_completed(futures):
            slug = futures[future]
            try:
                future.result()
                stage["tasks"][slug]["status"] = "completed"
                print(f"[review] Completed: {slug}")
            except Exception as exc:
                stage["tasks"][slug] = {"status": "failed", "error": str(exc)}
                print(f"[review] Failed: {slug} -- {exc}")
            save_state(state)

    all_ok = all(t.get("status") == "completed" for t in stage["tasks"].values())
    stage["status"] = "completed" if all_ok else "failed"
    save_state(state)

    done = sum(1 for t in stage["tasks"].values() if t["status"] == "completed")
    print(f"[review] Finished: {done}/{len(stage['tasks'])} reviews completed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pipeline(repo_name: str, project_path: str, max_research: int, max_review: int, start_from: str) -> None:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    state = load_state(repo_name)
    print(f"Pipeline: repo={state['full_repo']}, start_from={start_from}")

    t0 = time.time()
    if start_from == "orchestrator":
        run_orchestrator(state, project_path)
    if start_from in ("orchestrator", "research"):
        run_research(state, max_research)
    run_review(state, max_review)
    print(f"\nPipeline finished in {time.time() - t0:.0f}s.")


def main():
    parser = argparse.ArgumentParser(description="BeeWork full pipeline")
    parser.add_argument("--repo", required=True, help="GitHub repo name")
    parser.add_argument("--project", required=True, help="Path to project requirements .md file")
    parser.add_argument("--max-research", type=int, default=5, help="Max parallel researcher agents")
    parser.add_argument("--max-review", type=int, default=1, help="Max parallel reviewer agents")
    parser.add_argument("--start-from", choices=STAGES, default="orchestrator")
    args = parser.parse_args()
    run_pipeline(args.repo, args.project, args.max_research, args.max_review, args.start_from)


if __name__ == "__main__":
    main()
