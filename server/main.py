"""BeeWork local API server -- receives commands from Convex via cloudflared tunnel."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

SECRET_KEY = os.environ["BEEWORK_SECRET_KEY"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartRequest(BaseModel):
    sessionId: str
    repo: str
    researchWorkers: int = 5
    reviewWorkers: int = 2
    project: str = "shared/project_documents/tiny_test.md"


@app.post("/start")
async def start_pipeline(body: StartRequest, x_api_key: str = Header()):
    if x_api_key != SECRET_KEY:
        raise HTTPException(status_code=401, detail="invalid key")

    cmd = [
        sys.executable, str(PROJECT_ROOT / "shared" / "full_pipeline.py"),
        "--repo", body.repo,
        "--project", body.project,
        "--research-workers", str(body.researchWorkers),
        "--review-workers", str(body.reviewWorkers),
        "--session-id", body.sessionId,
    ]
    subprocess.Popen(cmd, cwd=str(PROJECT_ROOT))
    print(f"[server] launched pipeline for session {body.sessionId}")

    return {"ok": True}
