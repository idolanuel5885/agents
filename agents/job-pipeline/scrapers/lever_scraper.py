"""
Lever public postings API scraper.
Each company has its own endpoint: https://api.lever.co/v0/postings/{slug}
"""

import asyncio
import logging
import re
from typing import Optional

import httpx

from scrapers.base import BaseScraper, RawJob
from config.vc_portfolios import ALL_VC_PORTFOLIO_SLUGS

log = logging.getLogger(__name__)

_BASE = "https://api.lever.co/v0/postings/{slug}?mode=json&limit=500"
_TIMEOUT = 15


class LeverScraper(BaseScraper):
    name = "lever"

    def __init__(self, extra_slugs: list[str] | None = None):
        self._slugs = [
            e["slug"] for e in ALL_VC_PORTFOLIO_SLUGS if e["ats"] == "lever"
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
            items = resp.json()
            if not isinstance(items, list):
                return []
            return [j for j in (self._parse_job(item, slug) for item in items) if j]
        except Exception as e:
            log.debug(f"[lever:{slug}] {type(e).__name__}: {e}")
            return []

    def _parse_job(self, item: dict, slug: str) -> Optional[RawJob]:
        try:
            title = item.get("text", "")
            url = item.get("hostedUrl", "") or item.get("applyUrl", "")
            if not title or not url:
                return None

            categories = item.get("categories", {})
            location = categories.get("location", "") or categories.get("allLocations", [""])[0]
            is_remote = "remote" in location.lower() or "remote" in title.lower()

            # date — Lever uses Unix timestamps in ms
            created_ts = item.get("createdAt", 0)
            date_str = ""
            if created_ts:
                from datetime import datetime, timezone
                date_str = datetime.fromtimestamp(created_ts / 1000, tz=timezone.utc).isoformat()[:10]

            # description
            lists_raw = item.get("lists", [])
            desc_parts = [item.get("descriptionPlain", "")]
            for lst in lists_raw:
                desc_parts.append(lst.get("text", ""))
                desc_parts.extend(lst.get("content", []))
            description = " ".join(p for p in desc_parts if p)

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
            log.debug(f"[lever] parse error: {e}")
            return None
