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

from shared import telemetry

OWNER = "workerbee-gbt"
NUM_GEMINI_KEYS = 5
REVIEW_POLL_INTERVAL = 2.0
TASK_TIMEOUT = 15 * 60  # seconds -- skip a stuck task after this

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


def _run_with_timeout(fn, label, timeout=TASK_TIMEOUT):
    """Run *fn* in a daemon thread; return True if it finished, False if timed out."""
    result = {}
    def _wrapper():
        try:
            result["value"] = fn()
        except Exception as e:
            result["error"] = e
    t = threading.Thread(target=_wrapper, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        msg = f"[timeout] {label} still running after {timeout}s -- skipping"
        print(msg); telemetry.log(msg)
        return None
    if "error" in result:
        raise result["error"]
    return result.get("value")


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
        telemetry.event("researcher_started", {"agent_id": slug, "topic": task["topic"]})
        try:
            from researcher.run_researcher_agent import run as research
            pr = _run_with_timeout(
                lambda: research(
                    topic=task["topic"],
                    prompt=task["prompt"],
                    file_path=task["file_path"],
                    websites=task["websites"],
                    repo=full_repo,
                    agent_id=slug,
                    key_index=task["key_index"],
                    label=slug,
                ),
                label=f"research:{slug}",
            )
            if pr is not None:
                review_q.put({
                    "pr": pr,
                    "file_path": task["file_path"],
                    "research_agent_id": slug,
                    "key_index": task["key_index"],
                })
                msg = f"[research] Done: {slug} -> PR #{pr}"
                print(msg); telemetry.log(msg)
                telemetry.event("researcher_done", {"agent_id": slug, "pr": pr})
                telemetry.event("pr_created", {"pr": pr, "agent_id": slug, "repo": full_repo})
            else:
                msg = f"[research] No PR: {slug}"
                print(msg); telemetry.log(msg)
                telemetry.event("researcher_done", {"agent_id": slug, "pr": None})
        except Exception as e:
            msg = f"[research] Failed: {slug} -- {e}"
            print(msg); telemetry.log(msg)
            telemetry.event("researcher_done", {"agent_id": slug, "error": str(e)})


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

        telemetry.event("reviewer_started", {"pr": task["pr"], "agent_id": task["research_agent_id"]})
        try:
            from reviewer.run_reviewer_agent import run as review
            review_label = f"review:PR#{task['pr']}"
            _run_with_timeout(
                lambda: review(
                    repo=full_repo,
                    pr=task["pr"],
                    agent_id=task["research_agent_id"],
                    key_index=task["key_index"],
                    label=review_label,
                ),
                label=review_label,
            )
            msg = f"[review] Done: PR #{task['pr']} ({task['research_agent_id']})"
            print(msg); telemetry.log(msg)
            telemetry.event("reviewer_done", {"pr": task["pr"], "agent_id": task["research_agent_id"]})
        except Exception as e:
            msg = f"[review] Failed: PR #{task['pr']} -- {e}"
            print(msg); telemetry.log(msg)
            telemetry.event("reviewer_done", {"pr": task["pr"], "error": str(e)})
        finally:
            with review_lock:
                files_under_review.discard(task["file_path"])


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_tasks(research_tasks, full_repo, num_research, num_review):
    """Run research and review concurrently using two queues."""
    if not research_tasks:
        msg = "[pipeline] No tasks."
        print(msg); telemetry.log(msg)
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

    msg = f"[pipeline] {len(research_tasks)} tasks, {num_research} research workers, {num_review} review workers"
    print(msg); telemetry.log(msg)

    # Wait for all research to finish (sentinels signal exit)
    for _ in range(num_research):
        research_q.put(None)
    for t in research_threads:
        t.join()
    msg = "[pipeline] All research done."
    print(msg); telemetry.log(msg)

    # Signal review workers: no more items coming. They exit once queue + deferred are drained.
    review_done.set()
    for t in review_threads:
        t.join()
    msg = "[pipeline] All reviews done."
    print(msg); telemetry.log(msg)


def run_pipeline(repo_name, project_path, num_research, num_review, session_id=None):
    if session_id:
        telemetry.init(session_id)
        telemetry.status("running")

    missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")

    full_repo = f"{OWNER}/{repo_name}"
    msg = f"[pipeline] repo={full_repo}, research={num_research}, review={num_review}"
    print(msg); telemetry.log(msg)
    t0 = time.time()

    telemetry.event("pipeline_started", {
        "repo": full_repo,
        "researchWorkers": num_research,
        "reviewWorkers": num_review,
    })

    from orchestrator.run_orchestrator_agent import run as orchestrate
    result = orchestrate(repo_name, project_path)
    tasks = result["research_tasks"]
    for task in tasks:
        task["research_agent_id"] = _topic_slug(task.get("topic", "unknown"))
    msg = f"[orchestrator] {len(tasks)} task(s)"
    print(msg); telemetry.log(msg)
    for task in tasks:
        msg = f"[pipeline] Task: {task['research_agent_id']} -> {task.get('file_path', '?')}"
        print(msg); telemetry.log(msg)
    telemetry.event("orchestrator_done", {"taskCount": len(tasks)})

    run_tasks(tasks, full_repo, num_research, num_review)
    elapsed = time.time() - t0
    msg = f"[pipeline] Finished in {elapsed:.0f}s"
    print(msg); telemetry.log(msg)
    telemetry.event("pipeline_done", {"elapsedSeconds": int(elapsed)})
    telemetry.status("completed")
    telemetry.flush()


def main():
    parser = argparse.ArgumentParser(description="BeeWork full pipeline")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--research-workers", type=int, default=5)
    parser.add_argument("--review-workers", type=int, default=2)
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args()
    run_pipeline(args.repo, args.project, args.research_workers, args.review_workers, args.session_id)


if __name__ == "__main__":
    main()
