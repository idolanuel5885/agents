"""
Agent Runner server.

Scans the ./agents/ subdirectory for agent folders and exposes them
via a minimal FastAPI interface that the UI calls.

Each agent folder must contain a run.py that accepts CLI flags.

Start:
  pip install -r requirements.txt
  uvicorn server:app --reload --port 8000
"""

import asyncio
import os
import shlex
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
# Claude helpers
# ---------------------------------------------------------------------------

def get_agent_help(agent_dir: Path) -> str:
    try:
        result = subprocess.run(
            [sys.executable, str(agent_dir / "run.py"), "--help"],
            capture_output=True, text=True, timeout=10, cwd=str(agent_dir),
        )
        return result.stdout or result.stderr
    except Exception:
        return ""


def _looks_like_flags(text: str) -> bool:
    """True if the input is already CLI flags rather than natural language."""
    return bool(text.strip().startswith("--") or text.strip().startswith("-"))


def parse_input_to_flags(user_input: str, help_text: str) -> list[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        if _looks_like_flags(user_input):
            return shlex.split(user_input)
        # Natural language with no API key — run with no flags, warn user
        print(
            "[Warning] ANTHROPIC_API_KEY is not set — cannot translate natural language to flags. "
            "Running the agent with no extra arguments. "
            "Set ANTHROPIC_API_KEY in your environment to enable natural language input.",
            flush=True,
        )
        return []

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f"Convert this natural language request into CLI arguments for the command below.\n"
        f"Request: \"{user_input}\"\n\n"
        f"CLI help output:\n{help_text}\n\n"
        f"Rules:\n"
        f"- Reply with ONLY the shell arguments, nothing else\n"
        f"- Quote any multi-word positional arguments with double quotes (e.g. \"food trucks in the US\")\n"
        f"- Named flags look like --flag value or --flag\n"
        f"- Reply with exactly (empty) if no arguments are needed"
    )
    msg = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    flags_text = msg.content[0].text.strip()
    if flags_text == "(empty)" or not flags_text:
        return []
    try:
        return shlex.split(flags_text)
    except ValueError:
        return []


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

    agent_dir = AGENTS_DIR / req.agent
    entry     = agent_dir / "run.py"
    cmd       = [sys.executable, str(entry)]

    if req.input:
        help_text = get_agent_help(agent_dir)
        flags = parse_input_to_flags(req.input, help_text)
        cmd += flags

    async def stream():
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(agent_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output_lines: list[str] = []
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            output_lines.append(line.decode(errors="replace"))
            yield line
        await proc.wait()

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if req.input and api_key:
            yield b"\n\n\u2500\u2500\u2500 Summary \u2500\u2500\u2500\n"
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            combined_output = "".join(output_lines)[-4000:]
            summary_prompt = (
                f"The user asked: \"{req.input}\"\n\n"
                f"The agent produced this output:\n{combined_output}\n\n"
                f"Write a short, friendly summary that directly answers what the user asked."
            )
            with client.messages.stream(
                model="claude-haiku-4-5",
                max_tokens=500,
                messages=[{"role": "user", "content": summary_prompt}],
            ) as s:
                for text in s.text_stream:
                    yield text.encode()

    return StreamingResponse(stream(), media_type="text/plain")
