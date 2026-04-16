"""
Wellfound (formerly AngelList Talent) scraper using Playwright.
We intercept the GraphQL/REST responses during page navigation rather than
parsing DOM, which is more reliable and less sensitive to UI changes.
"""

import asyncio
import json
import logging
from typing import Optional

from scrapers.base import BaseScraper, RawJob
from config.job_titles import _SEARCH_TERMS

log = logging.getLogger(__name__)

_BASE = "https://wellfound.com"
_SEARCH_URL = "https://wellfound.com/jobs?remote=true&query={term}"


class WellfoundScraper(BaseScraper):
    name = "wellfound"

    async def scrape(self) -> list[RawJob]:
        try:
            from playwright.async_api import async_playwright
            from scrapers.playwright_scrapers.base_playwright import get_browser
        except ImportError:
            log.error("[wellfound] playwright not installed. Run: playwright install chromium")
            return []

        results: list[RawJob] = []
        seen: set[str] = set()
        captured_jobs: list[dict] = []

        async with async_playwright() as pw:
            browser = await get_browser(pw)
            try:
                for term in _SEARCH_TERMS:
                    jobs = await self._scrape_term(browser, term, captured_jobs)
                    for job in jobs:
                        if job.apply_url not in seen:
                            seen.add(job.apply_url)
                            results.append(job)
                    await asyncio.sleep(2)  # polite delay
            finally:
                await browser.close()

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    async def _scrape_term(self, browser, term: str, captured: list) -> list[RawJob]:
        from urllib.parse import quote

        url = f"{_BASE}/jobs?remote=true&query={quote(term)}"
        intercepted: list[dict] = []

        # Create context + page manually so we can attach the response listener
        # BEFORE navigating — after get_page() returns it's already too late.
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

        # Block ads/tracking noise before navigation
        await page.route(
            "**/{ads,analytics,tracking,gtm,hotjar}**",
            lambda route: route.abort(),
        )

        # Attach response listener BEFORE goto so no responses are missed
        async def handle_response(response):
            if (
                "graphql" in response.url
                or "/api/jobs" in response.url
                or "talent.wellfound" in response.url
            ):
                try:
                    body = await response.json()
                    intercepted.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            try:
                await page.goto(url, wait_until="networkidle", timeout=8000)
            except Exception as e:
                log.debug(f"[{self.name}] goto raised: {e} — continuing")

            # Also try to extract from page's __NEXT_DATA__ or window state
            next_data = await page.evaluate(
                "() => { try { return JSON.parse(document.getElementById('__NEXT_DATA__').textContent) } catch(e) { return null } }"
            )
            if next_data:
                intercepted.append(next_data)

            jobs = []
            for data in intercepted:
                jobs.extend(self._extract_from_response(data, term))

            if not jobs:
                # Last resort: parse visible DOM
                jobs = await self._dom_parse(page)
            return jobs
        finally:
            await page.close()
            await ctx.close()

    def _extract_from_response(self, data: dict, term: str) -> list[RawJob]:
        results = []
        try:
            # Navigate various possible response structures
            candidates = []
            if "props" in data:
                # Next.js data
                page_props = data.get("props", {}).get("pageProps", {})
                for key in ("jobs", "jobListings", "results", "data"):
                    val = page_props.get(key, [])
                    if isinstance(val, list):
                        candidates.extend(val)
                    elif isinstance(val, dict):
                        for sub in val.values():
                            if isinstance(sub, list):
                                candidates.extend(sub)
            elif "data" in data:
                gql_data = data["data"]
                for key in ("jobs", "jobListings", "searchJobs"):
                    val = (gql_data or {}).get(key, {})
                    if isinstance(val, dict):
                        candidates.extend(val.get("edges", val.get("nodes", [])))
                    elif isinstance(val, list):
                        candidates.extend(val)

            for item in candidates:
                node = item.get("node", item) if isinstance(item, dict) else {}
                job = self._parse_item(node)
                if job:
                    results.append(job)
        except Exception as e:
            log.debug(f"[{self.name}] extract_from_response error: {e}")
        return results

    def _parse_item(self, item: dict) -> Optional[RawJob]:
        try:
            title = item.get("title", "") or item.get("role", "")
            startup = item.get("startup", item.get("company", {})) or {}
            company = startup.get("name", "") if isinstance(startup, dict) else str(startup)
            slug = item.get("slug", "") or item.get("id", "")
            url = f"{_BASE}/jobs/{slug}" if slug and not slug.startswith("http") else slug

            if not title or not url:
                return None

            location = item.get("locationNames", [])
            if isinstance(location, list):
                location = ", ".join(location)
            is_remote = item.get("remote", False) or "remote" in str(location).lower()

            date_str = ""
            posted = item.get("createdAt") or item.get("liveStartAt")
            if posted:
                date_str = str(posted)[:10]

            size_raw = ""
            if isinstance(startup, dict):
                size_raw = startup.get("highConcept", "") or startup.get("companySize", "")

            sal_min = item.get("minimumSalary") or item.get("salaryMin")
            sal_max = item.get("maximumSalary") or item.get("salaryMax")
            salary_raw = f"${sal_min}-${sal_max}" if (sal_min or sal_max) else ""

            return RawJob(
                title=title,
                company=self.clean_company_name(company),
                apply_url=url,
                source=self.name,
                location=str(location),
                is_remote=bool(is_remote),
                date_posted=date_str,
                salary_raw=salary_raw,
                salary_min=int(sal_min) if sal_min else None,
                salary_max=int(sal_max) if sal_max else None,
                company_size_raw=str(size_raw),
            )
        except Exception as e:
            log.debug(f"[{self.name}] parse_item error: {e}")
            return None

    async def _dom_parse(self, page) -> list[RawJob]:
        """Parse visible job cards from DOM as last resort."""
        results = []
        try:
            cards = await page.query_selector_all("[data-test='JobListing'], .styles_component__job, [class*='JobListing']")
            for card in cards:
                try:
                    title_el = await card.query_selector("h2, h3, [class*='title']")
                    company_el = await card.query_selector("[class*='company'], [class*='startup']")
                    link_el = await card.query_selector("a[href*='/jobs/']")
                    if not title_el:
                        continue
                    title = await title_el.inner_text()
                    company = await company_el.inner_text() if company_el else "Unknown"
                    href = await link_el.get_attribute("href") if link_el else ""
                    url = href if href.startswith("http") else f"{_BASE}{href}"
                    if title and url:
                        results.append(RawJob(
                            title=title.strip(),
                            company=self.clean_company_name(company.strip()),
                            apply_url=url,
                            source=self.name,
                            is_remote=True,
                        ))
                except Exception:
                    continue
        except Exception as e:
            log.debug(f"[{self.name}] DOM parse error: {e}")
        return results
