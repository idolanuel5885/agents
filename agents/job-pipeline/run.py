#!/usr/bin/env python3
"""
Job Lead Pipeline — single entry point.

Usage:
  python run.py                        # full pipeline (scrape + filter + enrich + export)
  python run.py --scrapers-only        # scrape and filter only, no enrichment or sheet write
  python run.py --enrich-only          # enrich already-scraped jobs (no new scraping)
  python run.py --export-only          # re-export to sheet from local DB (no scraping)
  python run.py --scraper himalayas    # run only a specific scraper by name
  python run.py --dry-run              # scrape + filter, no enrichment, no sheet writes
  python run.py --list-scrapers        # print available scraper names and exit
  python run.py --verbose              # verbose logging
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(
        description="Automated job lead pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--scrapers-only", action="store_true", help="Skip enrichment and sheet export")
    parser.add_argument("--enrich-only", action="store_true", help="Enrich existing jobs only, skip scraping")
    parser.add_argument("--export-only", action="store_true", help="Re-export to sheet from DB only")
    parser.add_argument("--dry-run", action="store_true", help="No enrichment, no sheet writes")
    parser.add_argument("--scraper", type=str, help="Run only this scraper (by name)")
    parser.add_argument("--list-scrapers", action="store_true", help="Print scraper names and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    if args.list_scrapers:
        from scrapers.registry import SCRAPER_BY_NAME
        print("Available scrapers:")
        for name in sorted(SCRAPER_BY_NAME):
            print(f"  {name}")
        return

    from utils.logger import setup_logging
    setup_logging(verbose=args.verbose)

    if args.dry_run:
        import os
        os.environ["DRY_RUN"] = "true"

    asyncio.run(_run(args))


async def _run(args):
    from db import database as db
    from config.settings import DRY_RUN

    db.init_db()

    if args.export_only:
        # Re-export only
        from exporters.sheets_exporter import SheetsExporter
        jobs = db.get_all_for_export()
        stats = SheetsExporter().sync(jobs)
        print(f"Export complete: {stats}")
        return

    if args.enrich_only:
        # Enrich only
        from enrichment.hiring_manager import HiringManagerEnricher
        enricher = HiringManagerEnricher()
        pending = db.get_jobs_pending_enrichment()
        print(f"Enriching {len(pending)} jobs…")
        for job in pending:
            try:
                lead = await enricher.enrich(dict(job))
                db.upsert_lead(lead)
            except Exception as e:
                print(f"  Enrich failed for {job['company']}: {e}")
        print(f"Done. Hunter credits used: {enricher.total_hunter_credits}")
        return

    # Full pipeline (or scrapers-only)
    scraper_names = [args.scraper] if args.scraper else None

    from pipeline.orchestrator import Pipeline
    pipeline = Pipeline(scraper_names=scraper_names)

    if args.scrapers_only or DRY_RUN:
        # Override to skip enrichment + export stages
        await _scrape_and_filter_only(pipeline)
    else:
        await pipeline.run()


async def _scrape_and_filter_only(pipeline):
    """Run only scrape + filter stages."""
    import logging
    log = logging.getLogger(__name__)
    from db import database as db
    from scrapers.registry import get_scrapers

    db.init_db()
    scrapers = get_scrapers(pipeline._scraper_names)

    import asyncio
    from scrapers.registry import PLAYWRIGHT_SCRAPERS
    from config.settings import MAX_CONCURRENT_SCRAPERS, MAX_CONCURRENT_PLAYWRIGHT

    all_jobs = []
    sem = asyncio.Semaphore(MAX_CONCURRENT_SCRAPERS)

    async def run_one(scraper):
        is_pw = type(scraper) in PLAYWRIGHT_SCRAPERS
        async with sem:
            log.info(f"Running {scraper.name}…")
            try:
                return await scraper.scrape()
            except Exception as e:
                log.error(f"{scraper.name} failed: {e}")
                return []

    results = await asyncio.gather(*[run_one(s) for s in scrapers])
    for batch in results:
        all_jobs.extend(batch)

    # Deduplicate
    seen = {}
    for job in all_jobs:
        if job.id not in seen:
            seen[job.id] = job
    unique = list(seen.values())

    # Persist
    new_count = 0
    for job in unique:
        is_new, _ = db.upsert_job(job.to_db_dict())
        if is_new:
            new_count += 1

    # Filter
    pending = db.get_jobs_pending_filter()
    passed = 0
    for job in pending:
        p, r = pipeline._run_filters(dict(job))
        db.set_filter_result(job["id"], p, r)
        if p:
            passed += 1

    from config.settings import DB_PATH
    log.info(f"Done: {len(unique)} jobs collected, {new_count} new, {passed} passed filters")
    log.info(f"DB: {DB_PATH}")


if __name__ == "__main__":
    main()
