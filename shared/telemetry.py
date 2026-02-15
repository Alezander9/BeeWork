"""Telemetry -- post pipeline events to Convex for the live dashboard.

Call emit() from anywhere in the pipeline to send a structured event.
Events are fire-and-forget: failures are logged but never block the pipeline.
"""

import httpx

CONVEX_URL: str | None = None  # set via configure()


def configure(convex_url: str) -> None:
    global CONVEX_URL
    CONVEX_URL = convex_url.rstrip("/")


def emit(run_id: str, event_type: str, data: dict | None = None) -> None:
    """Post a single event to Convex. Non-blocking best-effort."""
    if not CONVEX_URL:
        return
    payload = {"run_id": run_id, "type": event_type, "data": data or {}}
    try:
        httpx.post(f"{CONVEX_URL}/api/events", json=payload, timeout=5)
    except Exception as e:
        print(f"[telemetry] failed to emit {event_type}: {e}")
