"""
Agent Runner server.

Scans the ./agents/ subdirectory for agent folders and exposes them
via a minimal FastAPI interface that the UI calls.

Each agent folder must contain a run.py that accepts:
  --input  <text>   (optional; text from the UI input box)

Start:
  pip install -r requirements.txt
  uvicorn server:app --reload --port 8000
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR    = Path(__file__).parent
AGENTS_DIR  = BASE_DIR / "agents"

app = FastAPI(title="Agent Runner")


# ---------------------------------------------------------------------------
# Static UI
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(BASE_DIR / "index.html")

app.mount("/static", StaticFiles(directory=BASE_DIR, html=False), name="static")

@app.get("/style.css", include_in_schema=False)
async def css():
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")

@app.get("/app.js", include_in_schema=False)
async def js():
    return FileResponse(BASE_DIR / "app.js", media_type="application/javascript")


# ---------------------------------------------------------------------------
# Agent discovery
# ---------------------------------------------------------------------------

def discover_agents() -> list[str]:
    """Return names of subdirectories inside ./agents/ that contain a run.py."""
    if not AGENTS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in AGENTS_DIR.iterdir()
        if d.is_dir() and (d / "run.py").exists()
    )


@app.get("/agents")
async def list_agents():
    return {"agents": discover_agents()}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    agent: str
    input: str = ""


@app.post("/run")
async def run_agent(req: RunRequest):
    available = discover_agents()
    if req.agent not in available:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent}' not found.")

    agent_dir  = AGENTS_DIR / req.agent
    entry      = agent_dir / "run.py"
    cmd        = [sys.executable, str(entry)]

    if req.input:
        import shlex
        cmd += shlex.split(req.input)

    async def stream():
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(agent_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            yield line
        await proc.wait()

    return StreamingResponse(stream(), media_type="text/plain")
