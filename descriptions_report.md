# Claude Descriptions — Implementation Report

## Scope delivered

Added an integration with the Claude API that auto-fills the city and
neighborhood description fields in the appraisal report when the
appraiser leaves them blank in the Web form. Output is qualitative-only
(no quantitative claims), per CLAUDE.md A.3 and the rules in
`skills/03_description.md` ("תיאור עיר — כללים מעודכנים").

Branch: `add-claude-descriptions` (off `main`).

## Files changed / added

| File | Change |
|---|---|
| `real_estate/claude_descriptions.py` | **NEW.** `describe_city`, `describe_neighborhood`, `try_describe_*` (graceful), `with_footnote`, `SOURCE_FOOTNOTE`, `DescriptionUnavailable` |
| `real_estate/web.py` | Accepts new optional fields `city_description`, `neighborhood_name`, `neighborhood_description`. When empty/placeholder, calls Claude and substitutes the result with the source footnote. Failures are logged and fall back to the old `יש להשלים` placeholder |
| `real_estate/shuma.html` | New optional card "תיאור עיר ושכונה" with a neighborhood-name field plus two textareas. Hints explain that empty values trigger Claude auto-fill |
| `tests/test_claude_descriptions.py` | **NEW.** Live integration tests for Tel Aviv / Jerusalem / Ramat Gan + a neighborhood for each. Whole module skipped when `ANTHROPIC_API_KEY` is not set |
| `CLAUDE.md` | Updated B.4 (form cards), B.9 (anthropic dependency note), B.10 (validation), and added section B.11 documenting the new module and wiring |

## Module design

`real_estate/claude_descriptions.py`:

* Model: `claude-haiku-4-5-20251001` (fast, sufficient for short Hebrew
  paragraphs).
* Auth: reads `ANTHROPIC_API_KEY` from the environment via the standard
  `anthropic.Anthropic()` constructor.
* System prompt: in Hebrew. Quotes the rules from
  `skills/03_description.md` directly, including the explicit ban on
  quantitative content because this tool has no web access and therefore
  no source to cite. Also forbids laudatory/marketing language and
  first-person voice.
* Public API:
  * `describe_city(city_name) -> str` — raises `DescriptionUnavailable`
    on any error.
  * `describe_neighborhood(city_name, neighborhood_name) -> str` — same.
  * `try_describe_city(...) -> Optional[str]` — never raises; logs and
    returns `None`.
  * `try_describe_neighborhood(...) -> Optional[str]` — same.
  * `with_footnote(text)` — appends the visible-source footnote.
  * `SOURCE_FOOTNOTE = "תיאור זה נוצר אוטומטית ויש לאמת מול מקורות סמכותיים."`
* The Web handler uses the `try_*` variants so that any Claude failure
  (network, missing key, quota, malformed response) leaves the existing
  `"יש להשלים"` placeholder intact and the report still renders.

## Source attribution (CLAUDE.md A.7)

Every paragraph that Claude generated is appended with the footnote:

> (תיאור זה נוצר אוטומטית ויש לאמת מול מקורות סמכותיים.)

The appraiser sees this in the docx, verifies the description against
their own knowledge or an authoritative source, and removes the
footnote (or rewrites the paragraph) before signing. The web handler
also writes an `INFO` log line on each successful auto-fill noting
which field was filled and for which city/neighborhood.

## Graceful failure verification

With `ANTHROPIC_API_KEY` unset, end-to-end submission of the form to
`POST /shuma/generate` returned HTTP 200 with a 40 KB docx that still
contained `יש להשלים` for the description fields and **did not** contain
the auto-generation footnote. The two `try_describe_*` calls each
emitted a single `WARNING` log line ("ANTHROPIC_API_KEY is not set") and
returned `None`. So the answer to the question in the brief is: yes —
when the key is removed the report is still produced with the
"יש להשלים" placeholder.

```
describe_city('תל אביב') failed: ANTHROPIC_API_KEY is not set
describe_neighborhood('תל אביב', 'רמת אביב') failed: ANTHROPIC_API_KEY is not set
status: 200 bytes: 40074
contains placeholder: True
contains auto-footnote: False
```

## Demo runs

All three demo report types still build cleanly:

```
python run_demo.py שוק          → demo_shuk.docx
python run_demo.py תקן19         → demo_teken19.docx
python run_demo.py פינוי_בינוי   → demo_pinui_binui.docx
```

`tests/test_golden.py` — 6 passed, 0 failed (text hashes unchanged).
`tests/test_claude_descriptions.py` — 8 skipped (no key in this
environment).

Local server smoke test: `uvicorn server:app --port 8765` →
`GET /shuma` returned 200 with the new form fields present;
`POST /shuma/generate` with the new `neighborhood_name=רמת אביב`
returned 200 with a valid docx.

## Live Claude examples (Tel Aviv / Jerusalem / Ramat Gan)

**Not produced.** The execution environment for this run does not
expose an `ANTHROPIC_API_KEY` env var (only OAuth credentials for
Claude Code itself), and the `anthropic` SDK requires the key to make
direct API calls. The integration test module is wired exactly for
this case — it skips cleanly without a key — and will produce real
descriptions as soon as it runs in an environment where the key is
present (CI, the appraiser's deployment, or a dev shell with the key
exported). If a sample is needed before deploying, run:

```
ANTHROPIC_API_KEY=... python -c "from real_estate.claude_descriptions \
import describe_city, describe_neighborhood; \
print(describe_city('תל אביב')); \
print(describe_neighborhood('תל אביב','רמת אביב'))"
```

The integration test cases prepared (and which will execute when a
key is present) cover exactly the requested combinations:

* City: תל אביב, ירושלים, רמת גן, חיפה (the qualitative-only spot check).
* Neighborhood: תל אביב/רמת אביב, ירושלים/רחביה, רמת גן/מרום נווה.

The qualitative spot-check (`test_describe_city_avoids_quantitative_claims`)
asserts the response contains no digit characters — a heuristic
backstop in case a future model regression starts emitting numbers
despite the system prompt. If a legitimate output ever needs digits,
relax the test, not the system prompt.

## Things noticed but not touched

These are observations from working in the area; they were left as-is
to honour the "no scope creep, no refactor" instruction in the brief.

* **CLAUDE.md C.1 ("`payload.address` undefined bug")** — already
  resolved on `main`; `web.py` now uses `address` directly. The C.1
  entry is stale and could be removed in a follow-up doc pass.
* **`requirements.txt` already lists `anthropic >= 0.25.0`.** Good —
  no dependency change was needed. The Procfile / Railway deploy
  already installs it.
* **CLI form (`real_estate/form.py`)** — still asks for
  `city_description` / `neighborhood_description` interactively. I
  left the CLI path untouched; auto-fill is wired only to the Web
  path. If the CLI is still used, the same `try_describe_*` calls
  could be added behind an "Enter to auto-fill" prompt, but that's a
  separate task.
* **No prompt-caching / batching.** Each call sends the full system
  prompt every request. At Haiku rates and ~2 calls per report this
  is negligible; if the system later auto-fills more sources per
  report, switching to cached system prompts (`cache_control`) is
  the next optimization.
* **Heuristic test for "no digits"** — could yield false positives
  for legitimate qualitative outputs that happen to mention an
  ordinal in digit form. Documented in the test docstring with
  guidance to relax the test, not the prompt.
* **Web form covers fewer fields than CLI (CLAUDE.md C.2)** — this
  change closes one slice of that gap (city + neighborhood text)
  but the rest (lot boundaries, planning plans, full tenancy dates,
  comparable transactions) still defaults to "יש להשלים".
* **No persistence (CLAUDE.md C.6)** — the auto-fill is invisible
  after the report is downloaded. If/when an audit log is added,
  recording "city_description: claude-haiku-4-5 at YYYY-MM-DD HH:MM"
  alongside the generated text would be a high-value entry.
