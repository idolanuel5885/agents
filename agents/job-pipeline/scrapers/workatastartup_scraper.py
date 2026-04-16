"""
Work at a Startup (YC job board) scraper.
The site uses Algolia for search. We extract the Algolia config from the
page source on first load, then query Algolia directly for subsequent searches.
Falls back to Playwright DOM scraping if Algolia extraction fails.
"""

import json
import logging
import re
from typing import Optional

import httpx

from scrapers.base import BaseScraper, RawJob
from config.job_titles import _SEARCH_TERMS

log = logging.getLogger(__name__)

_BASE_URL = "https://www.workatastartup.com"
_JOBS_URL = "https://www.workatastartup.com/jobs"
# Known Algolia app ID (may change — re-extracted dynamically if needed)
_ALGOLIA_APP_ID = "45BWZJ1SGC"
_ALGOLIA_INDEX = "Job_production"
_TIMEOUT = 20

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
}


class WorkAtAStartupScraper(BaseScraper):
    name = "workatastartup"

    def __init__(self):
        self._algolia_key: Optional[str] = None

    async def scrape(self) -> list[RawJob]:
        results: list[RawJob] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            # Step 1: Extract Algolia search-only API key from page
            await self._get_algolia_key(client)

            if self._algolia_key:
                for term in _SEARCH_TERMS:
                    jobs = await self._algolia_search(client, term)
                    for job in jobs:
                        if job.apply_url not in seen:
                            seen.add(job.apply_url)
                            results.append(job)
            else:
                # Fallback: simple HTML scrape
                jobs = await self._html_scrape(client)
                for job in jobs:
                    if job.apply_url not in seen:
                        seen.add(job.apply_url)
                        results.append(job)

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    async def _get_algolia_key(self, client: httpx.AsyncClient) -> None:
        try:
            resp = await client.get(_JOBS_URL, headers=_HEADERS)
            # Look for algoliaSearchKey or similar in page source
            match = re.search(r'"algoliaSearchKey"\s*:\s*"([a-zA-Z0-9]+)"', resp.text)
            if match:
                self._algolia_key = match.group(1)
                return
            # Also check for window.__algolia or similar JS objects
            match = re.search(r'algolia.*?apiKey.*?"([a-f0-9]{32})"', resp.text, re.IGNORECASE)
            if match:
                self._algolia_key = match.group(1)
        except Exception as e:
            log.debug(f"[{self.name}] Could not extract Algolia key: {e}")

    async def _algolia_search(self, client: httpx.AsyncClient, term: str) -> list[RawJob]:
        if not self._algolia_key:
            return []
        url = f"https://{_ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{_ALGOLIA_INDEX}/query"
        headers = {
            **_HEADERS,
            "X-Algolia-Application-Id": _ALGOLIA_APP_ID,
            "X-Algolia-API-Key": self._algolia_key,
        }
        payload = {
            "query": term,
            "hitsPerPage": 100,
            "filters": "remote:true",
        }
        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", [])
            return [j for j in (self._parse_algolia(hit) for hit in hits) if j]
        except Exception as e:
            log.warning(f"[{self.name}] Algolia search failed for '{term}': {e}")
            return []

    def _parse_algolia(self, hit: dict) -> Optional[RawJob]:
        try:
            title = hit.get("title", "") or hit.get("role", "")
            company_data = hit.get("company", {}) or {}
            company = company_data.get("name", "") if isinstance(company_data, dict) else str(company_data)
            job_id = hit.get("objectID", "")
            url = f"{_BASE_URL}/jobs/{job_id}" if job_id else ""

            if not title or not url:
                return None

            is_remote = hit.get("remote", False)
            location = hit.get("location", "Remote" if is_remote else "")

            date_str = ""
            created = hit.get("createdAt") or hit.get("updatedAt")
            if created:
                date_str = str(created)[:10]

            size_raw = ""
            if isinstance(company_data, dict):
                size_raw = company_data.get("numEmployees", "") or company_data.get("size", "")

            description = hit.get("description", "") or hit.get("responsibilities", "")

            return RawJob(
                title=title,
                company=self.clean_company_name(company),
                apply_url=url,
                source=self.name,
                location=location,
                is_remote=bool(is_remote),
                date_posted=date_str,
                company_size_raw=str(size_raw),
                description_raw=description,
            )
        except Exception as e:
            log.debug(f"[{self.name}] parse_algolia error: {e}")
            return None

    async def _html_scrape(self, client: httpx.AsyncClient) -> list[RawJob]:
        """Basic HTML fallback — limited but better than nothing."""
        try:
            from bs4 import BeautifulSoup
            resp = await client.get(
                f"{_JOBS_URL}?remote=true",
                headers={**_HEADERS, "Accept": "text/html"},
            )
            soup = BeautifulSoup(resp.text, "lxml")
            results = []
            for card in soup.select("[data-job-id], .job-card, article.job"):
                title_el = card.select_one("h2, h3, .job-title, [class*='title']")
                company_el = card.select_one(".company-name, [class*='company']")
                link_el = card.select_one("a[href*='/jobs/']")

                if not all([title_el, link_el]):
                    continue

                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                href = link_el.get("href", "")
                url = href if href.startswith("http") else f"{_BASE_URL}{href}"

                results.append(RawJob(
                    title=title,
                    company=self.clean_company_name(company),
                    apply_url=url,
                    source=self.name,
                    is_remote=True,
                ))
            return results
        except Exception as e:
            log.warning(f"[{self.name}] HTML fallback failed: {e}")
            return []
