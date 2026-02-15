"""BeeWork local API server -- receives commands from the website via cloudflared tunnel."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SECRET_KEY = os.environ["BEEWORK_SECRET_KEY"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/session")
async def create_session(x_api_key: str = Header()):
    if x_api_key != SECRET_KEY:
        raise HTTPException(status_code=401, detail="invalid key")
    print("hello world")
    return {"ok": True}
