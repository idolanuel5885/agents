# CLAUDE.md — Real Estate Appraisal Automation System

This file is your operating context. Read it at the start of every session.
It has three parts: stable principles (rarely change), current state (changes
often), and known gaps. When you finish a meaningful task, propose updates to
**Part B only** as a diff before writing.

---

## Part A — Stable Principles (last reviewed: initial draft)

### A.1 What this system is

A web-based tool that helps a single boutique appraiser in Tel Aviv produce
draft Israeli real estate appraisal reports (`דוח שמאות מקרקעין`). The appraiser
fills in property details through a Hebrew RTL form, uploads photos and
planning documents, and the system generates a Word file (.docx) that is a
near-final draft requiring light editing before signature.

The system does **not** replace the appraiser's professional judgment. Every
auto-filled value must remain visible, attributable to its source, and editable.

### A.2 Three report types

The system produces three distinct report types. Their differences are
substantive, not cosmetic:

1. **Market value report** (`דוח שוק`) — sections 1–6 only. No appendix.
2. **Standard 19** (`תקן 19`) — adds quick-realization value (85% of market
   value) and a separate tax appendix with capital gains calculation.
3. **Evacuation-construction** (`פינוי-בינוי`) — adds two alternatives:
   alternative A (current value) and alternative B (hypothetical future
   compensation unit value).

A given `PropertyInput` produces one of the three. The report type drives
which sections render and which validation rules apply.

### A.3 Hard constraints — never violate these

- **No fabricated data.** Property identifiers (block, parcel, sub-parcel),
  area measurements, owner names, permit numbers, transaction prices, and
  taxation figures must come from a verifiable source — either appraiser
  input or an authoritative external source (Tabu, Nadlan.gov.il, GovMap).
  If a value isn't available, render it as a placeholder (`[שם השדה]` or
  `יש להשלים`) so the appraiser sees what to fill manually.
- **No quantitative claims without a cited source.** When generating descriptive text (city, neighborhood, street descriptions), describe qualitative character only — geography, building style, accessibility, general atmosphere. Quantitative claims (population numbers, average prices, demographic percentages, growth rates) are permitted **only** when sourced from an authoritative reference cited inline (CBS / Lamas, official municipality website, official statistics body). Rounding for readability is acceptable. Inventing numbers from the model's general knowledge is not, even if the number is "probably correct." If a number is needed and no source is available, omit the claim or replace it with a qualitative description.
- **No drift in legal/factual sections.** Closing declarations, ethics
  statements, and the "principles of calculation" section contain text
  that is fixed by professional standards. Do not paraphrase or "improve"
  these. They are stored as fixed strings and must be inserted verbatim.
- **Hebrew RTL is mandatory.** All Word document output must use the
  helpers in `real_estate/docx_utils.py` — never set `cell.text` directly,
  never skip the `bidi=1` / `<w:rtl/>` markers. Direct python-docx writes
  silently break RTL.

### A.4 Style conventions for generated text

- Formal Hebrew, third person, neutral tone. The appraiser is referred to
  as `הח״מ` (the undersigned), never `אני`.
- The property under appraisal is called `נשוא חוות הדעת` or `הנכס שבנדון`.
- Built areas (measured) are prefixed with `כ-` (approximately).
  Registered areas (from the official record) are not.
- Cardinal directions: `צפון/דרום/מזרח/מערב` only — never `ימין/שמאל`.
- Sums use comma separators (`X,XXX,000 ₪`) and the final sum is also
  written in words.
- Land-use designations (`ייעוד`) appear in single quotes (`׳מגורים ג׳׳`).
- Avoid hedging language (`אולי`, `כנראה`) and avoid laudatory adjectives
  (`מרשים`, `יפה מאוד`). Appraisal language is neutral and evidentiary.

### A.5 Section character

Every report section has one of three characters that drives how it should
be generated and how it should be edited:

- **Fixed (`ק`)** — same text every report. Lives as a string constant.
  Examples: closing declarations, ethics statement, environmental
  development paragraph.
- **Semi-variable (`מ`)** — template with slots. Lives as a template with
  named placeholders. Examples: title block, property details table,
  building permit list.
- **Variable (`נ`)** — written fresh each report based on the specific
  property. Examples: city description, neighborhood description,
  comparable transactions table, final valuation paragraph.

When adding a new section or modifying an existing one, identify its
character first. Don't promote a fixed string to a template "for
flexibility" without a concrete reason — fixed strings are professionally
required to stay fixed.

### A.6 Data sources and their automation status

The system pulls data from these sources, each at a different automation
maturity:

| Source | What it provides | Status |
|---|---|---|
| Appraiser form input | All core property details, photos, decisions | Fully automated (it's the input) |
| Claude (LLM) | Qualitative city/neighborhood/street descriptions | Planned |
| Google Maps Static API | Location map, aerial reference | Planned |
| GovMap | Block/parcel lookup by address, aerial photo | Planned (internal API) |
| Nadlan.gov.il | Comparable transactions | Planned (internal API) |
| Tabu (`tabu.justice.gov.il`) | Land registry extract | Manual (auth required) |
| Municipal sites | Building permits, zoning plans | Manual (CAPTCHA) |
| CBS / Lamas (cbs.gov.il) | Official population, demographic, and statistical figures for cities and neighborhoods | Manual (when needed for specific data) |

For every planned automation, the principle is: **graceful degradation.**
If the auto-fetch fails, the UI opens the relevant external page in a new
tab and the appraiser fills 2–3 fields manually. The system never blocks
on a flaky integration.

### A.7 The appraiser's review flow is not optional

The system produces a draft, not a final document. Every auto-filled
section must be presented to the appraiser with its source visible (e.g.
"Block/parcel from GovMap, fetched 2025-11-12") so they can verify before
signing. This is both a professional requirement (signed appraisals are
the appraiser's legal responsibility) and a quality safeguard (auto-data
from internal/undocumented APIs may break or return wrong values).

When designing new automations, design the review surface alongside them.
"Fetch and insert silently" is never the right answer.

---

## Part B — Current State (last reviewed: initial draft, based on system audit)

### B.1 Stack and entry points

- **Language:** Python 3
- **Web framework:** FastAPI
- **Document generation:** `python-docx` with custom RTL helpers
- **Deployment:** Railway (`Procfile`, `railway.toml`) and local (`start.sh`),
  both run `uvicorn server:app`
- **Persistence:** None. Each report request is in-memory only.

Entry points:

| Path | Where | What it does |
|---|---|---|
| `GET /shuma` | `real_estate/web.py:get_form` | Returns the HTML form |
| `POST /shuma/generate` | `real_estate/web.py:generate` | Builds `PropertyInput` from form data, generates the docx, returns as download |
| `python real_estate/main.py` | `real_estate/main.py` | CLI: interactive prompts → docx file |
| `python run_demo.py [type]` | `run_demo.py` | Generates a demo report without form input |

The root `server.py` also hosts an unrelated generic "agent runner" at `/`.
The appraisal system is mounted via `app.include_router(shuma_router)` and
is independent of it. Ignore the `agents/` directory and the runner UI
unless the task explicitly involves them.

### B.2 Directory layout (relevant parts only)

```
real_estate/
├── __init__.py        (empty)
├── models.py          dataclasses + Enums (data model)
├── form.py            CLI interactive form
├── web.py             FastAPI router mounted at /shuma
├── shuma.html         single-file HTML+CSS+JS form
├── docx_utils.py      python-docx RTL helpers
├── report_generator.py the report builder (templates + all sections)
├── demo_data.py       sample PropertyInput for the three report types
└── main.py            CLI entry point
```

### B.3 Data model

Single core dataclass: `PropertyInput` in `real_estate/models.py`. ~85
fields covering report metadata, client, property identification, rights,
building, apartment, attached units (parking/storage/garden), tenancy,
environment, parcel boundaries, planning and permits, valuation,
tax appendix (Standard 19 only), evacuation-construction alternatives,
free-text notes, and uploaded media.

Two nested dataclasses:

- `ComparisonProperty` — a comparable transaction. Has computed
  properties `equiv_area` (using a tiered balcony coefficient: 50%
  up to 50sqm, 25% up to 100, 10% beyond) and `price_per_sqm`.
- `PlanningPlan` — a zoning plan reference (number, gazette, zoning).

Five enums:

- `ReportPurpose` — `שוק | תקן_19 | פינוי_בינוי`
- `RightsType` — `בעלות_פרטית | חכירה_רמי | חכירה_חברה`
- `FinishLevel` — `בסיסית | טובה | טובה מאוד`
- `PermitStatus` — `על פי היתר | חריגות`
- `ClientGender` — `זכר | נקבה | חברה | בנק`

There is no DB layer, no session, no persistence. The object is built
in memory from a single request and converted to docx within the same
HTTP response.

### B.4 How input is collected

Two parallel input paths produce the same `PropertyInput`:

**Web (the path used in practice):**
- `real_estate/shuma.html` is a single 704-line file with embedded HTML,
  CSS and JS. No external dependencies.
- The form is divided into cards: 01 purpose+client, 02 identification,
  03 apartment, 04 building (optional), 05 tenancy (optional), street
  description, photos (up to 8), planning documents (each tagged with
  section 04 or 05), 06 purchase (Standard 19 only — appears
  dynamically), 07 valuation, 08 notes.
- 13 required fields (marked with asterisk) are validated client-side
  in JS, with red highlight and scroll to first error.
- Submission: `fetch('/shuma/generate', { method:'POST', body: FormData })`,
  then download the blob as `שומת_מקרקעין_<address>.docx`.

**CLI:**
- `real_estate/form.py:collect_form()` prompts for all ~85 fields one
  by one via `input()`.
- The CLI covers more fields than the Web form — including all four
  parcel boundary directions, full city/neighborhood/street descriptions,
  3+ comparable transactions, planning plan details, full tenancy
  agreement dates. Web reports therefore have more "יש להשלים" placeholders
  than CLI reports.

### B.5 Report generation pipeline

Entry: `real_estate/report_generator.py:_build_doc(data)`. Builds the
report as a sequence of `_section_NN_*` calls separated by
`add_page_break()`. Sections:

- `_section_01_title` — title block + opening letter, gendered salutation
- `_section_02_details_table` — two-column property details table
- `_section_03_description` — city/neighborhood/street, parcel
  (with boundary table), apartment description (two paragraphs:
  emphasis + detail), finish level, permit status, tenancy
- `_section_photos` — 2-column grid of property photos if present
- `_section_04_planning` — zoning plans + permits (bullets) + planning
  document images (those tagged `doc_type=="04"`)
- `_section_05_legal` — Tabu extract (table), parcellation diagram
  placeholder, tenancy agreement if rented + images tagged `doc_type=="05"`
- `_section_06_valuation` — principles (4 sub-sections with bullets),
  comparison table, final valuation paragraph with `num_to_words`,
  closing declarations, plus conditional additions:
  - Standard 19 → quick-realization line at 85%
  - Evacuation-construction → two alternatives
- `_section_07_tax` — tax appendix (Standard 19 only): gain =
  `final_value - purchase_price`, 25% capital gains, net
- `_section_notes` — only if `special_notes` is non-empty

Two distribution wrappers in the same module:
- `generate_report(data, path)` — saves to file
- `generate_report_bytes(data) -> bytes` — returns bytes for HTTP response

### B.6 Where fixed text and templates live

Report wording lives in `skills/*.md` as marked snippets, loaded at
runtime by `real_estate/skill_loader.py`. The generator calls
`skill_loader.get(id)` (literal text) or `skill_loader.render(id, **vars)`
(template). Snippet markers look like:

```
<!-- snippet: section_03.apt.opening -->
<!-- character: variable -->
נשוא חוות הדעת מהווה דירה בת {rooms} חדרים ...
<!-- /snippet -->
```

The optional `<!-- character: ... -->` line carries the section's A.5
character (`fixed`/`semi`/`variable`).

| Category | Location |
|---|---|
| Hebrew number-to-words dictionaries | `report_generator.py` top (`_ONES`, `_TENS`, `_HUNDREDS`, `_FLOOR_ORD`) |
| Report purpose phrases | `skills/01_header.md` (`purpose.*`) |
| Rights type phrases | `skills/02_property_details.md` (`rights.*`) |
| Three "finish level" paragraphs | `skills/03_description.md` (`finish.*`) |
| All fixed report paragraphs and templates (sections 01–07, photos, notes) | `skills/NN_*.md` (`section_NN.*`) |
| Missing-field placeholders | `f"[{field name}]"` via `_opt(...)` (still in code; sentinel for empty data) |
| Filename templates | `main.py:29` and `web.py:236` (RFC 5987 encoding for Hebrew filenames) |
| Hebrew month names | `web.py:_HE_MONTHS` |
| Enum→Hebrew label mappings (form input side) | `web.py` (Web→Enum) and `form.py` (CLI→Enum), defined twice |
| Form CSS and UI strings | embedded in `shuma.html` |
| Demo data (sample city/neighborhood text) | `real_estate/demo_data.py` |

When asked to modify report wording, edit the snippet in the matching
`skills/*.md` file; the generator picks it up automatically. When
asked to modify generation structure or data flow, edit
`report_generator.py`. If a wording change requires structural change
too, do both.

### B.7 Skills directory

`skills/*.md` files contain both human-readable guidance for each
section and (under "## Generator snippets") the marked text blocks
the generator loads via `real_estate/skill_loader.py`. The migration
that wired the generator to these files is complete — embedded
strings in `report_generator.py` have been removed and replaced with
loader calls.

### B.8 RTL helper layer

`real_estate/docx_utils.py` wraps python-docx with raw XML
(`OxmlElement`, `qn`) to enforce:
- `bidi=1` at document, paragraph and cell level
- `jc=right` for justification
- `<w:rtl/>` on every run
- Arial font for ASCII, hAnsi, and complex script
- Fixed sizes: TITLE=16, HEADING1=14, HEADING2=13, BODY=12

Public functions: `make_rtl_doc`, `add_para`, `add_heading`, `add_bullet`,
`set_cell`, `make_table`. **Always use these.** Never set `cell.text`
directly — it silently strips RTL.

### B.9 Dependencies installed

From root `requirements.txt`:
- `fastapi >= 0.111.0`
- `uvicorn[standard] >= 0.29.0`
- `anthropic >= 0.25.0` — used by the generic agent runner only, not by
  the appraisal system
- `python-docx >= 1.1.0`
- `python-multipart >= 0.0.9`

**Not currently installed** (will be needed for upcoming automation):
no HTTP client (`requests` / `httpx`), no HTML parser, no Google SDK,
no GIS library, no OAuth client. Add them as needed.

### B.10 Validation

Client-side only (in `shuma.html` JS). No server-side validation. No
linter config. No `.env.example` for the appraisal system itself
(`ANTHROPIC_API_KEY` is used only by the unrelated agent runner).
Server-side coverage is provided by `tests/test_golden.py` (pytest):
generates the three demo reports and hashes the extracted text — run
with `UPDATE_GOLDEN=1 pytest tests/test_golden.py` to refresh after
intentional wording changes.

---

## Part C — Known Gaps

These are real issues in the current codebase. Some are bugs, some are
design tensions worth flagging. Don't fix them unless the current task
calls for it — but be aware of them.

### C.1 `payload` undefined bug in web.py

`real_estate/web.py:235` references `payload.address`, but no `payload`
variable exists in the scope of `generate(...)`. The address comes in
as the form parameter `address`. This will fail at runtime when
generating a report from the Web. Likely a refactor leftover. Verify
before relying on the Web path end-to-end.

### C.2 Web form covers fewer fields than CLI form

The Web form collects a subset of the CLI fields. Missing fields are
filled with the literal string `"יש להשלים"` in `web.py:155-232`. As
a result, Web-generated reports contain visible placeholders that the
appraiser must fill in manually. It's unclear whether this is an MVP
shortcut or an intentional design choice — but this is exactly the
gap that external automation (Tabu / Nadlan.gov.il / GovMap / Google)
is meant to close.

### C.3 Plan documents accept non-image files

`property_images` is capped at 8 in JS but not on the server.
`plan_docs` accepts uploads matching the `accept` attribute (which
includes PDF/DOCX), but the rendering function only calls
`add_picture` — non-image attachments fail and render as
"[תמונה לא תקינה]". Either restrict accepted types or add a
PDF-to-image conversion step.

### C.4 Web path has no logging on success

`generate_report(...)` prints on save; `generate_report_bytes(...)`
does not. The Web path is therefore silent on successful generation.
Consider structured logging if you need visibility into Web usage.

### C.5 Enum→label mapping is duplicated

`_PURPOSE_MAP`, `_RIGHTS_MAP`, `_GENDER_MAP`, `_FINISH_MAP` exist in
`web.py:75-95` and again in `form.py:137-205`. The display phrases
(`purpose_display`, `rights_display`) are in `report_generator.py`.
Three places, slightly different concerns, easy to drift out of sync.

### C.6 No persistence means no audit trail

The system regenerates a fresh PropertyInput from form data on every
request. There's no record of what was generated when, what data was
used, or what auto-fetched values were inserted. For a system that
will rely on possibly-flaky external APIs, an audit log of "this
report used these values from these sources at this time" would be
valuable both for debugging and for the appraiser's professional
defense.

### C.7 Limited test coverage

`tests/test_golden.py` covers the three demo reports end-to-end via
text-content hashes. There is no unit coverage of `skill_loader`,
`docx_utils`, or the `web.py` request handler, and no schema check
that every snippet referenced from `report_generator.py` actually
exists in `skills/` (a typo would only be caught at generation time
for the unlucky code path).

### C.9 Skill files referenced yad2 and madlan, which are not approved data sources

Resolved as part of this commit — references removed from `skills/00_index.md`. The system's approved data sources are: nadlan.gov.il, govmap, Google Maps, Tabu, CBS. yad2 and madlan are not approved.

---

## Working with this file

When you finish a meaningful change to the codebase, propose updates
to **Part B only** as a diff. Do not edit Part A without an explicit
product decision from the user. Add new entries to Part C when you
discover gaps; remove entries when they are resolved.

Before starting any session that's been preceded by a break, read this
file, then scan the actual directory structure and verify Part B still
matches reality. If anything has drifted, flag it before starting work.
