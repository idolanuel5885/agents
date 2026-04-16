"""
Greenhouse public boards-api scraper.
Iterates known company slugs from config/vc_portfolios.py plus any extra
slugs supplied directly.  The Greenhouse API is fully public — no auth needed.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx

from scrapers.base import BaseScraper, RawJob
from config.vc_portfolios import ALL_VC_PORTFOLIO_SLUGS

log = logging.getLogger(__name__)

_BASE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
_TIMEOUT = 15  # seconds per request


class GreenhouseScraper(BaseScraper):
    name = "greenhouse"

    def __init__(self, extra_slugs: list[str] | None = None):
        self._slugs = [
            e["slug"] for e in ALL_VC_PORTFOLIO_SLUGS if e["ats"] == "greenhouse"
        ]
        if extra_slugs:
            self._slugs.extend(extra_slugs)
        # Deduplicate while preserving order
        seen: set[str] = set()
        self._slugs = [s for s in self._slugs if not (s in seen or seen.add(s))]

    async def scrape(self) -> list[RawJob]:
        results: list[RawJob] = []
        sem = asyncio.Semaphore(8)  # max 8 concurrent requests to Greenhouse

        async def _bounded(slug):
            async with sem:
                return await self._fetch_company(client, slug)

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            tasks = [_bounded(slug) for slug in self._slugs]
            batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, list):
                    results.extend(batch)
        log.info(f"[{self.name}] Collected {len(results)} raw jobs from {len(self._slugs)} companies")
        return results

    async def _fetch_company(self, client: httpx.AsyncClient, slug: str) -> list[RawJob]:
        url = _BASE.format(slug=slug) + "?content=true"
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", [])
            return [j for j in (self._parse_job(item, slug) for item in jobs) if j]
        except Exception as e:
            log.debug(f"[greenhouse:{slug}] {type(e).__name__}: {e}")
            return []

    def _parse_job(self, item: dict, slug: str) -> RawJob | None:
        try:
            title = item.get("title", "")
            url = item.get("absolute_url", "")
            if not title or not url:
                return None

            location_obj = item.get("location", {})
            location = location_obj.get("name", "") if isinstance(location_obj, dict) else str(location_obj)
            is_remote = "remote" in location.lower()

            # date
            date_str = ""
            raw_date = item.get("first_published") or item.get("updated_at")
            if raw_date:
                date_str = str(raw_date)[:10]

            # description (HTML stripped)
            description = item.get("content", "")
            if description:
                description = re.sub(r"<[^>]+>", " ", description)
                description = re.sub(r"\s+", " ", description).strip()

            # Company name derived from slug (metadata is a list of custom fields, not the org name)
            company_name = slug.replace("-", " ").title()

            return RawJob(
                title=title,
                company=self.clean_company_name(company_name),
                apply_url=url,
                source=self.name,
                location=location,
                is_remote=is_remote,
                date_posted=date_str,
                description_raw=description,
            )
        except Exception as e:
            log.debug(f"[greenhouse] parse error: {e}")
            return None
