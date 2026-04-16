"""
Scraper registry — maps scraper names to classes.
The orchestrator imports this to build the active scraper list.
"""

from scrapers.jobspy_scraper import JobSpyScraper
from scrapers.greenhouse_scraper import GreenhouseScraper
from scrapers.lever_scraper import LeverScraper
from scrapers.ashby_scraper import AshbyScraper
from scrapers.himalayas_scraper import HimalayanScraper
from scrapers.builtin_scraper import BuiltinScraper
from scrapers.workatastartup_scraper import WorkAtAStartupScraper
from scrapers.getro_scraper import GetroScraper
from scrapers.vc_boards_scraper import VCBoardsScraper
from scrapers.playwright_scrapers.wellfound_scraper import WellfoundScraper
from scrapers.playwright_scrapers.remoterocketship_scraper import RemoteRocketshipScraper
from scrapers.playwright_scrapers.lennys_scraper import LennysScraper
from scrapers.playwright_scrapers.pallet_scraper import PalletScraper

# All scrapers that run by default.
# Playwright scrapers run in a separate, size-limited pool.
ALL_SCRAPERS = [
    JobSpyScraper,
    GreenhouseScraper,
    LeverScraper,
    AshbyScraper,
    HimalayanScraper,
    BuiltinScraper,
    WorkAtAStartupScraper,
    GetroScraper,
    VCBoardsScraper,
    WellfoundScraper,
    RemoteRocketshipScraper,
    LennysScraper,
    PalletScraper,
]

# Scrapers that require Playwright (browser automation)
PLAYWRIGHT_SCRAPERS = {
    WellfoundScraper,
    RemoteRocketshipScraper,
    LennysScraper,
    PalletScraper,
}

SCRAPER_BY_NAME: dict = {cls.name: cls for cls in ALL_SCRAPERS}


def get_scrapers(names: list[str] | None = None) -> list:
    """Return instantiated scraper objects. Pass names to run a subset."""
    if names:
        classes = [SCRAPER_BY_NAME[n] for n in names if n in SCRAPER_BY_NAME]
    else:
        classes = ALL_SCRAPERS
    return [cls() for cls in classes]
