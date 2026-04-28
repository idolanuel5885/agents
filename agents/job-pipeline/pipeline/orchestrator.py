"""
Main async pipeline orchestrator.
Runs all four stages: Scrape → Filter → Enrich → Export.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from scrapers.registry import get_scrapers, PLAYWRIGHT_SCRAPERS
from scrapers.base import RawJob
from filters.title_filter import passes_title_filter
from filters.location_filter import passes_location_filter
from filters.date_filter import passes_date_filter
from filters.company_filter import passes_company_filter
from filters.description_filter import passes_description_filter
from filters.size_filter import passes_size_filter
from enrichment.hiring_manager import HiringManagerEnricher
from exporters.sheets_exporter import SheetsExporter
from db import database as db
from config.settings import (
    MAX_CONCURRENT_SCRAPERS,
    MAX_CONCURRENT_PLAYWRIGHT,
    DAYS_BEFORE_MARK_CLOSED,
    DRY_RUN,
)

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, scraper_names: Optional[list[str]] = None):
        self._scraper_names = scraper_names
        self._enricher = HiringManagerEnricher()
        self._exporter = SheetsExporter()

    async def run(self) -> dict:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        db.init_db()

        # On ephemeral filesystems (Railway cron) the DB is always fresh.
        # Re-seed it from the sheet so stale-detection, deduplication, and
        # enrichment-skipping all work as if the DB had been persisted.
        seeded = self._exporter.seed_db()
        if seeded:
            log.info(f"Re-seeded {seeded} historical jobs from sheet into fresh DB")

        db.start_run(run_id)

        stats = {
            "run_id": run_id,
            "jobs_found": 0,
            "jobs_new": 0,
            "jobs_closed": 0,
            "enriched": 0,
            "errors": [],
            "flags": [],
        }

        log.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log.info(f"  Pipeline run: {run_id}")
        log.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # ── Stage 1: Scrape ─────────────────────────────────────────────────
        log.info("Stage 1: Scraping job boards…")
        all_raw_jobs = await self._stage_scrape(stats)
        log.info(f"Stage 1 complete: {len(all_raw_jobs)} raw jobs collected")
        stats["jobs_found"] = len(all_raw_jobs)

        # ── Persist to DB ────────────────────────────────────────────────────
        for job in all_raw_jobs:
            is_new, _ = db.upsert_job(job.to_db_dict())
            if is_new:
                stats["jobs_new"] += 1

        # ── Stage 2: Filter ──────────────────────────────────────────────────
        log.info("Stage 2: Filtering jobs…")
        pending = db.get_jobs_pending_filter()
        passed_count = 0
        for job in pending:
            passed, reason = self._run_filters(dict(job))
            db.set_filter_result(job["id"], passed, reason)
            if passed:
                passed_count += 1
        log.info(f"Stage 2 complete: {passed_count}/{len(pending)} jobs passed filters")

        # ── Stage 3: Enrich ──────────────────────────────────────────────────
        log.info("Stage 3: Enriching with hiring manager data…")
        to_enrich = db.get_jobs_pending_enrichment()
        for job in to_enrich:
            try:
                lead = await self._enricher.enrich(dict(job))
                db.upsert_lead(lead)
                stats["enriched"] += 1
            except Exception as e:
                log.warning(f"[enrich] Failed for job {job['id']}: {e}")
        log.info(
            f"Stage 3 complete: {stats['enriched']} leads enriched "
            f"(Hunter credits: {self._enricher.total_hunter_credits})"
        )

        # ── Detect closed jobs ───────────────────────────────────────────────
        closed = db.mark_closed_stale_jobs(DAYS_BEFORE_MARK_CLOSED)
        stats["jobs_closed"] = closed
        if closed:
            log.info(f"Marked {closed} jobs as Closed (not seen in {DAYS_BEFORE_MARK_CLOSED}+ days)")

        # ── Stage 4: Export ──────────────────────────────────────────────────
        log.info("Stage 4: Exporting to Google Sheets…")
        all_jobs = db.get_all_for_export()
        print(f"[sheets] Exporting {len(all_jobs)} jobs to sheet…", flush=True)
        sheet_stats = self._exporter.sync(all_jobs)
        if "error" in sheet_stats:
            msg = sheet_stats["error"]
            print(f"[sheets] EXPORT FAILED: {msg}", flush=True)
            log.error(
                f"[sheets] EXPORT FAILED: {msg}\n"
                "  → Check GOOGLE_SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON; "
                "also verify the service account has Editor access to the spreadsheet."
            )
            stats["errors"].append({"stage": "export", "error": msg})
        else:
            print(
                f"[sheets] Export OK — new={sheet_stats['new']}, "
                f"updated={sheet_stats['updated']}",
                flush=True,
            )
            log.info(f"Stage 4 complete: {sheet_stats}")
        stats["sheet_stats"] = sheet_stats

        # ── Finish ───────────────────────────────────────────────────────────
        db.finish_run(run_id, stats)

        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log.info(f"  Run {run_id} complete")
        log.info(f"  Found:    {stats['jobs_found']}")
        log.info(f"  New:      {stats['jobs_new']}")
        log.info(f"  Filtered: {passed_count} passed")
        log.info(f"  Enriched: {stats['enriched']}")
        log.info(f"  Closed:   {stats['jobs_closed']}")
        if stats["errors"]:
            log.warning(f"  Errors:   {len(stats['errors'])} scraper(s) failed")
        log.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return stats

    async def _stage_scrape(self, stats: dict) -> list[RawJob]:
        scrapers = get_scrapers(self._scraper_names)

        # Split into normal and playwright scrapers for separate rate-limiting
        normal_scrapers = [s for s in scrapers if type(s) not in PLAYWRIGHT_SCRAPERS]
        pw_scrapers = [s for s in scrapers if type(s) in PLAYWRIGHT_SCRAPERS]

        all_jobs: list[RawJob] = []

        # Run normal scrapers concurrently (up to MAX_CONCURRENT_SCRAPERS)
        sem = asyncio.Semaphore(MAX_CONCURRENT_SCRAPERS)

        async def run_one(scraper):
            async with sem:
                log.info(f"  → Running {scraper.name}…")
                try:
                    jobs = await asyncio.wait_for(scraper.scrape(), timeout=360)
                    log.info(f"  ✓ {scraper.name}: {len(jobs)} jobs")
                    return jobs
                except asyncio.TimeoutError:
                    log.error(f"  ✗ {scraper.name}: timed out after 360s")
                    stats["errors"].append({"scraper": scraper.name, "error": "timeout"})
                    return []
                except Exception as e:
                    log.error(f"  ✗ {scraper.name}: {type(e).__name__}: {e}")
                    stats["errors"].append({"scraper": scraper.name, "error": str(e)})
                    return []

        tasks = [run_one(s) for s in normal_scrapers]
        results = await asyncio.gather(*tasks)
        for batch in results:
            all_jobs.extend(batch)

        # Run Playwright scrapers with a smaller concurrency limit
        pw_sem = asyncio.Semaphore(MAX_CONCURRENT_PLAYWRIGHT)

        async def run_pw(scraper):
            async with pw_sem:
                log.info(f"  → Running {scraper.name} (Playwright)…")
                try:
                    jobs = await asyncio.wait_for(scraper.scrape(), timeout=120)
                    log.info(f"  ✓ {scraper.name}: {len(jobs)} jobs")
                    return jobs
                except asyncio.TimeoutError:
                    log.error(f"  ✗ {scraper.name}: timed out after 120s")
                    stats["errors"].append({"scraper": scraper.name, "error": "timeout"})
                    return []
                except Exception as e:
                    log.error(f"  ✗ {scraper.name}: {type(e).__name__}: {e}")
                    stats["errors"].append({"scraper": scraper.name, "error": str(e)})
                    return []

        pw_tasks = [run_pw(s) for s in pw_scrapers]
        pw_results = await asyncio.gather(*pw_tasks)
        for batch in pw_results:
            all_jobs.extend(batch)

        # Deduplicate by job ID
        seen: dict[str, RawJob] = {}
        for job in all_jobs:
            if job.id not in seen:
                seen[job.id] = job
        return list(seen.values())

    def _run_filters(self, job: dict) -> tuple[bool, str]:
        """Run the filter chain. Returns (passed, reason_if_failed)."""
        checks = [
            lambda: passes_title_filter(job.get("title", "")),
            lambda: passes_company_filter(job.get("company", "")),
            lambda: passes_location_filter(job.get("location", ""), bool(job.get("is_remote"))),
            lambda: passes_date_filter(job.get("date_posted", ""), job.get("first_seen", "")),
            lambda: passes_description_filter(job.get("description_raw", "")),
            lambda: passes_size_filter(job.get("company_size_resolved"), job.get("company_size_raw", "")),
        ]
        for check in checks:
            passed, reason = check()
            if not passed:
                return False, reason
        return True, ""
