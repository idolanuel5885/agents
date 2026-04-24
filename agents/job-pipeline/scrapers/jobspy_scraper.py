"""
Scraper for LinkedIn, Indeed, Glassdoor, and ZipRecruiter via python-jobspy.

JobSpy constraint: `hours_old` and `is_remote` cannot be combined on some
sites.  We run two passes per title — one with is_remote=True, one with
hours_old=720 — then merge results by apply_url.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from scrapers.base import BaseScraper, RawJob
from config.job_titles import TARGET_TITLES
from config.settings import SCRAPER_PROXY

log = logging.getLogger(__name__)

_SITES = ["linkedin", "indeed"]  # glassdoor/zip_recruiter consistently blocked


def _fmt_salary(sal_min, sal_max) -> str:
    """Format salary as '$180,000 - $240,000'."""
    if not sal_min and not sal_max:
        return ""
    def _fmt(v):
        try:
            return f"${int(float(v)):,}"
        except (TypeError, ValueError):
            return "?"
    if sal_min and sal_max:
        return f"{_fmt(sal_min)} - {_fmt(sal_max)}"
    if sal_min:
        return f"{_fmt(sal_min)}+"
    return f"Up to {_fmt(sal_max)}"

# Search terms submitted to LinkedIn and Indeed
_SEARCH_TERMS = [
    "Head of AI",
    "VP of AI",
    "Director of AI",
    "Chief AI Officer",
    "Head of AI Enablement",
    "Director of AI Enablement",
    "Head of Enterprise AI",
    "AI Program Director",
    "Head of Intelligent Automation",
    "VP of Business Transformation",
    "VP of Innovation",
    "Director of Innovation",
    "Head of Digital Transformation",
    "VP of Digital Transformation",
    "Director of Digital Transformation",
]


class JobSpyScraper(BaseScraper):
    name = "jobspy"

    async def scrape(self) -> list[RawJob]:
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._scrape_sync)
        except Exception as exc:
            log.error(f"[{self.name}] Fatal error: {exc}", exc_info=True)
            return []

    def _scrape_sync(self) -> list[RawJob]:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            log.error("[jobspy] python-jobspy is not installed. Run: pip install python-jobspy")
            return []

        seen_urls: set[str] = set()
        results: list[RawJob] = []

        proxies = None
        if SCRAPER_PROXY:
            proxies = {"http": SCRAPER_PROXY, "https": SCRAPER_PROXY}

        for term in _SEARCH_TERMS:
            for site in _SITES:
                # Pass A: remote filter (no date filter — JobSpy limitation)
                try:
                    df = scrape_jobs(
                        site_name=[site],
                        search_term=term,
                        is_remote=True,
                        results_wanted=50,
                        proxies=proxies,
                    )
                    for _, row in df.iterrows():
                        job = self._row_to_raw(row, site)
                        if job and job.apply_url not in seen_urls:
                            seen_urls.add(job.apply_url)
                            results.append(job)
                except Exception as e:
                    log.warning(f"[jobspy:{site}] Pass A failed for '{term}': {e}")

                # Pass B: date filter (no remote filter — separate pass)
                try:
                    df = scrape_jobs(
                        site_name=[site],
                        search_term=term,
                        hours_old=24 * 30,  # 30 days
                        results_wanted=50,
                        proxies=proxies,
                    )
                    for _, row in df.iterrows():
                        job = self._row_to_raw(row, site)
                        if job and job.apply_url not in seen_urls:
                            seen_urls.add(job.apply_url)
                            results.append(job)
                except Exception as e:
                    log.warning(f"[jobspy:{site}] Pass B failed for '{term}': {e}")

        log.info(f"[{self.name}] Collected {len(results)} raw jobs")
        return results

    @staticmethod
    def _val(row, *keys) -> str:
        """Safely get a string value from a pandas row, treating NaN/None as empty."""
        import math
        for k in keys:
            v = row.get(k)
            if v is None:
                continue
            try:
                if isinstance(v, float) and math.isnan(v):
                    continue
            except Exception:
                pass
            s = str(v).strip()
            if s and s.lower() != "nan":
                return s
        return ""

    def _row_to_raw(self, row, site: str) -> Optional[RawJob]:
        try:
            url = self._val(row, "job_url", "apply_url")
            if not url:
                return None

            title = self._val(row, "title")
            company = self._val(row, "company")
            if not title or not company:
                return None

            location = self._val(row, "location")
            is_remote = bool(row.get("is_remote", False))
            if not is_remote and "remote" in location.lower():
                is_remote = True

            # Date
            date_val = row.get("date_posted") or row.get("job_posted_at_datetime_utc")
            date_str = ""
            if date_val:
                if hasattr(date_val, "isoformat"):
                    date_str = date_val.isoformat()[:10]
                else:
                    date_str = str(date_val)[:10]

            # Salary
            sal_min = row.get("min_amount")
            sal_max = row.get("max_amount")
            salary_raw = _fmt_salary(sal_min, sal_max)

            description = str(row.get("description") or "")

            # Company size — jobspy returns this for LinkedIn
            size_raw = self._val(row, "company_num_employees")

            return RawJob(
                title=self.clean_company_name(title),
                company=self.clean_company_name(company),
                apply_url=url,
                source=f"jobspy:{site}",
                location=location,
                is_remote=is_remote,
                date_posted=date_str,
                salary_raw=salary_raw,
                salary_min=int(sal_min) if sal_min else None,
                salary_max=int(sal_max) if sal_max else None,
                company_size_raw=size_raw,
                description_raw=description,
            )
        except Exception as e:
            log.debug(f"[jobspy] Could not parse row: {e}")
            return None
