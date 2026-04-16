"""
Himalayas.app scraper.
Uses their public jobs search API at /jobs/api/search.
"""

import logging
from typing import Optional

import httpx

from scrapers.base import BaseScraper, RawJob
from config.job_titles import _SEARCH_TERMS

log = logging.getLogger(__name__)

_SEARCH_URL = "https://himalayas.app/jobs/api/search"
_TIMEOUT = 20
_LIMIT = 100


class HimalayanScraper(BaseScraper):
    name = "himalayas"

    async def scrape(self) -> list[RawJob]:
        results: list[RawJob] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for term in _SEARCH_TERMS:
                jobs = await self._search(client, term)
                for job in jobs:
                    if job.apply_url not in seen:
                        seen.add(job.apply_url)
                        results.append(job)

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    async def _search(self, client: httpx.AsyncClient, term: str) -> list[RawJob]:
        params = {
            "q": term,
            "remote": "true",
            "limit": _LIMIT,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Accept": "application/json",
        }
        try:
            resp = await client.get(_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            jobs_data = data.get("jobs", [])
            return [j for j in (self._parse(item) for item in jobs_data) if j]
        except Exception as e:
            log.warning(f"[{self.name}] Search '{term}' failed: {type(e).__name__}: {e}")
            return []

    def _parse(self, item: dict) -> Optional[RawJob]:
        try:
            title = item.get("title", "")
            company = item.get("companyName", "")
            url = item.get("applicationLink", "") or item.get("guid", "")
            if not title or not url:
                return None

            location_list = item.get("locationRestrictions") or []
            location = ", ".join(location_list) if location_list else "Remote"
            is_remote = True  # Himalayas is remote-only

            date_str = ""
            pub = item.get("pubDate")
            if pub:
                from datetime import datetime, timezone
                date_str = datetime.fromtimestamp(pub, tz=timezone.utc).strftime("%Y-%m-%d")

            sal_min = item.get("minSalary")
            sal_max = item.get("maxSalary")
            salary_raw = ""
            if sal_min or sal_max:
                salary_raw = f"${sal_min or '?'} - ${sal_max or '?'}"

            description = item.get("description", "") or item.get("excerpt", "")

            return RawJob(
                title=title,
                company=self.clean_company_name(company),
                apply_url=url,
                source=self.name,
                location=location,
                is_remote=is_remote,
                date_posted=date_str,
                salary_raw=salary_raw,
                salary_min=int(sal_min) if sal_min else None,
                salary_max=int(sal_max) if sal_max else None,
                description_raw=description,
            )
        except Exception as e:
            log.debug(f"[himalayas] parse error: {e}")
            return None
