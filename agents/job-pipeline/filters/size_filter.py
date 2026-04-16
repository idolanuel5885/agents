"""Filter: company size must be between COMPANY_SIZE_MIN and COMPANY_SIZE_MAX."""

import re
from typing import Optional
from config.settings import COMPANY_SIZE_MIN, COMPANY_SIZE_MAX


def passes_size_filter(
    size_resolved: Optional[int],
    size_raw: str = "",
) -> tuple[bool, str]:
    """
    Return (passed, reason).
    If size_resolved is None and size_raw is unparseable, return (True, 'deferred')
    so the job stays in for enrichment, which may resolve the size later.
    """
    if size_resolved is not None:
        if COMPANY_SIZE_MIN <= size_resolved <= COMPANY_SIZE_MAX:
            return True, ""
        return False, f"company size {size_resolved} outside {COMPANY_SIZE_MIN}-{COMPANY_SIZE_MAX}"

    # Try to parse size_raw (e.g. "201-500", "500 employees", "51-200 employees")
    parsed = _parse_size_range(size_raw)
    if parsed is not None:
        low, high = parsed
        midpoint = (low + high) // 2
        if COMPANY_SIZE_MIN <= midpoint <= COMPANY_SIZE_MAX:
            return True, ""
        # If range clearly falls outside (even high end < min or low end > max)
        if high < COMPANY_SIZE_MIN or low > COMPANY_SIZE_MAX:
            return False, f"size range '{size_raw}' outside {COMPANY_SIZE_MIN}-{COMPANY_SIZE_MAX}"

    # Can't determine size — defer (pass, will re-check after enrichment)
    return True, "size unknown — deferred"


def _parse_size_range(raw: str) -> Optional[tuple[int, int]]:
    """Parse strings like '201-500', '51-200 employees', '500+'."""
    if not raw:
        return None
    raw = raw.strip().lower().replace(",", "")

    # Range: "201-500" or "201 to 500"
    m = re.search(r"(\d+)\s*[-–to]+\s*(\d+)", raw)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Single number
    m = re.search(r"(\d+)\+?", raw)
    if m:
        n = int(m.group(1))
        return n, n

    return None
