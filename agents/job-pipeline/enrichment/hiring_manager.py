"""
Hiring manager enrichment — Hunter.io only.

For each job listing:
1. Extract company domain from apply URL (or guess from company name)
2. Run Hunter.io domain search to find contacts with relevant titles
3. Return enriched lead dict
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

from enrichment.hunter_client import HunterClient, guess_email
from db import database as db
from config.settings import EMAIL_MIN_CONFIDENCE

log = logging.getLogger(__name__)

_TITLE_KEYWORDS = ["ceo", "coo", "cpo", "vp", "chief", "director", "president"]

# Job board / ATS domains that are NOT the company's own domain.
# If apply_url resolves to one of these, skip it and fall back to domain-guessing.
_JOB_BOARD_DOMAINS = {
    "linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com",
    "monster.com", "careerbuilder.com", "simplyhired.com", "dice.com",
    "wellfound.com", "angel.co", "greenhouse.io", "lever.co", "ashbyhq.com",
    "workable.com", "jobvite.com", "smartrecruiters.com", "icims.com",
    "taleo.net", "successfactors.com", "myworkdayjobs.com",
}


class HiringManagerEnricher:
    def __init__(self):
        self._hunter = HunterClient()

    @property
    def total_hunter_credits(self) -> int:
        return self._hunter.credits_used

    async def enrich(self, job: dict) -> dict:
        """
        Enrich a job dict with hiring manager contact data via Hunter.io.
        Returns a lead dict ready for db.upsert_lead().
        """
        company = job["company"]
        job_id = job["id"]
        apply_url = job.get("apply_url", "")

        lead = {
            "job_id": job_id,
            "hiring_manager_name": None,
            "hiring_manager_title": None,
            "linkedin_url": None,
            "email": None,
            "email_confidence": None,
            "hunter_credits_used": 0,
        }

        company_domain = self._extract_domain_from_url(apply_url) or _guess_domain(company)
        if not company_domain or not self._hunter._key:
            return lead

        domain_data = await self._hunter.domain_search(company_domain)
        emails = domain_data.get("emails", [])
        lead["hunter_credits_used"] = self._hunter.credits_used

        for contact in emails:
            contact_title = (contact.get("position") or "").lower()
            if any(kw in contact_title for kw in _TITLE_KEYWORDS):
                fn = contact.get("first_name", "")
                ln = contact.get("last_name", "")
                confidence = contact.get("confidence", 0)
                if confidence >= EMAIL_MIN_CONFIDENCE:
                    lead["hiring_manager_name"] = f"{fn} {ln}".strip() or None
                    lead["hiring_manager_title"] = contact.get("position")
                    lead["email"] = contact.get("value")
                    lead["email_confidence"] = confidence
                    break

        return lead

    def _extract_domain_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        try:
            host = urlparse(url).netloc
            parts = host.lstrip("www.").split(".")
            if len(parts) >= 2:
                domain = ".".join(parts[-2:])
                if domain in _JOB_BOARD_DOMAINS:
                    return None  # Don't search the job board itself
                return domain
        except Exception:
            pass
        return None


def _guess_domain(company_name: str) -> Optional[str]:
    """Best-guess company domain from name — used as last resort, often wrong."""
    if not company_name:
        return None
    clean = re.sub(r"[^a-z0-9]", "", company_name.lower())
    return f"{clean}.com"
