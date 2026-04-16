"""
Pallet job board scraper.
Pallet powers many creator-economy job boards. We scrape notable boards
individually since Pallet has no global search endpoint.
"""

import asyncio
import logging
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, RawJob
from config.job_titles import _SEARCH_TERMS

log = logging.getLogger(__name__)

# Known Pallet boards worth targeting for AI leadership roles
# Note: pallet.com/discover (404), jobs.firstround.com (login wall),
#       jobs.nfx.com (handled by getro_scraper), jobs.lennysnewsletter.com (dead domain)
_PALLET_BOARDS = [
    {"name": "Contrary Capital", "url": "https://jobs.contrary.com/jobs"},
]


class PalletScraper(BaseScraper):
    name = "pallet"

    async def scrape(self) -> list[RawJob]:
        try:
            from playwright.async_api import async_playwright
            from scrapers.playwright_scrapers.base_playwright import get_browser, get_page
        except ImportError:
            log.error("[pallet] playwright not installed")
            return []

        results: list[RawJob] = []
        seen: set[str] = set()

        async with async_playwright() as pw:
            browser = await get_browser(pw)
            try:
                for board in _PALLET_BOARDS:
                    for term in _SEARCH_TERMS[:3]:  # limit to top 3 terms for speed
                        jobs = await self._scrape_board(browser, board, term, get_page)
                        for job in jobs:
                            if job.apply_url not in seen:
                                seen.add(job.apply_url)
                                results.append(job)
                        await asyncio.sleep(1.5)
            finally:
                await browser.close()

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    async def _scrape_board(self, browser, board: dict, term: str, get_page_fn) -> list[RawJob]:
        board_url = board["url"]
        board_name = board["name"]
        search_url = f"{board_url}?q={quote(term)}"

        try:
            page = await get_page_fn(browser, search_url, wait_for="domcontentloaded")
            await page.wait_for_timeout(3000)
            html = await page.content()
            await page.close()
            return self._parse_html(html, board_url, board_name)
        except Exception as e:
            log.debug(f"[{self.name}:{board_name}] '{term}' failed: {e}")
            return []

    def _parse_html(self, html: str, board_url: str, board_name: str) -> list[RawJob]:
        results = []
        try:
            soup = BeautifulSoup(html, "lxml")
            for card in soup.select(
                "[data-job-id], .job-listing, .job-card, "
                "article[class*='job'], [class*='JobCard'], li[class*='job']"
            ):
                title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='role']")
                if not title_el:
                    continue
                company_el = card.select_one("[class*='company'], [class*='employer'], [class*='org']")
                link_el = card.select_one("a[href]")

                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True) if company_el else "Unknown"
                href = link_el.get("href", "") if link_el else ""
                url = href if href.startswith("http") else f"{board_url.rstrip('/')}{href}"

                location_el = card.select_one("[class*='location'], [class*='Location']")
                location = location_el.get_text(strip=True) if location_el else ""
                is_remote = "remote" in location.lower() or "remote" in title.lower()

                if title and url:
                    results.append(RawJob(
                        title=title,
                        company=self.clean_company_name(company),
                        apply_url=url,
                        source=f"{self.name}:{board_name}",
                        location=location,
                        is_remote=is_remote,
                    ))
        except Exception as e:
            log.debug(f"[{self.name}] HTML parse error: {e}")
        return results
