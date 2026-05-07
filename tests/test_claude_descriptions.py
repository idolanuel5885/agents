"""Integration tests for ``real_estate.claude_descriptions`` (v2: with web search).

These are *real* API calls — not mocked. The whole module is skipped when
``ANTHROPIC_API_KEY`` is not set, so CI without the key (or contributors
without one) won't be blocked.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set; skipping live Claude integration tests",
)

from real_estate import claude_descriptions  # noqa: E402


# ── Language purity helpers ───────────────────────────────────────────────────
#
# We require Hebrew-only output. The acceptable Unicode set is:
#   * Hebrew block               U+0590..U+05FF
#   * ASCII letters and digits   (allowed for citation source names like
#                                 "CBS" or years; rare and intentionally
#                                 not blocked)
#   * Whitespace and punctuation (Latin and Hebrew geresh/gershayim)
#
# We explicitly reject:
#   * Arabic                     U+0600..U+06FF, U+0750..U+077F
#   * CJK (Chinese/Japanese/Korean) U+3000..U+9FFF, U+3400..U+4DBF, etc.
#   * Cyrillic                   U+0400..U+04FF
#   * Devanagari                 U+0900..U+097F

def _find_foreign_chars(text: str) -> list[str]:
    """Return a list of disallowed non-Hebrew, non-Latin characters in ``text``."""
    bad = []
    for ch in text:
        cp = ord(ch)
        if cp < 0x80:
            continue  # ASCII
        if 0x0590 <= cp <= 0x05FF:
            continue  # Hebrew
        if cp in (0x200E, 0x200F, 0x00A0, 0x2013, 0x2014, 0x2018, 0x2019,
                  0x201C, 0x201D, 0x20AA):
            continue  # bidi marks, nbsp, dashes, smart quotes, shekel sign
        # Anything else outside Hebrew + ASCII + a few common puncts is foreign.
        bad.append(ch)
    return bad


def _has_hebrew(text: str) -> bool:
    return any(0x0590 <= ord(ch) <= 0x05FF for ch in text)


# ── Sanity tests for known places ─────────────────────────────────────────────


@pytest.mark.parametrize("city", ["תל אביב", "ירושלים", "רמת גן"])
def test_describe_city_returns_nonempty_paragraph(city: str) -> None:
    text = claude_descriptions.describe_city(city)
    assert isinstance(text, str)
    assert text.strip(), "expected non-empty description"
    assert text.strip() != claude_descriptions.INSUFFICIENT_INFO, (
        f"unexpected INSUFFICIENT_INFO for known city {city!r}"
    )


@pytest.mark.parametrize(
    "city,neighborhood",
    [
        ("תל אביב", "פלורנטין"),
        ("ירושלים", "רחביה"),
        ("רמת גן", "מרום נווה"),
    ],
)
def test_describe_neighborhood_returns_nonempty_paragraph(
    city: str, neighborhood: str
) -> None:
    text = claude_descriptions.describe_neighborhood(city, neighborhood)
    assert isinstance(text, str)
    assert text.strip(), "expected non-empty description"
    assert text.strip() != claude_descriptions.INSUFFICIENT_INFO, (
        f"unexpected INSUFFICIENT_INFO for known neighborhood "
        f"{neighborhood!r} in {city!r}"
    )


# ── Hebrew-only language check ────────────────────────────────────────────────


@pytest.mark.parametrize("city", ["תל אביב", "חיפה"])
def test_city_description_is_hebrew_only(city: str) -> None:
    text = claude_descriptions.describe_city(city)
    foreign = _find_foreign_chars(text)
    assert not foreign, (
        f"description contains foreign-script characters {sorted(set(foreign))!r}:\n"
        f"{text}"
    )
    assert _has_hebrew(text), f"description is missing Hebrew characters:\n{text}"


def test_neighborhood_description_is_hebrew_only() -> None:
    text = claude_descriptions.describe_neighborhood("תל אביב", "פלורנטין")
    foreign = _find_foreign_chars(text)
    assert not foreign, (
        f"description contains foreign-script characters {sorted(set(foreign))!r}:\n"
        f"{text}"
    )
    assert _has_hebrew(text), f"description is missing Hebrew characters:\n{text}"


# ── INSUFFICIENT_INFO behaviour for unknown places ────────────────────────────


def test_unknown_neighborhood_returns_insufficient_or_none() -> None:
    """For an obviously made-up neighborhood the model must not hallucinate."""
    name = "שכונה דמיונית 12345"
    raw = claude_descriptions.describe_neighborhood("תל אביב", name)
    # Either the raw call signals INSUFFICIENT_INFO directly...
    if raw.strip() == claude_descriptions.INSUFFICIENT_INFO:
        pass
    else:
        # ...or the model wrote something. In that case the wrapper
        # contract is what we really care about: try_* must return None
        # rather than a fabricated description.
        result = claude_descriptions.try_describe_neighborhood("תל אביב", name)
        assert result is None, (
            f"try_describe_neighborhood produced a description for a "
            f"made-up neighborhood instead of returning None:\n{result}"
        )

    # Wrapper-level guarantee: must be None for an unknown place.
    assert claude_descriptions.try_describe_neighborhood("תל אביב", name) is None


# ── Specificity check for a known neighborhood ────────────────────────────────


def test_known_neighborhood_description_mentions_the_neighborhood() -> None:
    """For a well-known neighborhood the description must reference it by name
    or by an unambiguous attribute, not be a generic 'this neighborhood' blob.
    """
    city, nbhd = "תל אביב", "פלורנטין"
    text = claude_descriptions.describe_neighborhood(city, nbhd)
    # Either the neighborhood name appears, or a clearly specific landmark
    # commonly associated with Florentin (we keep the list small to avoid
    # over-fitting to a particular phrasing).
    needles = [nbhd, "פלורנטין"]
    assert any(n in text for n in needles), (
        f"description does not reference {nbhd!r} specifically:\n{text}"
    )


# ── Footnote helper unchanged ─────────────────────────────────────────────────


def test_with_footnote_appends_source_marker() -> None:
    out = claude_descriptions.with_footnote("פסקה לדוגמה.")
    assert claude_descriptions.SOURCE_FOOTNOTE in out
    assert out.startswith("פסקה לדוגמה.")


# Silence an unused-import warning when re isn't referenced above on some paths.
_ = re
