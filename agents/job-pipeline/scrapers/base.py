"""Base scraper contract that every scraper must implement."""

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawJob:
    """Normalised job record returned by every scraper."""
    title: str
    company: str
    apply_url: str
    source: str                          # scraper name
    location: str = ""
    is_remote: bool = False
    date_posted: str = ""                # ISO 8601 date string or empty
    salary_raw: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    company_size_raw: str = ""
    description_raw: str = ""
    extra: dict = field(default_factory=dict)  # scraper-specific extras

    @property
    def id(self) -> str:
        """Stable unique ID: SHA256 of (company + title + url), all lowercased."""
        key = f"{self.company.lower().strip()}|{self.title.lower().strip()}|{self.apply_url.lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def to_db_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "apply_url": self.apply_url,
            "source": self.source,
            "location": self.location,
            "is_remote": self.is_remote,
            "date_posted": self.date_posted,
            "salary_raw": self.salary_raw,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "company_size_raw": self.company_size_raw,
            "description_raw": self.description_raw[:4000] if self.description_raw else "",
        }


class BaseScraper(ABC):
    """Abstract base class for all job board scrapers."""

    name: str = "unknown"

    @abstractmethod
    async def scrape(self) -> list[RawJob]:
        """Fetch jobs and return a list of RawJob objects.

        Must not raise — catch all exceptions internally and return an
        empty list (the orchestrator logs the failure from the exception).
        Raise ScraperError only for unrecoverable config issues.
        """
        ...

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def parse_salary(text: str) -> tuple[Optional[int], Optional[int]]:
        """Extract min/max integers from salary strings like '$120k-$180k'."""
        if not text:
            return None, None
        # Normalise: remove $, commas, whitespace
        text = re.sub(r"[$,\s]", "", text.lower())
        # Handle k suffix
        text = re.sub(r"(\d+)k", lambda m: str(int(m.group(1)) * 1000), text)
        nums = re.findall(r"\d{4,7}", text)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        elif len(nums) == 1:
            return int(nums[0]), None
        return None, None

    @staticmethod
    def clean_company_name(name: str) -> str:
        """Strip common legal suffixes and extra whitespace."""
        suffixes = [
            ", Inc.", " Inc.", " Inc", ", LLC", " LLC",
            ", Ltd.", " Ltd.", " Ltd", " Corp.", " Corp",
            ", Co.", " Co.", " GmbH",
        ]
        for s in suffixes:
            name = name.replace(s, "")
        return name.strip()


class ScraperError(Exception):
    pass
