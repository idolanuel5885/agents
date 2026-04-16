"""
Getro platform scraper — Insight Partners, Vista Equity, NFX.

Getro's v2 API requires auth. Instead we use the Next.js SSR endpoint:
  GET {board}/_next/data/{buildId}/jobs.json?q={keyword}
which returns 20 jobs per search term without auth. We run each of our
6 search terms per board, deduplicate, and pass to the filter stage.
"""

import json
import logging
import re
from typing import Optional
from urllib.parse import quote

import httpx

from scrapers.base import BaseScraper, RawJob
from config.job_titles import _SEARCH_TERMS

log = logging.getLogger(__name__)

_TIMEOUT = 20

_GETRO_BOARDS = [
    {"name": "Insight Partners", "url": "https://jobs.insightpartners.com"},
    {"name": "Vista Equity Partners", "url": "https://vistaequitypartners.getro.com"},
    {"name": "NFX", "url": "https://jobs.nfx.com"},
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


class GetroScraper(BaseScraper):
    name = "getro"

    async def scrape(self) -> list[RawJob]:
        results: list[RawJob] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            for board in _GETRO_BOARDS:
                jobs = await self._scrape_board(client, board)
                for job in jobs:
                    if job.apply_url not in seen:
                        seen.add(job.apply_url)
                        results.append(job)

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    async def _scrape_board(self, client: httpx.AsyncClient, board: dict) -> list[RawJob]:
        base_url = board["url"]
        board_name = board["name"]

        # Step 1: get build ID from the HTML page
        build_id = await self._get_build_id(client, f"{base_url}/jobs")
        if not build_id:
            log.warning(f"[{self.name}:{board_name}] Could not get buildId")
            return []

        results: list[RawJob] = []
        seen_ids: set = set()

        for term in _SEARCH_TERMS:
            url = f"{base_url}/_next/data/{build_id}/jobs.json?q={quote(term)}"
            try:
                r = await client.get(url, headers={**_HEADERS, "Referer": f"{base_url}/jobs"})
                r.raise_for_status()
                data = r.json()
                jobs_raw = (
                    data.get("pageProps", {})
                    .get("initialState", {})
                    .get("jobs", {})
                    .get("found", [])
                )
            except Exception as e:
                log.debug(f"[{self.name}:{board_name}] '{term}' failed: {e}")
                continue

            for item in jobs_raw:
                job_id = item.get("id")
                if job_id and job_id in seen_ids:
                    continue
                if job_id:
                    seen_ids.add(job_id)
                job = self._parse(item, board_name)
                if job:
                    results.append(job)

        return results

    async def _get_build_id(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        try:
            r = await client.get(url, headers={**_HEADERS, "Accept": "text/html"})
            m = re.search(r'"buildId"\s*:\s*"([^"]+)"', r.text)
            return m.group(1) if m else None
        except Exception as e:
            log.debug(f"[{self.name}] buildId fetch failed: {e}")
            return None

    def _parse(self, item: dict, board_name: str) -> Optional[RawJob]:
        try:
            title = item.get("title", "")
            url = item.get("url", "")
            if not title or not url:
                return None

            org = item.get("organization") or {}
            company = org.get("name", "") if isinstance(org, dict) else ""

            locations = item.get("locations") or item.get("searchableLocations") or []
            location = ", ".join(locations) if isinstance(locations, list) else str(locations)
            work_mode = item.get("workMode", "")
            is_remote = work_mode == "remote" or "remote" in location.lower()

            date_str = ""
            created = item.get("createdAt")
            if created:
                from datetime import datetime, timezone
                date_str = datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d")

            sal_min_cents = item.get("compensationAmountMinCents")
            sal_max_cents = item.get("compensationAmountMaxCents")
            sal_min = int(sal_min_cents / 100) if sal_min_cents else None
            sal_max = int(sal_max_cents / 100) if sal_max_cents else None
            salary_raw = f"${sal_min or '?'} - ${sal_max or '?'}" if (sal_min or sal_max) else ""

            size_raw = str(org.get("headCount", "")) if isinstance(org, dict) and org.get("headCount") else ""

            return RawJob(
                title=title,
                company=self.clean_company_name(company),
                apply_url=url,
                source=f"{self.name}:{board_name}",
                location=location,
                is_remote=is_remote,
                date_posted=date_str,
                salary_raw=salary_raw,
                salary_min=sal_min,
                salary_max=sal_max,
                company_size_raw=size_raw,
            )
        except Exception as e:
            log.debug(f"[{self.name}] parse error: {e}")
            return None
