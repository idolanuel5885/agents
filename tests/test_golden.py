"""Golden-file tests for the report generator.

Generates the three demo reports and hashes their *text content* (not the
binary docx, which embeds timestamps and other non-deterministic bytes).

If a hash mismatches, the test will print the first differing line so the
diff is easy to inspect. To intentionally update the goldens, run:

    UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

import pytest
from docx import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from real_estate.demo_data import (  # noqa: E402
    sample_market, sample_standard19, sample_evacuation,
)
from real_estate.report_generator import generate_report_bytes  # noqa: E402


GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden.json")

DEMOS = {
    "market": sample_market,
    "standard19": sample_standard19,
    "evacuation": sample_evacuation,
}


def _doc_to_text(doc_bytes: bytes) -> str:
    """Extract every paragraph and table-cell line from the docx, in order."""
    doc = Document(io.BytesIO(doc_bytes))
    lines: list[str] = []

    def walk(parent):
        # python-docx exposes paragraphs and tables in document order via
        # body.element children, but a flat traversal of doc.paragraphs +
        # doc.tables suffices for our generator (which never nests tables).
        for para in parent.paragraphs:
            lines.append(para.text)
        for table in parent.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        lines.append(para.text)

    walk(doc)
    return "\n".join(lines)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_golden() -> dict:
    if not os.path.exists(GOLDEN_PATH):
        return {}
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_golden(golden: dict) -> None:
    with open(GOLDEN_PATH, "w", encoding="utf-8") as f:
        json.dump(golden, f, ensure_ascii=False, indent=2, sort_keys=True)


@pytest.mark.parametrize("name", list(DEMOS.keys()))
def test_golden(name: str) -> None:
    text = _doc_to_text(generate_report_bytes(DEMOS[name]()))
    actual = _hash(text)

    golden = _load_golden()

    if os.environ.get("UPDATE_GOLDEN") == "1":
        golden[name] = {"hash": actual, "lines": len(text.splitlines())}
        _save_golden(golden)
        return

    expected = golden.get(name, {}).get("hash")
    if expected is None:
        pytest.fail(
            f"no golden recorded for '{name}'. "
            f"Run with UPDATE_GOLDEN=1 to record."
        )
    if actual != expected:
        # Try to surface the first differing line vs. a sidecar text file.
        sidecar = os.path.join(os.path.dirname(__file__), f"golden_{name}.txt")
        if os.path.exists(sidecar):
            with open(sidecar, "r", encoding="utf-8") as f:
                expected_text = f.read()
            actual_lines = text.splitlines()
            expected_lines = expected_text.splitlines()
            for i, (a, b) in enumerate(zip(actual_lines, expected_lines)):
                if a != b:
                    pytest.fail(
                        f"hash mismatch for '{name}'. "
                        f"First diff at line {i}:\n"
                        f"  expected: {b!r}\n"
                        f"  actual:   {a!r}"
                    )
            if len(actual_lines) != len(expected_lines):
                pytest.fail(
                    f"hash mismatch for '{name}': "
                    f"line count {len(actual_lines)} vs {len(expected_lines)}"
                )
        pytest.fail(
            f"hash mismatch for '{name}': {actual} != {expected}. "
            f"Re-run with UPDATE_GOLDEN=1 to update."
        )


@pytest.mark.parametrize("name", list(DEMOS.keys()))
def test_text_sidecar(name: str) -> None:
    """Keep a human-readable sidecar of the text for diff debugging."""
    text = _doc_to_text(generate_report_bytes(DEMOS[name]()))
    sidecar = os.path.join(os.path.dirname(__file__), f"golden_{name}.txt")

    if os.environ.get("UPDATE_GOLDEN") == "1" or not os.path.exists(sidecar):
        with open(sidecar, "w", encoding="utf-8") as f:
            f.write(text)
        return

    with open(sidecar, "r", encoding="utf-8") as f:
        expected = f.read()
    if text != expected:
        # Hash test will produce the actionable failure; just mark as failing.
        pytest.fail(f"text mismatch for '{name}' — see hash test for diff")
