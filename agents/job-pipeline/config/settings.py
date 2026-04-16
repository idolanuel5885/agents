import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _get_int(key: str, default: int = 0) -> int:
    val = os.getenv(key)
    return int(val) if val else default


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, "").lower()
    return val in ("1", "true", "yes") if val else default


# ── Google Sheets ────────────────────────────────────────────────────────────
GOOGLE_SERVICE_ACCOUNT_JSON: str = _get(
    "GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials/google_service_account.json"
)
GOOGLE_SHEET_ID: str = _get("GOOGLE_SHEET_ID")

# ── Enrichment APIs ──────────────────────────────────────────────────────────
HUNTER_API_KEY: str = _get("HUNTER_API_KEY")

# ── Proxy ────────────────────────────────────────────────────────────────────
SCRAPER_PROXY: str = _get("SCRAPER_PROXY")

# ── Playwright ───────────────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS: bool = _get_bool("PLAYWRIGHT_HEADLESS", default=True)
PLAYWRIGHT_SLOW_MO: int = _get_int("PLAYWRIGHT_SLOW_MO", default=100)

# ── Pipeline ─────────────────────────────────────────────────────────────────
MAX_CONCURRENT_SCRAPERS: int = _get_int("MAX_CONCURRENT_SCRAPERS", default=5)
MAX_CONCURRENT_PLAYWRIGHT: int = _get_int("MAX_CONCURRENT_PLAYWRIGHT", default=2)
DAYS_BEFORE_MARK_CLOSED: int = _get_int("DAYS_BEFORE_MARK_CLOSED", default=3)
EMAIL_MIN_CONFIDENCE: int = _get_int("EMAIL_MIN_CONFIDENCE", default=50)
DRY_RUN: bool = _get_bool("DRY_RUN", default=False)
DB_PATH: str = _get("DB_PATH", str(_ROOT / "pipeline.db"))

# ── Job search parameters ─────────────────────────────────────────────────────
DAYS_POSTED_MAX: int = 30
COMPANY_SIZE_MIN: int = 50
COMPANY_SIZE_MAX: int = 1000
