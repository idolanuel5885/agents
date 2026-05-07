"""Auto-fill qualitative city/neighborhood descriptions via the Claude API.

Two public functions, ``describe_city`` and ``describe_neighborhood``, return
a single short Hebrew paragraph each. They are called from the Web form
handler when the appraiser leaves the description fields empty.

Hard rules enforced via the system prompt (see CLAUDE.md A.3 and
``skills/03_description.md`` "תיאור עיר — כללים מעודכנים"):

* Qualitative description only. No quantitative claims of any kind
  (population, percentages, prices, growth rates, demographics).
* Formal Hebrew, third person, neutral tone — no laudatory adjectives.
* One paragraph, 3-4 sentences.

The model used is Claude Haiku 4.5 — the task is small and per-call
latency matters more than capability. Failures (network, missing key,
quota) are signalled by raising ``DescriptionUnavailable``; the Web
handler catches that and falls back to the existing "יש להשלים"
placeholder so report generation never blocks on the API.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 400

# Per CLAUDE.md A.7: auto-filled sections must be presented to the appraiser
# with their source visible. The Web handler appends this sentence to any
# description it filled via the API so the appraiser can verify it.
SOURCE_FOOTNOTE = "תיאור זה נוצר אוטומטית ויש לאמת מול מקורות סמכותיים."


def with_footnote(text: str) -> str:
    """Append the auto-generation source footnote to ``text``."""
    text = (text or "").rstrip()
    if not text:
        return text
    return f"{text} ({SOURCE_FOOTNOTE})"

_SYSTEM_PROMPT = (
    "אתה עוזר לשמאי מקרקעין בישראל בכתיבת תיאור איכותני קצר של מיקום עבור "
    "דוח שמאות בעברית רשמית.\n\n"
    "כללים מחייבים (מתוך 03_description.md, סעיף 'תיאור עיר — כללים מעודכנים'):\n"
    "1. כתוב פסקה אחת בלבד, 3-4 משפטים.\n"
    "2. עברית רשמית בגוף שלישי. ללא שימוש בגוף ראשון, ללא לשון מדוברת.\n"
    "3. תיאור איכותני בלבד: מיקום גיאוגרפי, אופי כללי, אופי הבנייה הדומיננטי, "
    "ונגישות תחבורתית.\n"
    "4. אסור בהחלט לכלול נתונים כמותיים מכל סוג: מספר תושבים, אחוזים, "
    "מחירים ממוצעים, נתונים דמוגרפיים, קצב גידול, מרחקים במספרים, שנים מספריות "
    "כקביעה עובדתית, או כל מספר שאינו מצוטט ממקור סמכותי. הכלי הזה אינו מבצע "
    "חיפוש ברשת ולכן אין לך מקור סמכותי לצטט. אם אתה לא בטוח אם משהו הוא נתון "
    "כמותי, השמט אותו.\n"
    "5. הימנע מלשון משבחת או שיווקית (\"מרשים\", \"יפהפה\", \"מבוקש\", "
    "\"איכותי\"). שפת השמאות נייטרלית ועובדתית.\n"
    "6. אל תתחיל את הפסקה בכותרת או בשם המקום בנפרד — כתוב פסקה רציפה.\n"
    "7. החזר את הפסקה בלבד, ללא הקדמות, ללא הסברים, ללא הערות שוליים."
)


class DescriptionUnavailable(RuntimeError):
    """Raised when the Claude API call cannot complete."""


def _client():
    try:
        import anthropic
    except ImportError as e:
        raise DescriptionUnavailable(f"anthropic package not installed: {e}") from e
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise DescriptionUnavailable("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic()


def _generate(user_prompt: str) -> str:
    try:
        client = _client()
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except DescriptionUnavailable:
        raise
    except Exception as e:
        raise DescriptionUnavailable(f"Claude API call failed: {e}") from e

    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    text = "".join(parts).strip()
    if not text:
        raise DescriptionUnavailable("Claude returned an empty response")
    return text


def describe_city(city_name: str) -> str:
    """Return a single Hebrew paragraph describing the given city qualitatively."""
    name = (city_name or "").strip()
    if not name:
        raise DescriptionUnavailable("city_name is empty")
    prompt = (
        f"כתוב פסקה אחת בעברית רשמית המתארת את העיר {name} מבחינה איכותנית: "
        f"מיקום גיאוגרפי, אופי כללי, אופי הבנייה הדומיננטי, ונגישות תחבורתית. "
        f"הקפד על איסור הנתונים הכמותיים שצוין בהוראות המערכת."
    )
    return _generate(prompt)


def describe_neighborhood(city_name: str, neighborhood_name: str) -> str:
    """Return a single Hebrew paragraph describing the given neighborhood."""
    city = (city_name or "").strip()
    nbhd = (neighborhood_name or "").strip()
    if not nbhd:
        raise DescriptionUnavailable("neighborhood_name is empty")
    prompt = (
        f"כתוב פסקה אחת בעברית רשמית המתארת את שכונת {nbhd} שבעיר {city} "
        f"מבחינה איכותנית: מיקום השכונה בעיר, אופי הבנייה הדומיננטי "
        f"(ותיקה/חדשה/מעורבת), ומה אופייה הכללי. הקפד על איסור הנתונים "
        f"הכמותיים שצוין בהוראות המערכת."
    )
    return _generate(prompt)


def try_describe_city(city_name: str) -> Optional[str]:
    """Like ``describe_city`` but returns ``None`` on failure (logged)."""
    try:
        return describe_city(city_name)
    except DescriptionUnavailable as e:
        logger.warning("describe_city(%r) failed: %s", city_name, e)
        return None


def try_describe_neighborhood(city_name: str, neighborhood_name: str) -> Optional[str]:
    """Like ``describe_neighborhood`` but returns ``None`` on failure (logged)."""
    try:
        return describe_neighborhood(city_name, neighborhood_name)
    except DescriptionUnavailable as e:
        logger.warning(
            "describe_neighborhood(%r, %r) failed: %s",
            city_name, neighborhood_name, e,
        )
        return None
