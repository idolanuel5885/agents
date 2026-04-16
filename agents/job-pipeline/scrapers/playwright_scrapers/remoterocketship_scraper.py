"""
Remote Rocketship scraper using Playwright.
Site returns 403 on plain HTTP requests — browser required.
"""

import asyncio
import logging
from typing import Optional
from urllib.parse import quote

from scrapers.base import BaseScraper, RawJob
from config.job_titles import _SEARCH_TERMS

log = logging.getLogger(__name__)

_BASE = "https://remoterocketship.com"


class RemoteRocketshipScraper(BaseScraper):
    name = "remoterocketship"

    async def scrape(self) -> list[RawJob]:
        try:
            from playwright.async_api import async_playwright
            from scrapers.playwright_scrapers.base_playwright import get_browser
        except ImportError:
            log.error("[remoterocketship] playwright not installed")
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
        url = f"{_BASE}/jobs?keyword={quote(term)}"
        intercepted = []
        jobs = []

        # Create context + page manually so we can attach the response listener
        # and request interception BEFORE navigating — after get_page() returns
        # it's already too late to catch XHR/API responses from the page load.
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

        # Set up request interception BEFORE navigation
        await page.route("**/*", lambda route: route.continue_())

        # Attach response listener BEFORE goto so no responses are missed
        async def handle_response(response):
            if "/api" in response.url:
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        body = await response.json()
                        intercepted.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                log.debug(f"[{self.name}] goto raised: {e} — continuing")

            if intercepted:
                for data in intercepted:
                    jobs.extend(self._parse_api_response(data))
            else:
                jobs = await self._parse_dom(page)
        finally:
            await page.close()
            await ctx.close()

        return jobs

    def _parse_api_response(self, data: dict | list) -> list[RawJob]:
        results = []
        items = data if isinstance(data, list) else data.get("jobs", data.get("results", []))
        for item in items:
            if not isinstance(item, dict):
                continue
            job = self._parse_item(item)
            if job:
                results.append(job)
        return results

    def _parse_item(self, item: dict) -> Optional[RawJob]:
        try:
            title = item.get("title", "") or item.get("jobTitle", "")
            company = item.get("companyName", "") or item.get("company", "")
            if isinstance(company, dict):
                company = company.get("name", "")
            url = item.get("url", "") or item.get("applyUrl", "") or item.get("link", "")
            if not url.startswith("http"):
                url = f"{_BASE}{url}" if url else ""
            if not title or not url:
                return None

            location = item.get("location", "Remote")
            is_remote = item.get("remote", True)
            date_str = str(item.get("postedAt", item.get("datePosted", "")))[:10]
            sal_min, sal_max = self.parse_salary(item.get("salary", ""))

            return RawJob(
                title=title,
                company=self.clean_company_name(str(company)),
                apply_url=url,
                source=self.name,
                location=str(location),
                is_remote=bool(is_remote),
                date_posted=date_str if date_str != "None" else "",
                salary_raw=item.get("salary", ""),
                salary_min=sal_min,
                salary_max=sal_max,
            )
        except Exception as e:
            log.debug(f"[{self.name}] parse_item error: {e}")
            return None

    async def _parse_dom(self, page) -> list[RawJob]:
        results = []
        try:
            cards = await page.query_selector_all("article, .job-card, [class*='JobCard'], li[class*='job']")
            for card in cards:
                try:
                    title_el = await card.query_selector("h2, h3, [class*='title'], [class*='role']")
                    company_el = await card.query_selector("[class*='company'], [class*='employer']")
                    link_el = await card.query_selector("a[href]")
                    if not title_el or not link_el:
                        continue
                    title = (await title_el.inner_text()).strip()
                    company = (await company_el.inner_text()).strip() if company_el else "Unknown"
                    href = await link_el.get_attribute("href")
                    url = href if (href or "").startswith("http") else f"{_BASE}{href}"
                    if title:
                        results.append(RawJob(
                            title=title,
                            company=self.clean_company_name(company),
                            apply_url=url,
                            source=self.name,
                            is_remote=True,
                        ))
                except Exception:
                    continue
        except Exception as e:
            log.debug(f"[{self.name}] DOM parse error: {e}")
        return results
