"""Filter: exclude AI-native companies whose core product is an AI model/platform."""

from config.exclusions import AI_NATIVE_COMPANIES


def passes_company_filter(company_name: str) -> tuple[bool, str]:
    """Return (passed, reason). Excludes AI-native companies."""
    if not company_name:
        return True, ""

    company_lower = company_name.lower().strip()

    for blocked in AI_NATIVE_COMPANIES:
        if blocked in company_lower or company_lower in blocked:
            return False, f"AI-native company: '{company_name}'"

    return True, ""
