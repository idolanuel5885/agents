"""Integration tests for ``real_estate.claude_descriptions``.

These are *real* API calls — not mocked. The whole module is skipped when
``ANTHROPIC_API_KEY`` is not set, so CI without the key (or contributors
without one) won't be blocked.
"""
from __future__ import annotations

import os
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


# Quantitative tokens we expect Claude *not* to emit, given the system prompt.
# A description containing any of these would suggest it leaked numerics.
_FORBIDDEN_DIGITS = "0123456789"


def _looks_qualitative(text: str) -> bool:
    """Return True if the description appears to contain no quantitative claims.

    The system prompt forbids any digit-bearing factual claims because the
    tool has no web access to cite a source. A bare digit anywhere in the
    paragraph is a strong signal the rule was broken.
    """
    return not any(ch in _FORBIDDEN_DIGITS for ch in text)


@pytest.mark.parametrize("city", ["תל אביב", "ירושלים", "רמת גן"])
def test_describe_city_returns_nonempty_paragraph(city: str) -> None:
    text = claude_descriptions.describe_city(city)
    assert isinstance(text, str)
    assert text.strip(), "expected non-empty description"
    # One paragraph: should not contain newlines beyond trimming.
    assert text.count("\n") <= 1, f"expected single paragraph, got:\n{text}"


@pytest.mark.parametrize(
    "city,neighborhood",
    [
        ("תל אביב", "רמת אביב"),
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


def test_describe_city_avoids_quantitative_claims() -> None:
    """Spot-check that the system prompt suppresses digits in the output.

    This is a heuristic — Claude could in theory cite a year qualitatively
    ("בשנות החמישים") without digits. If this test starts flaking on a
    legitimate output, relax it; do not relax the system prompt.
    """
    text = claude_descriptions.describe_city("חיפה")
    assert _looks_qualitative(text), (
        f"description appears to contain quantitative claims:\n{text}"
    )


def test_with_footnote_appends_source_marker() -> None:
    out = claude_descriptions.with_footnote("פסקה לדוגמה.")
    assert claude_descriptions.SOURCE_FOOTNOTE in out
    assert out.startswith("פסקה לדוגמה.")
