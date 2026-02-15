import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import telemetry

BASE_URL = "https://api.browser-use.com/api/v2"
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "browser_agent_output"
OUTPUT_FILE = OUTPUT_DIR / "result.json"
POLL_INTERVAL = 5
TIMEOUT = 10 * 60  # 10 minutes


def headers():
    return {
        "X-Browser-Use-API-Key": os.environ["BROWSER_USE_API_KEY"],
        "Content-Type": "application/json",
    }


def create_session():
    resp = requests.post(f"{BASE_URL}/sessions", json={"keepAlive": False}, headers=headers())
    resp.raise_for_status()
    return resp.json()


CITATION_PROMPT = (
    " IMPORTANT: For every piece of information you find, record the exact URL "
    "of the page where you found it. In your memory, always note [source: URL] "
    "next to each fact. In your final output, include a Citations section that "
    "maps each claim to its source URL."
)


def create_task(session_id, task, website=None):
    payload = {
        "task": task + CITATION_PROMPT,
        "sessionId": session_id,
        "llm": "browser-use-2.0",
        "maxSteps": 25,
        "judge": True,
    }
    if website:
        payload["startUrl"] = website
    resp = requests.post(f"{BASE_URL}/tasks", json=payload, headers=headers())
    resp.raise_for_status()
    return resp.json()


def poll_task(task_id, label="agent"):
    tag = f"{label}:" if label else ""
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > TIMEOUT:
            msg = f"[{tag}poll] timed out after {int(elapsed)}s"
            print(msg); telemetry.log(msg)
            return {"status": "timeout", "output": "Browser agent timed out", "steps": []}
        resp = requests.get(f"{BASE_URL}/tasks/{task_id}", headers=headers())
        resp.raise_for_status()
        task = resp.json()
        status = task.get("status")
        steps = task.get("steps", [])
        msg = f"[{tag}poll] status={status} steps={len(steps)} elapsed={int(elapsed)}s"
        print(msg); telemetry.log(msg)
        if status in ("finished", "stopped"):
            return task
        time.sleep(POLL_INTERVAL)


def run_browser_agent(task, website=None, label="agent"):
    """Run a browser-use agent and return the cleaned result dict."""
    tag = f"{label}:" if label else ""
    # Create session to get the live URL
    session = create_session()
    session_id = session["id"]
    live_url = session.get("liveUrl")
    msg = f"[{tag}session] {session_id}"
    print(msg); telemetry.log(msg)
    if live_url:
        msg = f"[{tag}live] {live_url}"
        print(msg); telemetry.log(msg)
        telemetry.event("browser_url", {"url": live_url, "agent": tag})

    # Start the task in the session
    task_resp = create_task(session_id, task, website)
    task_id = task_resp["id"]
    msg = f"[{tag}task] {task_id}"
    print(msg); telemetry.log(msg)

    # Poll until done
    result = poll_task(task_id, label=label)
    telemetry.event("browser_done", {"agent": tag, "status": result.get("status", "unknown")})

    # Strip fields the OpenCode agent doesn't need
    for key in ("id", "sessionId", "llm"):
        result.pop(key, None)
    for step in result.get("steps", []):
        for key in ("evaluationPreviousGoal", "nextGoal"):
            step.pop(key, None)

    output = result.get("output")
    if output:
        msg = f"[{tag}output] {output[:300]}"
        print(msg); telemetry.log(msg)
    verdict = result.get("judgeVerdict")
    if verdict is not None:
        msg = f"[{tag}judge] {verdict}"
        print(msg); telemetry.log(msg)
        telemetry.event("browser_judge_done", {"agent": tag, "verdict": verdict})

    return result


def main():
    parser = argparse.ArgumentParser(description="Start a browser-use agent for web research")
    parser.add_argument("--task", required=True, help="Task description for the browser agent")
    parser.add_argument("--website", help="Target website URL to start browsing from")
    args = parser.parse_args()

    result = run_browser_agent(args.task, args.website)

    # Dump results to a fixed, predictable path
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, indent=2))
    print(f"Results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
