"""
BeeWork full pipeline -- orchestrator -> parallel (research + review) per task.

Usage:
    uv run python shared/full_pipeline.py --repo <name> --project <path/to/requirements.md> [--max-parallel 5] [--start-from orchestrator|tasks]

State is persisted to pipeline_runs/{repo_name}.json for resumability.
Per-task statuses: pending -> researched -> completed.
Tasks with a PR but no review are resumed from review only.
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
STAGES = ["orchestrator", "tasks"]
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
        yield None
        return
    stage["status"] = "in_progress"
    save_state(state)
    yield stage
    stage["status"] = "completed"
    save_state(state)


# ---------------------------------------------------------------------------
# Stage: orchestrator
# ---------------------------------------------------------------------------

def _topic_slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def run_orchestrator(state: dict, project_path: str) -> None:
    with track_stage(state, "orchestrator") as stage:
        if stage is None:
            return
        from orchestrator.run_orchestrator_agent import run as orchestrate
        result = orchestrate(state["repo_name"], project_path)
        tasks = result["research_tasks"]
        input_tokens = result.get("input_tokens")
        output_tokens = result.get("output_tokens")
        for task in tasks:
            task["research_agent_id"] = _topic_slug(task.get("topic", "unknown"))
        stage["result"] = {"research_tasks": tasks, "input_tokens": input_tokens, "output_tokens": output_tokens}
        print(f"[orchestrator] Done -- {len(tasks)} task(s), input tokens: {input_tokens}, output tokens: {output_tokens}")


# ---------------------------------------------------------------------------
# Stage: tasks (research + review per task, in parallel)
# ---------------------------------------------------------------------------

def _run_single_task(task: dict, full_repo: str, key_index: int, existing_pr: int | None = None) -> int:
    """Run research (if needed) then review for a single task. Returns PR number."""
    pr = existing_pr
    if pr is None:
        from researcher.run_researcher_agent import run as research
        pr = research(
            topic=task["topic"],
            prompt=task["prompt"],
            file_path=task["file_path"],
            websites=task["websites"],
            repo=full_repo,
            agent_id=task.get("research_agent_id"),
            key_index=key_index,
        )
    from reviewer.run_reviewer_agent import run as review
    review(repo=full_repo, pr=pr, agent_id=task.get("research_agent_id"), key_index=key_index)
    return pr


def run_tasks(state: dict, max_parallel: int) -> None:
    research_tasks = state["stages"].get("orchestrator", {}).get("result", {}).get("research_tasks", [])
    if not research_tasks:
        print("[tasks] No tasks to run.")
        return

    stage = state["stages"].setdefault("tasks", {"status": "pending", "tasks": {}})
    stage["status"] = "in_progress"
    save_state(state)

    # Build work list -- skip completed, resume researched from review only
    work = []
    for task in research_tasks:
        slug = _topic_slug(task.get("topic", "unknown"))
        existing = stage["tasks"].get(slug, {})
        if existing.get("status") == "completed":
            print(f"[tasks] Skipping completed: {slug}")
            continue
        existing_pr = existing.get("pr")
        stage["tasks"].setdefault(slug, {"status": "pending"})
        work.append((slug, task, existing_pr))

    if not work:
        print("[tasks] All tasks already completed.")
        stage["status"] = "completed"
        save_state(state)
        return

    print(f"[tasks] Running {len(work)} task(s), max_parallel={max_parallel}")

    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {}
        for i, (slug, task, existing_pr) in enumerate(work):
            stage["tasks"][slug]["status"] = "in_progress"
            save_state(state)
            key_index = i % NUM_GEMINI_KEYS
            futures[pool.submit(_run_single_task, task, state["full_repo"], key_index, existing_pr)] = slug

        for future in as_completed(futures):
            slug = futures[future]
            try:
                pr = future.result()
                stage["tasks"][slug] = {"status": "completed", "pr": pr}
                print(f"[tasks] Completed: {slug} (PR #{pr})")
            except Exception as exc:
                prev = stage["tasks"].get(slug, {})
                stage["tasks"][slug] = {"status": "failed", "error": str(exc)}
                if prev.get("pr"):
                    stage["tasks"][slug]["pr"] = prev["pr"]
                print(f"[tasks] Failed: {slug} -- {exc}")
            save_state(state)

    all_ok = all(t.get("status") == "completed" for t in stage["tasks"].values())
    stage["status"] = "completed" if all_ok else "failed"
    save_state(state)

    done = sum(1 for t in stage["tasks"].values() if t["status"] == "completed")
    print(f"[tasks] Finished: {done}/{len(stage['tasks'])} completed.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_pipeline(repo_name: str, project_path: str, max_parallel: int, start_from: str) -> None:
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    state = load_state(repo_name)
    print(f"Pipeline: repo={state['full_repo']}, start_from={start_from}")

    t0 = time.time()
    if start_from == "orchestrator":
        run_orchestrator(state, project_path)
    run_tasks(state, max_parallel)
    print(f"\nPipeline finished in {time.time() - t0:.0f}s.")


def main():
    parser = argparse.ArgumentParser(description="BeeWork full pipeline")
    parser.add_argument("--repo", required=True, help="GitHub repo name")
    parser.add_argument("--project", required=True, help="Path to project requirements .md file")
    parser.add_argument("--max-parallel", type=int, default=5, help="Max parallel task agents")
    parser.add_argument("--start-from", choices=STAGES, default="orchestrator")
    args = parser.parse_args()
    run_pipeline(args.repo, args.project, args.max_parallel, args.start_from)


if __name__ == "__main__":
    main()
