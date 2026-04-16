"""
Lenny's Newsletter Job Board scraper.
jobs.lennysnewsletter.com and all known alternate domains are currently
unreachable (DNS failure). Scraper is disabled until a valid URL is found.
"""

import logging
from scrapers.base import BaseScraper, RawJob

log = logging.getLogger(__name__)


class LennysScraper(BaseScraper):
    name = "lennys"

    async def scrape(self) -> list[RawJob]:
        log.debug("[lennys] Board URL is unreachable — skipping")
        return []
