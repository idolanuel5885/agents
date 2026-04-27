"""SQLite connection manager and all query helpers."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from config.settings import DB_PATH

_SCHEMA = Path(__file__).parent / "schema.sql"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript(_SCHEMA.read_text())


# ── Jobs ──────────────────────────────────────────────────────────────────────

def upsert_job(job: dict) -> tuple[bool, bool]:
    """
    Insert or update a job row.
    Returns (is_new, was_closed_now_reopened).
    """
    now = _now()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id, status FROM jobs WHERE id = ?", (job["id"],)
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO jobs
                (id, title, company, company_size_raw, date_posted, salary_raw,
                 location, is_remote, apply_url, source, description_raw,
                 status, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (
                    job["id"], job["title"], job["company"],
                    job.get("company_size_raw"), job.get("date_posted"),
                    job.get("salary_raw"), job.get("location"),
                    int(job.get("is_remote", False)),
                    job.get("apply_url"), job["source"],
                    job.get("description_raw"), now, now,
                ),
            )
            return True, False

        # Existing row — update last_seen and reopen if closed.
        # Also backfill any fields that were blank on first insert but now have data.
        was_closed = existing["status"] == "closed"
        existing_full = conn.execute(
            "SELECT location, salary_raw, date_posted, company_size_raw FROM jobs WHERE id = ?",
            (job["id"],)
        ).fetchone()

        updates: list[str] = ["last_seen = ?", "status = 'open'"]
        params: list = [now]

        for field, new_val in [
            ("location",        job.get("location") or ""),
            ("salary_raw",      job.get("salary_raw") or ""),
            ("date_posted",     job.get("date_posted") or ""),
            ("company_size_raw", job.get("company_size_raw") or ""),
        ]:
            if new_val and not (existing_full[field] or ""):
                updates.append(f"{field} = ?")
                params.append(new_val)

        params.append(job["id"])
        conn.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        return False, was_closed


def get_jobs_pending_filter() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE passed_filters IS NULL AND status = 'open'"
        ).fetchall()


def set_filter_result(job_id: str, passed: bool, reason: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET passed_filters = ?, excluded_reason = ? WHERE id = ?",
            (int(passed), reason if not passed else None, job_id),
        )


def get_jobs_pending_enrichment() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT j.* FROM jobs j
            LEFT JOIN leads l ON l.job_id = j.id
            WHERE j.passed_filters = 1
              AND j.status = 'open'
              AND l.job_id IS NULL
            """
        ).fetchall()


def upsert_lead(lead: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO leads
            (job_id, hiring_manager_name, hiring_manager_title, linkedin_url,
             email, email_confidence, enriched_at, hunter_credits_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
              hiring_manager_name  = excluded.hiring_manager_name,
              hiring_manager_title = excluded.hiring_manager_title,
              linkedin_url         = excluded.linkedin_url,
              email                = excluded.email,
              email_confidence     = excluded.email_confidence,
              enriched_at          = excluded.enriched_at,
              hunter_credits_used  = excluded.hunter_credits_used
            """,
            (
                lead["job_id"],
                lead.get("hiring_manager_name"),
                lead.get("hiring_manager_title"),
                lead.get("linkedin_url"),
                lead.get("email"),
                lead.get("email_confidence"),
                _now(),
                lead.get("hunter_credits_used", 0),
            ),
        )


def get_all_for_export() -> list[dict]:
    """Return all passed + open jobs joined with leads for sheet export.
    Deduplicates by (title, company) — keeps the row with the best date:
    valid ISO date preferred (most recent first), then falls back to lowest rowid.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT j.*, l.hiring_manager_name, l.hiring_manager_title,
                   l.linkedin_url, l.email, l.email_confidence
            FROM jobs j
            LEFT JOIN leads l ON l.job_id = j.id
            WHERE j.passed_filters = 1
              AND j.rowid IN (
                SELECT rowid FROM (
                  SELECT rowid,
                    ROW_NUMBER() OVER (
                      PARTITION BY LOWER(TRIM(title)), LOWER(TRIM(company))
                      ORDER BY
                        CASE
                          WHEN date_posted GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                          THEN 0 ELSE 1
                        END ASC,
                        date_posted DESC,
                        rowid ASC
                    ) AS rn
                  FROM jobs
                  WHERE passed_filters = 1
                ) ranked WHERE rn = 1
              )
            ORDER BY
              CASE
                WHEN j.date_posted GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
                THEN j.date_posted ELSE NULL
              END DESC NULLS LAST,
              j.first_seen DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def mark_closed_stale_jobs(days: int) -> int:
    """Mark jobs as closed if last_seen is more than `days` days ago."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        result = conn.execute(
            "UPDATE jobs SET status = 'closed' WHERE status = 'open' AND last_seen < ?",
            (cutoff,),
        )
        return result.rowcount


def update_sheet_row(job_id: str, row_num: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET sheet_row = ? WHERE id = ?", (row_num, job_id)
        )


def is_db_fresh() -> bool:
    """True when the jobs table is empty — signals an ephemeral/cron filesystem."""
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def seed_job_from_sheet(job: dict) -> None:
    """
    Insert a job record reconstructed from the Google Sheet.
    Skips silently if the ID already exists so a live scrape result is never
    overwritten.  All seeded rows are marked passed_filters=1 (they were
    already vetted when originally exported to the sheet).
    """
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job["id"],)).fetchone():
            return
        conn.execute(
            """
            INSERT INTO jobs
            (id, title, company, apply_url, source, location, is_remote,
             date_posted, salary_raw, company_size_raw, status,
             passed_filters, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                job["id"], job.get("title", ""), job.get("company", ""),
                job.get("apply_url", ""), job.get("source", "sheet"),
                job.get("location", ""), job.get("is_remote", 0),
                job.get("date_posted", ""), job.get("salary_raw", ""),
                job.get("company_size_raw", ""), job.get("status", "open"),
                job["last_seen"], job["last_seen"],
            ),
        )


def seed_lead_from_sheet(lead: dict) -> None:
    """Insert a lead record reconstructed from the Google Sheet."""
    if not lead.get("job_id"):
        return
    with get_conn() as conn:
        if conn.execute(
            "SELECT 1 FROM leads WHERE job_id = ?", (lead["job_id"],)
        ).fetchone():
            return
        conn.execute(
            """
            INSERT INTO leads
            (job_id, hiring_manager_name, hiring_manager_title,
             linkedin_url, email, email_confidence, enriched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead["job_id"],
                lead.get("hiring_manager_name"),
                lead.get("hiring_manager_title"),
                lead.get("linkedin_url"),
                lead.get("email"),
                lead.get("email_confidence"),
                lead.get("enriched_at"),
            ),
        )


# ── Company cache ─────────────────────────────────────────────────────────────

def get_cached_company(domain: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM company_cache
            WHERE domain = ?
              AND resolved_at > datetime('now', '-30 days')
            """,
            (domain,),
        ).fetchone()
        return dict(row) if row else None


def cache_company(data: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO company_cache
            (domain, company_name, linkedin_url, employee_count, employee_range, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
              employee_count = excluded.employee_count,
              employee_range = excluded.employee_range,
              linkedin_url   = excluded.linkedin_url,
              resolved_at    = excluded.resolved_at
            """,
            (
                data["domain"], data.get("company_name"),
                data.get("linkedin_url"), data.get("employee_count"),
                data.get("employee_range"), _now(),
            ),
        )


# ── Run log ───────────────────────────────────────────────────────────────────

def start_run(run_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO run_log (run_id, started_at) VALUES (?, ?)",
            (run_id, _now()),
        )


def finish_run(run_id: str, stats: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE run_log SET
              finished_at   = ?,
              jobs_found    = ?,
              jobs_new      = ?,
              jobs_closed   = ?,
              enriched      = ?,
              scraper_errors = ?,
              flags          = ?
            WHERE run_id = ?
            """,
            (
                _now(),
                stats.get("jobs_found", 0),
                stats.get("jobs_new", 0),
                stats.get("jobs_closed", 0),
                stats.get("enriched", 0),
                json.dumps(stats.get("errors", [])),
                json.dumps(stats.get("flags", [])),
                run_id,
            ),
        )
