"""
Hunter.io API client.
Free tier: 25 searches/month — use sparingly.
Only call email-finder for the highest-priority leads.
"""

import logging
from typing import Optional
from urllib.parse import urlparse

import httpx

from config.settings import HUNTER_API_KEY

log = logging.getLogger(__name__)

_BASE = "https://api.hunter.io/v2"
_TIMEOUT = 15


class HunterClient:
    def __init__(self):
        self._key = HUNTER_API_KEY
        self._credits_used = 0
        self._quota_exhausted = False  # set True on first 429 — skip all further calls

    @property
    def credits_used(self) -> int:
        return self._credits_used

    async def find_email(
        self,
        domain: str,
        first_name: str,
        last_name: str,
    ) -> dict:
        """
        Find email for a person at a company domain.
        Returns dict with: email, score, sources, credits_used.
        """
        if not self._key or self._quota_exhausted:
            return {"email": None, "score": 0, "credits_used": 0}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                resp = await client.get(
                    f"{_BASE}/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first_name,
                        "last_name": last_name,
                        "api_key": self._key,
                    },
                )
                if resp.status_code == 429:
                    log.warning("[hunter] Rate limit hit — skipping remaining enrichment this run")
                    self._quota_exhausted = True
                    return {"email": None, "score": 0, "credits_used": 0}
                resp.raise_for_status()
                data = resp.json().get("data", {})
                email = data.get("email")
                score = data.get("score", 0)
                self._credits_used += 1
                return {"email": email, "score": score, "credits_used": 1}
            except Exception as e:
                log.debug(f"[hunter] email-finder error: {e}")
                return {"email": None, "score": 0, "credits_used": 0}

    async def domain_search(self, domain: str, seniority: str = "senior,executive") -> dict:
        """
        Find people at a domain. Returns list of contacts with titles.
        Useful to discover executive names before targeting email-finder.
        """
        if not self._key or self._quota_exhausted:
            return {"emails": []}

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            try:
                resp = await client.get(
                    f"{_BASE}/domain-search",
                    params={
                        "domain": domain,
                        "seniority": seniority,
                        "department": "management",
                        "api_key": self._key,
                        "limit": 10,
                    },
                )
                if resp.status_code == 429:
                    log.warning("[hunter] Rate limit hit — skipping remaining enrichment this run")
                    self._quota_exhausted = True
                    return {"emails": []}
                resp.raise_for_status()
                data = resp.json().get("data", {})
                self._credits_used += 1
                return {"emails": data.get("emails", [])}
            except Exception as e:
                log.debug(f"[hunter] domain-search error: {e}")
                return {"emails": []}


def extract_domain(company_url_or_name: str) -> Optional[str]:
    """Extract root domain from a URL, or return None."""
    if not company_url_or_name:
        return None
    if "." in company_url_or_name and not " " in company_url_or_name:
        parsed = urlparse(company_url_or_name if "://" in company_url_or_name else f"https://{company_url_or_name}")
        host = parsed.netloc or parsed.path
        # Strip www
        return host.lstrip("www.").split("/")[0]
    return None


def guess_email(first: str, last: str, domain: str) -> tuple[str, int]:
    """
    Guess the most likely email format based on common patterns.
    Returns (email, confidence_score).
    Common patterns:
      firstname.lastname@  → most common (~55%)
      firstnamelastname@   → ~20%
      firstname@           → ~15%
      f.lastname@          → ~10%
    """
    if not all([first, last, domain]):
        return "", 0

    f = first.lower().strip()
    l = last.lower().strip()
    # Most likely pattern
    email = f"{f}.{l}@{domain}"
    return email, 40  # 40% confidence — just a guess
