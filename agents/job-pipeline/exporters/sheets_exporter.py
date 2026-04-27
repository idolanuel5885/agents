"""
Google Sheets exporter.
Appends new jobs, marks closed jobs, sorts by date, and applies flag formatting.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config.settings import GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEET_ID, DRY_RUN, EMAIL_MIN_CONFIDENCE
from exporters.column_map import HEADERS, COL_IDX, DEDUP_COL
from filters.date_filter import is_approaching_stale

log = logging.getLogger(__name__)

_WORKSHEET_NAME = "Jobs"
_MAX_RETRIES = 3


class SheetsExporter:
    def __init__(self):
        self._sheet = None
        self._worksheet = None
        self._existing_urls: dict[str, int] = {}  # apply_url -> row_number

    def _connect(self):
        """Lazy-connect to Google Sheets."""
        if self._worksheet:
            return

        import json as _json
        import gspread
        from gspread.http_client import BackOffHTTPClient
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]

        creds_source = GOOGLE_SERVICE_ACCOUNT_JSON.strip()
        if creds_source.startswith("{"):
            # Inline JSON content (Railway / cloud deployments)
            creds = Credentials.from_service_account_info(
                _json.loads(creds_source), scopes=scopes
            )
        else:
            # File path (local development)
            creds_path = Path(creds_source)
            if not creds_path.exists():
                raise FileNotFoundError(
                    f"Google service account JSON not found at {creds_path}. "
                    f"Set GOOGLE_SERVICE_ACCOUNT_JSON to the file path or paste the JSON content directly."
                )
            creds = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
        gc = gspread.authorize(creds, http_client=BackOffHTTPClient)
        self._sheet = gc.open_by_key(GOOGLE_SHEET_ID)

        # Get or create the worksheet
        try:
            self._worksheet = self._sheet.worksheet(_WORKSHEET_NAME)
        except Exception:
            self._worksheet = self._sheet.add_worksheet(_WORKSHEET_NAME, rows=5000, cols=len(HEADERS))

        # Ensure header row
        first_row = self._worksheet.row_values(1)
        if first_row != HEADERS:
            self._worksheet.insert_row(HEADERS, 1)
            self._worksheet.format("1:1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.23, "green": 0.27, "blue": 0.71},
            })

        # Index existing rows by Apply URL; also track the last occupied row so
        # we can write new rows at exactly last_row+1 (avoiding the Sheets API's
        # unreliable table-detection which picks the wrong insertion point when
        # the sheet has blank rows near the top or stale data in far-right cols).
        url_col_idx = COL_IDX[DEDUP_COL] + 1  # gspread is 1-indexed
        self._last_data_row: int = 1  # will be updated below
        try:
            all_urls = self._worksheet.col_values(url_col_idx)
            for i, url in enumerate(all_urls[1:], start=2):  # skip header
                if url:
                    self._existing_urls[url.strip()] = i
                    self._last_data_row = max(self._last_data_row, i)
        except Exception as e:
            log.warning(f"[sheets] Could not index existing rows: {e}")

    def seed_db(self) -> int:
        """
        Re-hydrate the local SQLite DB from existing sheet rows.

        Called at pipeline start on ephemeral filesystems (Railway cron).  The
        sheet becomes the persistent store: job history, stale-detection
        timestamps, and hiring-manager data all flow back into the fresh DB so
        the rest of the pipeline behaves identically to a local run with a
        persisted DB.

        Skips immediately when the DB already has data (local / non-ephemeral
        runs) so there is zero overhead for the common case.

        Returns the number of rows seeded.
        """
        from db import database as db

        if not db.is_db_fresh():
            return 0

        try:
            self._connect()
        except Exception as e:
            log.warning(f"[sheets] seed_db: cannot connect to sheet — {e}")
            return 0

        all_values = self._worksheet.get_all_values()
        if len(all_values) <= 1:
            return 0

        seeded = 0
        for row in all_values[1:]:  # skip header row
            # Pad short rows so zip always produces all columns
            if len(row) < len(HEADERS):
                row = row + [""] * (len(HEADERS) - len(row))

            r = dict(zip(HEADERS, row))
            apply_url = r.get("Apply URL", "").strip()
            if not apply_url:
                continue

            title   = r.get("Job Title", "").strip()
            company = r.get("Company", "").strip()

            # Reconstruct the stable job ID (must match RawJob.id)
            key    = f"{company.lower().strip()}|{title.lower().strip()}|{apply_url.lower().strip()}"
            job_id = hashlib.sha256(key.encode()).hexdigest()[:32]

            last_seen = _parse_sheet_timestamp(r.get("Last Updated", ""))

            status = r.get("Status", "Open").lower().strip()
            if status not in ("open", "closed"):
                status = "open"

            db.seed_job_from_sheet({
                "id":               job_id,
                "title":            title,
                "company":          company,
                "apply_url":        apply_url,
                "source":           r.get("Job Board Source", "").strip() or "sheet",
                "location":         r.get("Location", ""),
                "is_remote":        1 if r.get("Remote?", "").lower() == "yes" else 0,
                "date_posted":      r.get("Date Posted", ""),
                "salary_raw":       r.get("Salary", ""),
                "company_size_raw": r.get("Company Size (employees)", ""),
                "status":           status,
                "last_seen":        last_seen,
            })

            # Seed lead data so enriched jobs aren't re-queried against Hunter
            mgr_name  = r.get("Hiring Manager Name", "").strip()
            mgr_email = r.get("Email", "").strip()
            if mgr_name or mgr_email:
                conf_raw = r.get("Email Confidence", "").replace("%", "").strip()
                try:
                    conf = int(float(conf_raw)) if conf_raw else None
                except ValueError:
                    conf = None

                db.seed_lead_from_sheet({
                    "job_id":                job_id,
                    "hiring_manager_name":   mgr_name or None,
                    "hiring_manager_title":  r.get("Hiring Manager Title", "").strip() or None,
                    "linkedin_url":          r.get("LinkedIn URL", "").strip() or None,
                    "email":                 mgr_email or None,
                    "email_confidence":      conf,
                    "enriched_at":           last_seen,
                })

            seeded += 1

        log.info(f"[sheets] Seeded {seeded} historical jobs from sheet into fresh DB")
        return seeded

    def sync(self, jobs: list[dict]) -> dict:
        """
        Sync jobs list to Google Sheet.
        Returns stats: {new, updated, closed, skipped}.
        """
        if DRY_RUN:
            log.info(f"[sheets] DRY RUN — would sync {len(jobs)} jobs (no sheet writes)")
            return {"new": 0, "updated": 0, "skipped": len(jobs)}

        try:
            self._connect()
        except Exception as e:
            log.error(f"[sheets] Cannot connect to Google Sheets: {e}")
            return {"error": str(e)}

        stats = {"new": 0, "updated": 0, "skipped": 0}
        new_rows: list[list] = []
        # Collect all cell updates to issue as one batch_update call
        batch_updates: list[dict] = []
        now = _now()

        for job in jobs:
            url = (job.get("apply_url") or "").strip()
            if not url:
                stats["skipped"] += 1
                continue

            row_data = self._job_to_row(job)

            if url in self._existing_urls:
                existing_row = self._existing_urls[url]
                status = job.get("status", "open").capitalize()
                status_col = COL_IDX["Status"] + 1
                updated_col = COL_IDX["Last Updated"] + 1
                batch_updates.append({
                    "range": f"R{existing_row}C{status_col}",
                    "values": [[status]],
                })
                batch_updates.append({
                    "range": f"R{existing_row}C{updated_col}",
                    "values": [[now]],
                })
                stats["updated"] += 1
            else:
                new_rows.append(row_data)
                stats["new"] += 1

        # Single batch_update for all cell changes (1 API call instead of N*2)
        if batch_updates:
            import time
            for attempt in range(_MAX_RETRIES):
                try:
                    self._worksheet.batch_update(batch_updates, value_input_option="USER_ENTERED")
                    break
                except Exception as e:
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                    else:
                        log.error(f"[sheets] batch_update failed: {e}")

        # Write new rows directly after the last known data row, bypassing the
        # Sheets API's table-detection which can pick the wrong insertion point.
        if new_rows:
            import time
            start_row = self._last_data_row + 1
            range_str = f"A{start_row}"
            for attempt in range(_MAX_RETRIES):
                try:
                    self._worksheet.update(
                        range_str,
                        new_rows,
                        value_input_option="USER_ENTERED",
                    )
                    break
                except Exception as e:
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                    else:
                        log.error(f"[sheets] update (new rows) failed: {e}")

        log.info(
            f"[sheets] Sync complete — new={stats['new']}, updated={stats['updated']}"
        )
        return stats

    def _job_to_row(self, job: dict) -> list:
        """Convert a job dict to a sheet row (ordered by HEADERS)."""
        date_posted = job.get("date_posted", "")
        email_confidence = job.get("email_confidence")
        status = job.get("status", "open")

        # Build flags
        flags = []
        if email_confidence is not None and email_confidence < 70:
            flags.append(f"⚠ Low email confidence ({email_confidence}%)")
        if is_approaching_stale(date_posted):
            flags.append("⚠ Posting >21 days old")

        location = job.get("location") or ""
        if not location:
            title_lower = job.get("title", "").lower()
            if job.get("is_remote") or "remote" in title_lower:
                location = "Remote"
            else:
                location = "Not specified"

        return [
            job.get("title", ""),
            job.get("company", ""),
            date_posted,
            _fmt_salary(job),
            location,
            "Yes" if job.get("is_remote") else "No",
            job.get("company_size_resolved") or job.get("company_size_raw") or "",
            job.get("apply_url", ""),
            job.get("source", ""),
            status.capitalize(),
            "; ".join(flags),
            job.get("hiring_manager_name", ""),
            job.get("hiring_manager_title", ""),
            job.get("linkedin_url", ""),
            job.get("email", ""),
            f"{email_confidence}%" if email_confidence is not None else "",
            _now()[:10],
        ]

    def _safe_get_cell(self, row: int, col: int) -> str:
        try:
            return self._worksheet.cell(row, col).value or ""
        except Exception:
            return ""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_salary(job: dict) -> str:
    """Format salary as '$180,000 - $240,000' using stored integers when available."""
    sal_min = job.get("salary_min")
    sal_max = job.get("salary_max")

    def _fmt(v):
        try:
            return f"${int(float(v)):,}"
        except (TypeError, ValueError):
            return "?"

    if sal_min or sal_max:
        if sal_min and sal_max:
            return f"{_fmt(sal_min)} - {_fmt(sal_max)}"
        if sal_min:
            return f"{_fmt(sal_min)}+"
        return f"Up to {_fmt(sal_max)}"

    return job.get("salary_raw", "")


def _parse_sheet_timestamp(ts: str) -> str:
    """
    Convert the sheet's "Last Updated" value ("2024-01-15 10:30 UTC") to an
    ISO 8601 UTC string suitable for SQLite comparisons.

    Falls back to 7 days ago so that unrecognised / blank entries are eligible
    for stale detection on the very next run — preventing them from lingering
    in the sheet as perpetually-open orphans.
    """
    if ts:
        m = re.match(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})", ts)
        if m:
            try:
                dt = datetime.strptime(
                    f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)
                return dt.isoformat()
            except ValueError:
                pass
    return (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
