"""
Ashby HQ public job board API scraper.
Endpoint: https://api.ashbyhq.com/posting-api/job-board/{slug}
"""

import asyncio
import logging
from typing import Optional

import httpx

from scrapers.base import BaseScraper, RawJob
from config.vc_portfolios import ALL_VC_PORTFOLIO_SLUGS

log = logging.getLogger(__name__)

_BASE = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
_TIMEOUT = 15


class AshbyScraper(BaseScraper):
    name = "ashby"

    def __init__(self, extra_slugs: list[str] | None = None):
        self._slugs = [
            e["slug"] for e in ALL_VC_PORTFOLIO_SLUGS if e["ats"] == "ashby"
        ]
        if extra_slugs:
            self._slugs.extend(extra_slugs)
        seen: set[str] = set()
        self._slugs = [s for s in self._slugs if not (s in seen or seen.add(s))]

    async def scrape(self) -> list[RawJob]:
        results: list[RawJob] = []
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            tasks = [self._fetch_company(client, slug) for slug in self._slugs]
            batches = await asyncio.gather(*tasks, return_exceptions=True)
            for batch in batches:
                if isinstance(batch, list):
                    results.extend(batch)
        log.info(f"[{self.name}] Collected {len(results)} raw jobs from {len(self._slugs)} companies")
        return results

    async def _fetch_company(self, client: httpx.AsyncClient, slug: str) -> list[RawJob]:
        url = _BASE.format(slug=slug)
        try:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code in (404, 403):
                return []
            resp.raise_for_status()
            data = resp.json()
            jobs = data.get("jobs", data.get("jobPostings", []))
            org = data.get("organization", {})
            company_name = org.get("name", slug.replace("-", " ").title())
            return [
                j for j in (self._parse_job(item, company_name) for item in jobs) if j
            ]
        except Exception as e:
            log.debug(f"[ashby:{slug}] {type(e).__name__}: {e}")
            return []

    def _parse_job(self, item: dict, company_name: str) -> Optional[RawJob]:
        try:
            title = item.get("title", "")
            url = item.get("jobUrl", "") or item.get("applyUrl", "")
            if not title or not url:
                return None

            workplace = item.get("workplaceType", "")
            is_remote = workplace.lower() == "remote" or item.get("isRemote", False)
            location = item.get("location", "") or workplace

            date_str = ""
            published = item.get("publishedAt")
            if published:
                date_str = str(published)[:10]

            # Salary
            salary_raw = ""
            salary_min = None
            salary_max = None
            comp = item.get("compensation")
            if comp:
                if isinstance(comp, dict):
                    salary_min = comp.get("minValue")
                    salary_max = comp.get("maxValue")
                    currency = comp.get("currency", "USD")
                    period = comp.get("period", "")
                    salary_raw = f"{currency} {salary_min or '?'}-{salary_max or '?'} {period}".strip()

            description = item.get("descriptionPlain", "") or item.get("description", "")

            return RawJob(
                title=title,
                company=self.clean_company_name(company_name),
                apply_url=url,
                source=self.name,
                location=location,
                is_remote=is_remote,
                date_posted=date_str,
                salary_raw=salary_raw,
                salary_min=int(salary_min) if salary_min else None,
                salary_max=int(salary_max) if salary_max else None,
                description_raw=description,
            )
        except Exception as e:
            log.debug(f"[ashby] parse error: {e}")
            return None
