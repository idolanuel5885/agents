"""Filter: job must have been posted within the last DAYS_POSTED_MAX days."""

from datetime import datetime, timezone, timedelta
from config.settings import DAYS_POSTED_MAX


def passes_date_filter(date_posted: str, first_seen: str = "") -> tuple[bool, str]:
    """Return (passed, reason)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_POSTED_MAX)

    date_str = date_posted or first_seen
    if not date_str:
        # No date info — include conservatively
        return True, ""

    try:
        # Parse various date formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(date_str[:19], fmt.replace("%z", ""))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    return True, ""
                return False, f"posted {date_str} is older than {DAYS_POSTED_MAX} days"
            except ValueError:
                continue
    except Exception:
        pass

    # Could not parse — include conservatively
    return True, ""


def is_approaching_stale(date_posted: str, warn_days: int = 21) -> bool:
    """Return True if the posting is over warn_days old (flag for user attention)."""
    if not date_posted:
        return False
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=warn_days)
        dt = datetime.strptime(date_posted[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt < cutoff
    except Exception:
        return False
