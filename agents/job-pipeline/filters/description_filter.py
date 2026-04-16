"""Filter: exclude jobs whose description mentions hands-on technical keywords."""

from config.exclusions import EXCLUSION_KEYWORDS


def passes_description_filter(description: str) -> tuple[bool, str]:
    """Return (passed, reason). Any exclusion keyword match → fail."""
    if not description:
        # No description available — pass (can't filter what we can't read)
        return True, ""

    desc_lower = description.lower()

    for kw in EXCLUSION_KEYWORDS:
        if kw in desc_lower:
            return False, f"exclusion keyword found: '{kw}'"

    return True, ""
