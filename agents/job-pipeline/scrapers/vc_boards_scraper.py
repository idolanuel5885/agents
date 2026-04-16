"""
VC portfolio job board scraper.
Targets the Consider-platform boards used by a16z, Sequoia, Bessemer, Battery,
Lightspeed, GV, and First Round Capital.

Consider API flow:
  1. GET the board page to acquire a session cookie
  2. POST /api-boards/search-jobs with board ID + cursor pagination
  3. Filter locally — API keyword search is ignored server-side
"""

import asyncio
import logging
from typing import Optional

import httpx

from scrapers.base import BaseScraper, RawJob
from config.vc_portfolios import VC_BOARD_URLS

log = logging.getLogger(__name__)
_TIMEOUT = 25

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# Broad local filter: any of these substrings in the lowercased title will
# keep the job for the pipeline's fuzzy-match filter stage to evaluate.
_BROAD_KEYWORDS = [
    "head of ai", "vp of ai", "vp ai", "director of ai", "director ai",
    "chief ai", "caio", "gm of ai", "gm ai", "general manager ai",
    "head of artificial", "vp artificial",
    # Also keep anything that has "ai" AND a seniority marker
    # (handled separately in _matches_broad)
]
_LEADERSHIP_MARKERS = ["head of", "vp ", " vp,", "vice president", "director",
                        "chief", "general manager", "gm "]
_AI_MARKERS = [" ai ", " ai,", " ai/", "(ai", "ai-", "artificial intelligence",
               "machine learning", " ml ", "/ai"]


def _matches_broad(title: str) -> bool:
    t = title.lower()
    # Exact substring hit
    if any(kw in t for kw in _BROAD_KEYWORDS):
        return True
    # Leadership + AI combo
    has_leadership = any(m in t for m in _LEADERSHIP_MARKERS)
    has_ai = any(m in t for m in _AI_MARKERS)
    return has_leadership and has_ai


class VCBoardsScraper(BaseScraper):
    name = "vc_boards"

    async def scrape(self) -> list[RawJob]:
        results: list[RawJob] = []
        seen: set[str] = set()

        consider_boards = [b for b in VC_BOARD_URLS if b.get("type") == "consider"]

        async with httpx.AsyncClient(
            timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            for board in consider_boards:
                jobs = await self._scrape_consider(client, board)
                for job in jobs:
                    if job.apply_url not in seen:
                        seen.add(job.apply_url)
                        results.append(job)
                await asyncio.sleep(1)

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    async def _scrape_consider(
        self, client: httpx.AsyncClient, board: dict
    ) -> list[RawJob]:
        board_name = board["name"]
        board_url = board["url"]
        board_id = board.get("consider_id", "")

        if not board_id:
            log.warning(f"[{self.name}] No consider_id for {board_name} — skipping")
            return []

        # Derive the base domain from the URL (e.g. https://jobs.a16z.com/jobs -> https://jobs.a16z.com)
        from urllib.parse import urlparse
        parsed = urlparse(board_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        # Step 1: GET page to obtain session cookie
        try:
            await client.get(board_url, headers=_HEADERS)
        except Exception as e:
            log.warning(f"[{self.name}:{board_name}] Page GET failed: {e}")
            return []

        api_url = f"{base}/api-boards/search-jobs"
        api_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": base,
            "Referer": board_url,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

        results: list[RawJob] = []
        sequence: Optional[str] = None
        pages = 0
        max_pages = 6  # 6 × 500 = 3000 jobs per board

        while pages < max_pages:
            payload: dict = {
                "meta": {"size": 500},
                "board": {"id": board_id, "isParent": True},
                "query": {"promoteFeatured": False},
            }
            if sequence:
                payload["meta"]["sequence"] = sequence

            try:
                r = await client.post(api_url, json=payload, headers=api_headers)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log.warning(f"[{self.name}:{board_name}] API call failed (page {pages+1}): {e}")
                break

            jobs_raw = data.get("jobs", [])
            if not jobs_raw:
                break

            for item in jobs_raw:
                job = self._parse_item(item, board_name)
                if job and _matches_broad(job.title):
                    results.append(job)

            new_sequence = data.get("meta", {}).get("sequence")
            pages += 1
            log.debug(f"[{self.name}:{board_name}] page {pages}: {len(jobs_raw)} jobs, {len(results)} matching so far")

            if not new_sequence or new_sequence == sequence:
                break
            sequence = new_sequence

        return results

    def _parse_item(self, item: dict, board_name: str) -> Optional[RawJob]:
        try:
            title = item.get("title", "")
            apply_url = item.get("applyUrl", "") or item.get("url", "")
            if not title or not apply_url:
                return None

            company = item.get("companyName", "") or item.get("companyDomain", "")

            locs = item.get("locations") or item.get("normalizedLocations") or []
            if locs and isinstance(locs[0], dict):
                location = locs[0].get("label", "")
            elif locs:
                location = locs[0]
            else:
                location = ""

            is_remote = bool(item.get("remote")) or bool(item.get("hybrid"))
            if not is_remote and "remote" in location.lower():
                is_remote = True

            salary_data = item.get("salary") or {}
            sal_min = None
            sal_max = None
            salary_raw = ""
            if isinstance(salary_data, dict):
                sal_min = salary_data.get("minValue")
                sal_max = salary_data.get("maxValue")
                if sal_min or sal_max:
                    salary_raw = f"${sal_min or '?'} - ${sal_max or '?'}"

            size_raw = str(item.get("companyStaffCount", "")) if item.get("companyStaffCount") else ""

            ts = item.get("timeStamp", "")
            date_str = str(ts)[:10] if ts else ""

            return RawJob(
                title=title,
                company=self.clean_company_name(company),
                apply_url=apply_url,
                source=f"{self.name}:{board_name}",
                location=location,
                is_remote=is_remote,
                date_posted=date_str,
                salary_raw=salary_raw,
                salary_min=int(sal_min) if sal_min else None,
                salary_max=int(sal_max) if sal_max else None,
                company_size_raw=size_raw,
            )
        except Exception as e:
            log.debug(f"[{self.name}] parse error: {e}")
            return None
