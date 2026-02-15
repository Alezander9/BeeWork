"""Local FastAPI server -- receives pipeline trigger requests via cloudflared.

Run:
    uv run uvicorn shared.server:app --host 0.0.0.0 --port 8111
"""

import threading
import time
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="BeeWork Local Server")


class PipelineRequest(BaseModel):
    repo: str
    project: str
    max_parallel: int = 5
    start_from: str = "orchestrator"


class PipelineResponse(BaseModel):
    run_id: str
    status: str


def _run_pipeline_dummy(run_id: str, req: PipelineRequest) -> None:
    """Placeholder -- will call real full_pipeline.run_pipeline() later."""
    print(f"[server] Pipeline started: run_id={run_id} repo={req.repo}")
    time.sleep(2)
    print(f"[server] Pipeline finished: run_id={run_id}")


@app.post("/start-pipeline", response_model=PipelineResponse)
def start_pipeline(req: PipelineRequest) -> PipelineResponse:
    run_id = uuid.uuid4().hex[:12]
    threading.Thread(target=_run_pipeline_dummy, args=(run_id, req), daemon=True).start()
    return PipelineResponse(run_id=run_id, status="started")


@app.get("/health")
def health():
    return {"ok": True}
