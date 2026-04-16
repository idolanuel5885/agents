"""
Builtin.com scraper — targets remote jobs via Playwright DOM extraction.
The site is a client-side SPA with no __NEXT_DATA__, so we render the page
in a browser and extract job cards directly from the DOM.
"""

import asyncio
import logging
from typing import Optional
from urllib.parse import quote

from scrapers.base import BaseScraper, RawJob
from config.job_titles import _SEARCH_TERMS

log = logging.getLogger(__name__)

_BASE = "https://builtin.com"
# Only scrape remote — other geo editions are lower volume and slow to load
_SEARCH_URL = f"{_BASE}/jobs/remote?search={{term}}"


class BuiltinScraper(BaseScraper):
    name = "builtin"

    async def scrape(self) -> list[RawJob]:
        try:
            from playwright.async_api import async_playwright
            from scrapers.playwright_scrapers.base_playwright import get_browser
        except ImportError:
            log.error("[builtin] playwright not installed")
            return []

        results: list[RawJob] = []
        seen: set[str] = set()

        async with async_playwright() as pw:
            browser = await get_browser(pw)
            try:
                for term in _SEARCH_TERMS:
                    jobs = await self._scrape_term(browser, term)
                    for job in jobs:
                        if job.apply_url not in seen:
                            seen.add(job.apply_url)
                            results.append(job)
                    await asyncio.sleep(2)
            finally:
                await browser.close()

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    async def _scrape_term(self, browser, term: str) -> list[RawJob]:
        url = _SEARCH_URL.format(term=quote(term))

        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        try:
            from playwright_stealth import stealth_async
            page = await ctx.new_page()
            await stealth_async(page)
        except ImportError:
            page = await ctx.new_page()

        try:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                log.debug(f"[{self.name}] goto raised: {e} — continuing")

            await page.wait_for_timeout(3000)

            raw_jobs = await page.evaluate("""() => {
                const cards = document.querySelectorAll('[id^="job-card-"]');
                return Array.from(cards).map(card => {
                    const titleEl = card.querySelector('[data-id="job-card-title"]');
                    const companyEl = card.querySelector('[data-id="company-title"]');
                    // Info spans: first is work-type, second is location, third (if present) is salary
                    const infoSpans = Array.from(card.querySelectorAll('span.text-gray-04'))
                                          .map(s => s.textContent.trim()).filter(t => t);
                    const workType = infoSpans[0] || '';
                    const location = infoSpans[1] || '';
                    const salary = infoSpans.find(s => s.includes('Annually') || s.includes('Hourly')) || '';
                    return {
                        title: titleEl ? titleEl.textContent.trim() : '',
                        href: titleEl ? titleEl.getAttribute('href') : '',
                        company: companyEl ? companyEl.textContent.trim() : '',
                        workType,
                        location,
                        salary,
                    };
                });
            }""")

            return [j for j in (self._parse(item) for item in raw_jobs) if j]

        except Exception as e:
            log.warning(f"[{self.name}] '{term}' failed: {e}")
            return []
        finally:
            await page.close()
            await ctx.close()

    def _parse(self, item: dict) -> Optional[RawJob]:
        try:
            title = item.get("title", "").strip()
            href = item.get("href", "").strip()
            if not title or not href:
                return None

            url = href if href.startswith("http") else f"{_BASE}{href}"
            company = item.get("company", "Unknown").strip()
            work_type = item.get("workType", "").lower()
            location = item.get("location", "").strip()

            is_remote = "remote" in work_type or "remote" in location.lower()
            if not location:
                location = "Remote" if is_remote else ""

            salary_str = item.get("salary", "")
            sal_min, sal_max = self.parse_salary(salary_str)

            return RawJob(
                title=title,
                company=self.clean_company_name(company),
                apply_url=url,
                source=self.name,
                location=location,
                is_remote=is_remote,
                salary_raw=salary_str,
                salary_min=sal_min,
                salary_max=sal_max,
            )
        except Exception as e:
            log.debug(f"[{self.name}] parse error: {e}")
            return None
