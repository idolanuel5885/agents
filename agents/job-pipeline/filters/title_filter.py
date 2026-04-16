"""Filter: job title must match one of our target titles."""

import re

from config.job_titles import TARGET_TITLES, TITLE_INCLUDE_KEYWORDS, TITLE_FUZZY_THRESHOLD

# "AI" must appear as a standalone word, or "artificial intelligence" must appear.
_AI_WORD = re.compile(r'\bai\b', re.IGNORECASE)


def passes_title_filter(title: str) -> tuple[bool, str]:
    """Return (passed, reason)."""
    if not title:
        return False, "empty title"

    title_lower = title.lower()

    # Fast path: substring match on key phrases (all already contain AI keywords)
    for kw in TITLE_INCLUDE_KEYWORDS:
        if kw in title_lower:
            return True, ""

    # Fuzzy match — only consider titles that explicitly mention AI or Artificial Intelligence.
    # This prevents partial token overlap (e.g. "VP of Stop-Loss") from scoring well against
    # "VP of AI" via WRatio.
    if not _AI_WORD.search(title) and "artificial intelligence" not in title_lower:
        return False, f"title '{title}' does not match target roles"

    try:
        from rapidfuzz import process, fuzz
        result = process.extractOne(
            title,
            TARGET_TITLES,
            scorer=fuzz.WRatio,
        )
        if result and result[1] >= TITLE_FUZZY_THRESHOLD:
            return True, ""
    except ImportError:
        for target in TARGET_TITLES:
            if target.lower() in title_lower or title_lower in target.lower():
                return True, ""

    return False, f"title '{title}' does not match target roles"
