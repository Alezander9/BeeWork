"""BeeWork telemetry -- posts logs and events to Convex for the frontend."""

import os
import threading
import time

import requests

FLUSH_INTERVAL = 1.0

_session_id: str | None = None
_site_url: str | None = None
_secret: str | None = None
_buf: list[str] = []
_buf_lock = threading.Lock()
_flush_thread: threading.Thread | None = None
_stop = threading.Event()


def init(session_id: str):
    global _session_id, _site_url, _secret, _flush_thread
    _session_id = session_id
    _site_url = os.environ.get("CONVEX_SITE_URL")
    _secret = os.environ.get("BEEWORK_SECRET_KEY")
    if not _site_url or not _secret:
        print("[telemetry] CONVEX_SITE_URL or BEEWORK_SECRET_KEY not set -- telemetry disabled")
        return
    _stop.clear()
    _flush_thread = threading.Thread(target=_flush_loop, daemon=True)
    _flush_thread.start()


def _flush_loop():
    while not _stop.is_set():
        _stop.wait(FLUSH_INTERVAL)
        _do_flush()


def _do_flush():
    if not _session_id or not _site_url:
        return
    with _buf_lock:
        if not _buf:
            return
        text = "\n".join(_buf)
        _buf.clear()
    _post("/ingest", {"kind": "log", "sessionId": _session_id, "text": text})


def log(*lines: str):
    with _buf_lock:
        _buf.extend(lines)


def event(event_type: str, data: dict | None = None):
    if not _session_id or not _site_url:
        return
    _post("/ingest", {
        "kind": "event",
        "sessionId": _session_id,
        "type": event_type,
        "data": data or {},
    })


def status(new_status: str):
    if not _session_id or not _site_url:
        return
    _post("/updateStatus", {"sessionId": _session_id, "status": new_status})


def flush():
    _do_flush()
    _stop.set()


def _post(path: str, body: dict):
    try:
        body["secret"] = _secret
        requests.post(f"{_site_url}{path}", json=body, timeout=10)
    except Exception as e:
        print(f"[telemetry] post failed: {e}")
