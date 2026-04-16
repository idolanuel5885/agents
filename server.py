"""
Agent runner — FastAPI backend.
Runs the job-pipeline and streams logs to the browser via Server-Sent Events.
"""

import asyncio
import json
import logging
import os
import queue
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Make job-pipeline importable
PIPELINE_DIR = Path(__file__).parent / "job-pipeline"
sys.path.insert(0, str(PIPELINE_DIR))

app = FastAPI(title="Agent Runner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run state ───────────────────────────────────────────────────────

_runs: dict[str, dict] = {}   # run_id -> {status, logs, started_at, finished_at, stats}
_active_run: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Log capture ───────────────────────────────────────────────────────────────

class QueueHandler(logging.Handler):
    """Push log records into a thread-safe queue so SSE can stream them."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.q = log_queue

    def emit(self, record: logging.LogRecord):
        self.q.put(self.format(record))


# ── Pipeline runner ───────────────────────────────────────────────────────────

def _run_pipeline_thread(run_id: str, scraper: str | None, dry_run: bool):
    global _active_run

    log_queue: queue.Queue = queue.Queue()
    _runs[run_id]["log_queue"] = log_queue

    # Wire a queue handler into the root logger for this thread
    handler = QueueHandler(log_queue)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)

    try:
        os.chdir(PIPELINE_DIR)
        if dry_run:
            os.environ["DRY_RUN"] = "true"
        else:
            os.environ.pop("DRY_RUN", None)

        from utils.logger import setup_logging
        setup_logging(verbose=True)

        from db import database as db
        from pipeline.orchestrator import Pipeline

        db.init_db()

        scraper_names = [scraper] if scraper else None
        pipeline = Pipeline(scraper_names=scraper_names)

        stats = asyncio.run(pipeline.run())
        _runs[run_id]["stats"] = stats
        _runs[run_id]["status"] = "done"
    except Exception as e:
        _runs[run_id]["status"] = "error"
        _runs[run_id]["error"] = str(e)
        log_queue.put(f"ERROR Pipeline failed: {e}")
    finally:
        root.removeHandler(handler)
        log_queue.put(None)  # sentinel: stream is finished
        _runs[run_id]["finished_at"] = _now()
        _active_run = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    index = Path(__file__).parent / "index.html"
    return HTMLResponse(index.read_text())


@app.post("/run")
async def start_run(scraper: str | None = None, dry_run: bool = False):
    global _active_run
    if _active_run:
        raise HTTPException(409, "A run is already in progress")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    _active_run = run_id
    _runs[run_id] = {
        "run_id": run_id,
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "stats": None,
        "error": None,
    }

    t = threading.Thread(target=_run_pipeline_thread, args=(run_id, scraper, dry_run), daemon=True)
    t.start()
    return {"run_id": run_id}


@app.get("/run/{run_id}/logs")
async def stream_logs(run_id: str):
    """Server-Sent Events stream of log lines for a run."""
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")

    async def generator() -> AsyncGenerator[str, None]:
        # Wait for log_queue to be attached (the thread sets it up immediately)
        for _ in range(50):
            if "log_queue" in _runs[run_id]:
                break
            await asyncio.sleep(0.1)

        q = _runs[run_id].get("log_queue")
        if not q:
            yield "data: [no log queue]\n\n"
            return

        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, q.get, True, 0.5)
                if line is None:  # sentinel
                    yield "data: __DONE__\n\n"
                    break
                # Escape newlines in the SSE data field
                safe = line.replace("\n", " ")
                yield f"data: {safe}\n\n"
            except queue.Empty:
                yield ": ping\n\n"  # keep-alive

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/run/{run_id}")
async def get_run(run_id: str):
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    r = dict(_runs[run_id])
    r.pop("log_queue", None)
    return r


@app.get("/runs")
async def list_runs():
    """Recent runs from the pipeline DB."""
    try:
        os.chdir(PIPELINE_DIR)
        from db import database as db
        import sqlite3
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM run_log ORDER BY started_at DESC LIMIT 20"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return {"error": str(e)}


@app.get("/status")
async def status():
    try:
        os.chdir(PIPELINE_DIR)
        from db import database as db
        with db.get_conn() as conn:
            jobs_open = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='open' AND passed_filters=1").fetchone()[0]
            jobs_total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        return {
            "active_run": _active_run,
            "jobs_open": jobs_open,
            "jobs_total": jobs_total,
            "leads": leads,
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/scrapers")
async def list_scrapers():
    try:
        sys.path.insert(0, str(PIPELINE_DIR))
        from scrapers.registry import SCRAPER_BY_NAME
        return sorted(SCRAPER_BY_NAME.keys())
    except Exception as e:
        return {"error": str(e)}
