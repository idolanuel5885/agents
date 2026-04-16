"""Filter: location must be US-remote or one of the allowed cities."""

from config.locations import ALLOWED_CITIES, REMOTE_INDICATORS, NON_US_REMOTE_BLOCKLIST


def passes_location_filter(location: str, is_remote: bool) -> tuple[bool, str]:
    """Return (passed, reason)."""
    loc_lower = (location or "").lower().strip()

    # Check non-US remote blocklist first
    for blocked in NON_US_REMOTE_BLOCKLIST:
        if blocked in loc_lower:
            return False, f"non-US remote: '{location}'"

    # If marked remote by scraper and no blocking indicators
    if is_remote:
        # Still check it's not explicitly non-US
        return True, ""

    # Check remote indicators in location string
    for indicator in REMOTE_INDICATORS:
        if indicator in loc_lower:
            return True, ""

    # Check specific allowed cities
    for city in ALLOWED_CITIES:
        if city.name.lower() in loc_lower or any(alias in loc_lower for alias in city.aliases):
            return True, ""

    if not loc_lower:
        # No location info — include it for manual review
        return True, ""

    return False, f"location '{location}' not in allowed list"
