"""
BeeWork full pipeline -- orchestrator -> concurrent research & review queues.

Usage:
    uv run python shared/full_pipeline.py --repo <name> --project <path> [--research-workers 5] [--review-workers 2]
"""

import argparse
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

OWNER = "workerbee-gbt"
NUM_GEMINI_KEYS = 5
REVIEW_POLL_INTERVAL = 2.0

REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY_0",
    "GITHUB_PAT",
    "ANTHROPIC_API_KEY",
    "PARALLEL_API_KEY",
    "BROWSER_USE_API_KEY",
    "LMNR_PROJECT_API_KEY",
]


def _topic_slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


# ---------------------------------------------------------------------------
# Research worker
# ---------------------------------------------------------------------------

def research_worker(research_q, review_q, full_repo):
    """Pull research tasks, run researcher, push results to review queue."""
    while True:
        task = research_q.get()
        if task is None:
            break
        slug = task["research_agent_id"]
        try:
            from researcher.run_researcher_agent import run as research
            pr = research(
                topic=task["topic"],
                prompt=task["prompt"],
                file_path=task["file_path"],
                websites=task["websites"],
                repo=full_repo,
                agent_id=slug,
                key_index=task["key_index"],
            )
            if pr is not None:
                review_q.put({
                    "pr": pr,
                    "file_path": task["file_path"],
                    "research_agent_id": slug,
                    "key_index": task["key_index"],
                })
                print(f"[research] Done: {slug} -> PR #{pr}")
            else:
                print(f"[research] No PR: {slug}")
        except Exception as e:
            print(f"[research] Failed: {slug} -- {e}")


# ---------------------------------------------------------------------------
# Review worker
# ---------------------------------------------------------------------------

def _take_unlocked(deferred, files_under_review, review_lock):
    """Pop and return the first deferred task whose file is not locked, or None."""
    remaining = []
    taken = None
    for task in deferred:
        if taken is None:
            with review_lock:
                if task["file_path"] not in files_under_review:
                    files_under_review.add(task["file_path"])
                    taken = task
                    continue
        remaining.append(task)
    deferred[:] = remaining
    return taken


def review_worker(review_q, full_repo, files_under_review, review_lock, done_event):
    """Pull review tasks, skip locked files (defer them), process unlocked ones."""
    deferred = []
    while True:
        # Try deferred items first
        task = _take_unlocked(deferred, files_under_review, review_lock)

        if task is None:
            # Pull from queue
            try:
                task = review_q.get(timeout=REVIEW_POLL_INTERVAL)
            except queue.Empty:
                if done_event.is_set() and not deferred:
                    break
                continue

            # Check file lock
            with review_lock:
                if task["file_path"] in files_under_review:
                    deferred.append(task)
                    continue
                files_under_review.add(task["file_path"])

        try:
            from reviewer.run_reviewer_agent import run as review
            review(
                repo=full_repo,
                pr=task["pr"],
                agent_id=task["research_agent_id"],
                key_index=task["key_index"],
            )
            print(f"[review] Done: PR #{task['pr']} ({task['research_agent_id']})")
        except Exception as e:
            print(f"[review] Failed: PR #{task['pr']} -- {e}")
        finally:
            with review_lock:
                files_under_review.discard(task["file_path"])


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_tasks(research_tasks, full_repo, num_research, num_review):
    """Run research and review concurrently using two queues."""
    if not research_tasks:
        print("[pipeline] No tasks.")
        return

    research_q = queue.Queue()
    review_q = queue.Queue()
    files_under_review = set()
    review_lock = threading.Lock()
    review_done = threading.Event()

    for i, task in enumerate(research_tasks):
        task["key_index"] = i % NUM_GEMINI_KEYS
        research_q.put(task)

    # Start review workers (block on empty queue until research produces items)
    review_threads = []
    for _ in range(num_review):
        t = threading.Thread(target=review_worker,
                             args=(review_q, full_repo, files_under_review, review_lock, review_done),
                             daemon=True)
        t.start()
        review_threads.append(t)

    # Start research workers
    research_threads = []
    for _ in range(num_research):
        t = threading.Thread(target=research_worker,
                             args=(research_q, review_q, full_repo),
                             daemon=True)
        t.start()
        research_threads.append(t)

    print(f"[pipeline] {len(research_tasks)} tasks, {num_research} research workers, {num_review} review workers")

    # Wait for all research to finish (sentinels signal exit)
    for _ in range(num_research):
        research_q.put(None)
    for t in research_threads:
        t.join()
    print("[pipeline] All research done.")

    # Signal review workers: no more items coming. They exit once queue + deferred are drained.
    review_done.set()
    for t in review_threads:
        t.join()
    print("[pipeline] All reviews done.")


def run_pipeline(repo_name, project_path, num_research, num_review):
    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    full_repo = f"{OWNER}/{repo_name}"
    print(f"Pipeline: repo={full_repo}")
    t0 = time.time()

    from orchestrator.run_orchestrator_agent import run as orchestrate
    result = orchestrate(repo_name, project_path)
    tasks = result["research_tasks"]
    for task in tasks:
        task["research_agent_id"] = _topic_slug(task.get("topic", "unknown"))
    print(f"[orchestrator] {len(tasks)} task(s)")

    run_tasks(tasks, full_repo, num_research, num_review)
    print(f"\nPipeline finished in {time.time() - t0:.0f}s.")


def main():
    parser = argparse.ArgumentParser(description="BeeWork full pipeline")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--research-workers", type=int, default=5)
    parser.add_argument("--review-workers", type=int, default=2)
    args = parser.parse_args()
    run_pipeline(args.repo, args.project, args.research_workers, args.review_workers)


if __name__ == "__main__":
    main()
