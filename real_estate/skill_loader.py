"""Skill loader — loads marked snippets from skills/*.md files.

Snippets are HTML-comment-bracketed blocks inside the skill markdown:

    <!-- snippet: section_03.apt.opening -->
    <!-- character: variable -->
    נשוא חוות הדעת מהווה דירה בת {rooms} חדרים ...
    <!-- /snippet -->

The optional `<!-- character: ... -->` line declares the section character
(`fixed`, `semi`, or `variable`) per CLAUDE.md A.5.

Two public functions:
- ``get(snippet_id)`` returns the raw snippet text.
- ``render(snippet_id, **vars)`` formats the snippet with ``str.format``.
"""
from __future__ import annotations

import os
import re
from typing import Dict


_SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills")
_SKILLS_DIR = os.path.normpath(_SKILLS_DIR)

_SNIPPET_RE = re.compile(
    r"<!--\s*snippet:\s*([A-Za-z0-9_.]+)\s*-->\n"
    r"(.*?)"
    r"\n<!--\s*/snippet\s*-->",
    re.DOTALL,
)
_CHARACTER_LINE_RE = re.compile(r"\A[ \t]*<!--\s*character:\s*[A-Za-z]+\s*-->[ \t]*\n")

_cache: Dict[str, str] = {}
_loaded = False


def _load_all() -> None:
    global _loaded
    _cache.clear()
    if not os.path.isdir(_SKILLS_DIR):
        raise RuntimeError(f"skills directory not found: {_SKILLS_DIR}")
    for name in sorted(os.listdir(_SKILLS_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(_SKILLS_DIR, name)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        for match in _SNIPPET_RE.finditer(text):
            snippet_id = match.group(1)
            body = match.group(2)
            body = _CHARACTER_LINE_RE.sub("", body, count=1)
            if snippet_id in _cache:
                raise RuntimeError(
                    f"duplicate snippet id '{snippet_id}' "
                    f"(second occurrence in {name})"
                )
            _cache[snippet_id] = body
    _loaded = True


def _ensure_loaded() -> None:
    if not _loaded:
        _load_all()


def reload() -> None:
    """Re-read all skill files from disk. Mainly for tests."""
    _load_all()


def get(snippet_id: str) -> str:
    """Return the raw text of a snippet."""
    _ensure_loaded()
    if snippet_id not in _cache:
        raise KeyError(f"snippet '{snippet_id}' not found in skills/")
    return _cache[snippet_id]


def render(snippet_id: str, **vars) -> str:
    """Return the snippet rendered with str.format(**vars)."""
    template = get(snippet_id)
    try:
        return template.format(**vars)
    except KeyError as e:
        raise KeyError(
            f"missing variable {e} when rendering snippet '{snippet_id}'"
        ) from e
