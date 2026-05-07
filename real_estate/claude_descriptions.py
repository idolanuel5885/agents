"""Auto-fill qualitative city/neighborhood descriptions via the Claude API.

Two public functions, ``describe_city`` and ``describe_neighborhood``, return
a single short Hebrew paragraph each. They are called from the Web form
handler when the appraiser leaves the description fields empty.

This is the v2 implementation. Differences from v1:

* Model upgraded from Claude Haiku 4.5 to Claude Sonnet 4.6 — Haiku produced
  Hebrew with grammatical errors and occasional language mixing (Arabic
  fragments) that is unacceptable in a signed appraisal report.
* The Anthropic server-side ``web_search`` tool is enabled so Claude can
  ground its description in real information about the specific
  city/neighborhood before writing. Without search the model falls back
  to generic, undifferentiated descriptions.
* When search returns no specific information about the requested place
  the model is instructed to return the sentinel string
  ``INSUFFICIENT_INFO``. The wrapper translates that into ``None`` so
  the Web handler keeps its existing "יש להשלים" placeholder, per A.7
  ("a placeholder is better than a wrong description").

Hard rules enforced via the system prompt (see CLAUDE.md A.3 and
``skills/03_description.md`` "תיאור עיר — כללים מעודכנים"):

* Hebrew only. No Arabic, no transliterations, no English glosses.
* Formal Hebrew, third person, neutral tone.
* One paragraph, 3-4 sentences.
* Quantitative claims are allowed only if cited inline from an
  authoritative source surfaced by the search (CBS / municipal site /
  official statistics).

Failures (network, missing key, quota) are signalled by raising
``DescriptionUnavailable``; the Web handler catches that and falls back
to the existing "יש להשלים" placeholder so report generation never
blocks on the API.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Latest Sonnet at time of writing (verified against
# https://platform.claude.com/docs/en/about-claude/models/overview).
_MODEL = "claude-sonnet-4-6"

# Built-in Anthropic server-side web search tool. Documented at
# https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
# Using the basic version (no code-execution dependency); 5 searches is
# more than enough for one city + one neighborhood.
#
# Note on user_location: the API rejects ``country: "IL"`` ("Country code
# IL is not supported"), so we omit user_location entirely. The Hebrew
# system prompt and the literal "בישראל" / city name in the user prompt
# already steer searches to Israeli sources.
_WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 5,
}

# Generous output budget — the agentic loop needs room for tool calls and
# results before the final paragraph; the paragraph itself is short.
_MAX_TOKENS = 2048

# Sentinel returned by the model when web search did not surface
# specific information about the requested place.
INSUFFICIENT_INFO = "INSUFFICIENT_INFO"

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
    "דוח שמאות בעברית רשמית. בדוח רשמי בעברית; כל סטייה בלשון פוסלת את "
    "הפסקה.\n\n"
    "שלב חיפוש (חובה לפני הכתיבה):\n"
    "השתמש בכלי web_search כדי לאסוף מידע ספציפי על המקום המבוקש: מיקומו "
    "המדויק, גבולות, אופי הבנייה הדומיננטי, תקופת בנייה כללית, אופי "
    "השכונות הסמוכות (אם רלוונטי), ושירותים ותשתיות אופייניים. בצע "
    "1-3 חיפושים לפי הצורך. אם הביצוע הראשון לא החזיר מידע ספציפי, נסה "
    "ניסוח אחר.\n\n"
    "כלל חוסר מידע:\n"
    "אם לאחר החיפוש לא מצאת מידע ספציפי לגבי המקום שנשאלת עליו (למשל "
    "שכונה קטנה שאינה מתועדת באינטרנט), אל תכתוב תיאור גנרי. במקום זה "
    f"החזר אך ורק את המחרוזת '{INSUFFICIENT_INFO}' — בלי שום טקסט נוסף, "
    "בלי הסבר, בלי פסקה. עדיף שהשמאי יקבל הודעת 'יש להשלים' מאשר תיאור "
    "כללי שעשוי להיות שגוי.\n\n"
    "כללי כתיבה (כשיש מספיק מידע):\n"
    "1. פסקה אחת בלבד, 3-4 משפטים.\n"
    "2. עברית רשמית בלבד, גוף שלישי. אסור בהחלט לערבב שפות אחרות (ערבית, "
    "אנגלית, תעתיקים) בתוך הפסקה. שמות לועזיים אם נדרשים — בתעתיק עברי "
    "בלבד. אסור להשתמש באותיות שאינן עברית או לטינית.\n"
    "3. אסור לשון מדוברת, אסור גוף ראשון.\n"
    "4. תיאור איכותני: מיקום בעיר/אזור, אופי הבנייה הדומיננטי "
    "(ותיקה/חדשה/מעורבת/לשימור), אופי כללי, ונגישות תחבורתית.\n"
    "5. נתונים כמותיים (אחוזים, מספרי תושבים, מחירים, שנים מספריות "
    "כקביעה) מותרים אך ורק כאשר מצאת אותם בחיפוש ואתה מצטט מקור סמכותי "
    "בגוף הפסקה (למשל 'על פי נתוני הלמ\"ס' או 'על פי אתר העירייה'). "
    "אם אין מקור — השמט את המספר או החלף בתיאור איכותני.\n"
    "6. הימנע מלשון משבחת או שיווקית ('מרשים', 'יפהפה', 'מבוקש', "
    "'איכותי'). שפת השמאות נייטרלית ועובדתית.\n"
    "7. אל תתחיל את הפסקה בכותרת או בשם המקום בנפרד — פסקה רציפה.\n"
    "8. החזר את הפסקה בלבד, ללא הקדמות, ללא הסברים, ללא הערות שוליים, "
    "ללא רשימת מקורות בסוף.\n"
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


def _extract_text(message) -> str:
    """Concatenate the final text content blocks from a Messages response.

    With the server-side web_search tool the response can contain
    interleaved ``text``, ``server_tool_use`` and
    ``web_search_tool_result`` blocks. We want the model's natural-language
    output only, joined with single spaces.
    """
    parts = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            t = (block.text or "").strip()
            if t:
                parts.append(t)
    return " ".join(parts).strip()


def _generate(user_prompt: str) -> str:
    try:
        client = _client()
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            tools=[_WEB_SEARCH_TOOL],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except DescriptionUnavailable:
        raise
    except Exception as e:
        raise DescriptionUnavailable(f"Claude API call failed: {e}") from e

    text = _extract_text(message)
    if not text:
        raise DescriptionUnavailable("Claude returned an empty response")
    return text


def describe_city(city_name: str) -> str:
    """Return a single Hebrew paragraph describing the given city qualitatively.

    Returns the special string ``INSUFFICIENT_INFO`` when web search did
    not surface specific information about the city. Use
    :func:`try_describe_city` to map that case to ``None``.
    """
    name = (city_name or "").strip()
    if not name:
        raise DescriptionUnavailable("city_name is empty")
    prompt = (
        f"חפש ברשת מידע על העיר {name} בישראל וכתוב פסקה אחת המתארת אותה "
        f"לפי הכללים שבהוראות המערכת. אם לא מצאת מידע ספציפי על העיר, "
        f"החזר {INSUFFICIENT_INFO}."
    )
    return _generate(prompt)


def describe_neighborhood(city_name: str, neighborhood_name: str) -> str:
    """Return a single Hebrew paragraph describing the given neighborhood.

    Returns the special string ``INSUFFICIENT_INFO`` when web search did
    not surface specific information about the neighborhood. Use
    :func:`try_describe_neighborhood` to map that case to ``None``.
    """
    city = (city_name or "").strip()
    nbhd = (neighborhood_name or "").strip()
    if not nbhd:
        raise DescriptionUnavailable("neighborhood_name is empty")
    prompt = (
        f"חפש ברשת מידע על שכונת {nbhd} שבעיר {city} וכתוב פסקה אחת "
        f"המתארת אותה לפי הכללים שבהוראות המערכת. הקפד שהפסקה מתייחסת "
        f"באופן ספציפי לשכונה זו ולא כתיאור גנרי שמתאים לכל שכונה. "
        f"אם החיפוש לא החזיר מידע ספציפי על שכונה זו דווקא, "
        f"החזר {INSUFFICIENT_INFO}."
    )
    return _generate(prompt)


def _is_insufficient(text: str) -> bool:
    """True if the model returned the INSUFFICIENT_INFO sentinel."""
    return INSUFFICIENT_INFO in (text or "")


def try_describe_city(city_name: str) -> Optional[str]:
    """Like ``describe_city`` but returns ``None`` on failure or when the
    model signalled INSUFFICIENT_INFO. Failures are logged.
    """
    try:
        result = describe_city(city_name)
    except DescriptionUnavailable as e:
        logger.warning("describe_city(%r) failed: %s", city_name, e)
        return None
    if _is_insufficient(result):
        logger.info("describe_city(%r): model returned INSUFFICIENT_INFO", city_name)
        return None
    return result


def try_describe_neighborhood(city_name: str, neighborhood_name: str) -> Optional[str]:
    """Like ``describe_neighborhood`` but returns ``None`` on failure or
    when the model signalled INSUFFICIENT_INFO. Failures are logged.
    """
    try:
        result = describe_neighborhood(city_name, neighborhood_name)
    except DescriptionUnavailable as e:
        logger.warning(
            "describe_neighborhood(%r, %r) failed: %s",
            city_name, neighborhood_name, e,
        )
        return None
    if _is_insufficient(result):
        logger.info(
            "describe_neighborhood(%r, %r): model returned INSUFFICIENT_INFO",
            city_name, neighborhood_name,
        )
        return None
    return result
