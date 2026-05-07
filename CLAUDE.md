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

### A.8 Guiding principles for external integrations

External integrations (GovMap, iplan.gov.il, Tabu, Nadlan.gov.il, CBS,
Google Maps, etc.) are valuable when they work and a liability when
they don't. The following rules govern every external-service feature:

- **Polite failure is mandatory.** If a service is unreachable,
  unauthenticated, slow, or returns an unexpected payload, the
  appraiser must be able to keep working manually with no
  interruption to the form-fill → generate flow. The HTTP handler
  returns a structured result with a Hebrew message; it never
  raises a 500 to the appraiser.
- **No technical errors in the UI.** SSL stack traces, JSON parse
  failures, ArcGIS error codes, etc. must never be shown to the
  appraiser. Translate everything into a short Hebrew sentence the
  appraiser can act on, or hide it entirely.
- **Hide unstable features.** If an integration is not reliable in
  production — even temporarily — remove its entry point from the
  UI rather than show it broken. The supporting code (module,
  endpoint, dependencies) may stay so the feature can be re-enabled
  cleanly when the underlying service is fixed.
- **Source attribution stays visible.** Per A.7, any value brought in
  from an external source must be presented with its provenance so
  the appraiser can verify it before signing.

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
| `POST /shuma/lookup-parcel` | `real_estate/web.py:lookup_parcel_endpoint` | Best-effort lookup of block/parcel/land-use/plans/boundaries from an address — see B.12 |
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
├── claude_descriptions.py auto-fill city/neighborhood (B.11)
├── parcel_lookup.py   address → block/parcel/land-use/plans/boundaries (B.12)
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
  description, city+neighborhood description (optional — auto-filled via
  Claude when blank, see B.11), photos (up to 8), planning documents
  (each tagged with section 04 or 05), 06 purchase (Standard 19 only —
  appears dynamically), 07 valuation, 08 notes.
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

- `_section_00_cover` — cover page: gray-shaded 1×1 table containing 4
  bold+underlined centered title lines, followed by the first property
  photo. Shows " מלאה" suffix only for Standard 19 / Evacuation reports.
- `_section_01_title` — title block + opening letter, gendered salutation
- `_section_02_details_table` — borderless property details rendered as
  RTL paragraphs with two tab stops (label → ":" → value), not a Word table
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
(`OxmlElement`, `qn`) to enforce, in addition to per-paragraph RTL:
- A4 page size (`pgSz` 11906×16838 DXA) and margins
  (top/bottom 1440, left/right 1800, header 708, footer 1020)
- `<w:bidi/>`, `<w:rtlGutter/>` and `<w:titlePg/>` on the section's `sectPr`
- `<w:themeFontLang w:bidi="he-IL"/>` in `settings.xml`
- `<w:bidiVisual/>` on every table created via `make_table` (columns flip RTL)
- `David` as the default font (ascii / hAnsi / cs)
- Header and footer that embed `assets/header_logo.png` and
  `assets/footer_strip.png` (centered, ~16.5 cm wide). Missing assets
  produce empty header/footer paragraphs — the document still validates.
- Bullet paragraphs use a single RTL run beginning with `"• "` so the
  bullet appears on the right
- `add_heading` produces bold + underline at body size (no Word built-in
  Heading style — those introduce sans-serif blue text)
- `add_field_line(label, value)` for the label-tab-colon-tab-value
  layout used in the property-details section
- `set_cell_shading(cell, fill_hex)` for the cover page's gray box

Public API (unchanged): `make_rtl_doc`, `add_para`, `add_heading`,
`add_bullet`, `set_cell`, `make_table` — all existing call sites continue
to work.

The lower-level RTL contract still holds:
- `bidi=1` at document, paragraph and cell level
- `jc=right` for justification
- `<w:rtl/>` on every run
- David font for ASCII, hAnsi, and complex script
- Fixed sizes: TITLE=16, HEADING1=14, HEADING2=13, BODY=12

Public functions: `make_rtl_doc`, `add_para`, `add_heading`, `add_bullet`,
`set_cell`, `make_table`. **Always use these.** Never set `cell.text`
directly — it silently strips RTL.

### B.9 Dependencies installed

From root `requirements.txt`:
- `fastapi >= 0.111.0`
- `uvicorn[standard] >= 0.29.0`
- `anthropic >= 0.25.0` — used by the generic agent runner *and* by the
  Claude descriptions module (see B.11)
- `python-docx >= 1.1.0`
- `python-multipart >= 0.0.9`
- `requests >= 2.31.0` — HTTP client used by the parcel-lookup module
  and the Nadlan client (see B.12, B.14)
- `pyproj >= 3.6.0` — WGS84 → ITM (EPSG:2039) projection
  (used by both B.12 and B.14)
- `shapely >= 2.0.0` — polygon geometry for boundary processing (B.12)

The Nadlan integration (B.14) added **no new dependencies** —
`requests` and `pyproj` were already available from B.12.

### B.10 Validation

Client-side only (in `shuma.html` JS). No server-side validation. No
linter config. No `.env.example` for the appraisal system itself
(`ANTHROPIC_API_KEY` is used by the agent runner and by the Claude
descriptions module — see B.11).
Server-side coverage is provided by `tests/test_golden.py` (pytest):
generates the three demo reports and hashes the extracted text — run
with `UPDATE_GOLDEN=1 pytest tests/test_golden.py` to refresh after
intentional wording changes. `tests/test_claude_descriptions.py` runs
live integration tests against the Claude API; the whole module is
skipped automatically when `ANTHROPIC_API_KEY` is not set.

### B.11 Claude descriptions module (auto-fill city/neighborhood) — v2 (with web search)

`real_estate/claude_descriptions.py` exposes `describe_city(city_name)`
and `describe_neighborhood(city_name, neighborhood_name)`, each returning
a single short Hebrew paragraph generated by Claude.

**Model:** `claude-sonnet-4-6` (upgraded from Haiku 4.5). Haiku produced
Hebrew with grammatical errors and occasional language mixing (Arabic
fragments) — unacceptable in a signed appraisal report.

**Web search:** the call enables Anthropic's built-in server-side
`web_search_20250305` tool (max 5 uses per call, IL locale). Claude
searches for the specific place before writing, so the description is
grounded in real information rather than the model's general knowledge.
This addresses the prior failure mode where Haiku produced generic
descriptions that did not differentiate between neighborhoods. The
system prompt also permits inline-cited quantitative claims when the
search surfaces them with an authoritative source (e.g. CBS, municipal
site).

**Insufficient information sentinel:** when search does not surface
information specific to the requested place, the model is instructed
to return the literal string `INSUFFICIENT_INFO`. The wrappers
`try_describe_city` / `try_describe_neighborhood` translate that into
`None` so the Web handler keeps the existing "יש להשלים" placeholder
rather than display a generic-and-possibly-wrong description.

Wiring: `real_estate/web.py:generate(...)` accepts three optional form
fields — `city_description`, `neighborhood_name`, `neighborhood_description`.
When `city_description` is empty (or contains the legacy "יש להשלים"
placeholder) and a city was parsed from the address,
`try_describe_city(city)` is called and the result, suffixed with the
source footnote (`with_footnote(...)`), replaces the placeholder. The
neighborhood path mirrors this and additionally requires the appraiser
to provide a neighborhood name. Both wrappers return `None` on
INSUFFICIENT_INFO, on API failure, or when the package/key is missing —
the existing "יש להשלים" placeholder is preserved in all those cases.

Source attribution per A.7: the footnote sentence
`(תיאור זה נוצר אוטומטית ויש לאמת מול מקורות סמכותיים.)` is appended
to every auto-filled paragraph so the appraiser sees what to verify
or remove before signing.

**Costs (rough order of magnitude per call):** Sonnet 4.6 is
\$3 / MTok input, \$15 / MTok output; the built-in web search is
\$10 per 1,000 searches in addition to token usage. A typical call
performs 1-2 searches and returns a 100-token paragraph, with
several thousand input tokens of fetched search content — see
`descriptions_v2_report.md` for the worked estimate.

### B.12 Parcel-lookup module (auto-fill block / parcel / land-use / plans / boundaries) — currently hidden in UI

`real_estate/parcel_lookup.py` exposes one public function,
`lookup_parcel(address) -> ParcelLookupResult`, that turns a Hebrew
address into structured property data. The `POST /shuma/lookup-parcel`
endpoint is wired in `web.py` and the module + dependencies
(`requests`, `pyproj`, `shapely`) are installed and ready.

**Status: feature is hidden from the appraiser.** The "מלא נתוני חלקה
אוטומטית" button and the five corresponding form fields (land-use +
four boundaries) were removed from `shuma.html` because the iplan.gov.il
ArcGIS service has an SSL/TLS compatibility issue that prevents the
service from being reached from the Railway production host (and from
ordinary browsers). Per A.8, an unstable integration is hidden until
it works reliably — but the supporting code stays so the feature can
be re-enabled by re-adding the button + fields when the upstream
issue is fixed or an alternative endpoint is wired in.

**Pipeline:**

1. **Geocoding.** `_geocode(address)` calls
   `https://nominatim.openstreetmap.org/search` with `countrycodes=il`
   and a descriptive `User-Agent` (Nominatim's usage policy blocks
   anonymous requests). Returns `(lat, lon)` in WGS84.
2. **Projection.** `_to_itm(lat, lon)` projects to Israeli Transverse
   Mercator (EPSG:2039) using `pyproj.Transformer` — Israeli planning
   services expect ITM coordinates.
3. **ArcGIS query.** `_list_layers()` fetches the layer index of
   `https://ags.iplan.gov.il/arcgis/rest/services/PlanningPublic/Xplan/MapServer`
   and `_find_layer_id` matches layer names against substring hints
   (`parcel_all`, `designation`, `plan`, plus Hebrew equivalents) so
   we don't hardcode IDs that change across service versions. The
   service is then queried at the parcel point for parcel attributes,
   land-use designation, and applicable plans, and at the parcel
   bounding-box for neighbouring parcel polygons.
4. **Boundary processing.** `_process_boundaries` reduces neighbouring
   polygons into four cardinal descriptions. Per neighbour: compute
   centroid offset from the subject parcel, classify by dominant axis
   (north / south / east / west), keep the closest neighbour per
   direction. This is the simplified "quadrant" strategy authorised
   by the brief — accurate enough for the appraiser to verify and
   adjust before signing.

**Result shape** (`ParcelLookupResult.to_dict()`):

```
{
  "ok": bool,                       # true iff block + parcel were found
  "block": "...", "parcel": "...",
  "land_use": "...",
  "plans": [{number, name, designation, year}, ...],
  "boundaries": {north, south, east, west},
  "warnings": ["..."],              # Hebrew strings shown to the appraiser
  "error": "..."                    # Hebrew string when the pipeline failed
}
```

Sub-parcel (`תת-חלקה`) is **not** populated — Xplan does not expose it.
The form keeps it as a manual field.

**Wiring in the Web layer.** `web.py` adds five new optional form
fields (`land_use`, `north_boundary`, `south_boundary`, `east_boundary`,
`west_boundary`) to the existing `/shuma/generate` payload. They flow
into `PropertyInput` so the report renders the looked-up values
instead of "יש להשלים". The four `*_boundary` fields plus
`zoning_for_principles` (= `land_use`) gracefully fall back to
"יש להשלים" when the appraiser leaves them empty, preserving
backwards compatibility with the previous form behaviour.

**Failure modes** are surfaced to the appraiser, never raised:

- Empty address → `error="הכתובת ריקה"`.
- Nominatim fails or returns nothing → `error="הכתובת לא זוהתה ..."`.
- Xplan unreachable → `error="שירות תכנון זמין אינו זמין ..."`.
- Layer hint matches nothing → entry recorded in `warnings`, the
  rest of the data is still returned.
- Geometry parsing exception → recorded as a warning; the block /
  parcel attributes are still returned even if boundaries failed.

The Web form button shows `error` in red, fills only the blank
fields with what was returned, and shows applicable plans in an
informational box (the existing form has no plans-list field — wiring
plans into structured input is a follow-up).

### B.13 External integrations

| Service | Endpoint | Used for | Notes |
|---|---|---|---|
| Nominatim (OSM) | `https://nominatim.openstreetmap.org/search` | Hebrew address → (lat, lon) | No key; requires descriptive `User-Agent`; 1 req/sec policy |
| Iplan Xplan ArcGIS | `https://ags.iplan.gov.il/arcgis/rest/services/PlanningPublic/Xplan/MapServer` | Parcel polygon, land-use, plans, neighbouring parcels | Public; no key. Layer IDs discovered at runtime by name hints (parcel / designation / plan) |
| Anthropic API | `https://api.anthropic.com` (via SDK) | City / neighbourhood descriptions | Requires `ANTHROPIC_API_KEY` (B.11) |
| nadlan.gov.il | `https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals` | Recent transactions in radius | Public, no key. Endpoint shape unconfirmed live in sandbox — see B.14 |

### B.14 Nadlan comparables module (auto-fill comparison transactions)

`real_estate/nadlan_client.py` exposes two public functions —
`address_to_itm(address)` and
`fetch_recent_deals(itm_x, itm_y, radius_m, address_label="", max_results=10)`
— that pull recent real-estate transactions from the public
`nadlan.gov.il` "Nadlan.REST" endpoint and map them to
`ComparisonProperty` rows for the report's section 6 table.

**Pipeline.**

1. Geocode the Hebrew address via Nominatim (re-uses
   `parcel_lookup.geocode`).
2. Project WGS84 → ITM (EPSG:2039) (re-uses `parcel_lookup.to_itm`).
3. POST the documented payload to
   `https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals` with
   `Distance=radius_m`, `OrderByFilled=DEALDATETIME`,
   `OrderByDescending=true`.
4. Map each row to `ComparisonProperty`. Field mapping:
   `FULLADRESS → address`, `ASSETROOMNUM → rooms`, `FLOORNO → floor`,
   `DEALNATURE → built_area`, `DEALAMOUNT → price`,
   `DEALDATETIME / BUILDINGYEAR / NEWPROJECTTEXT` → `notes`.
   `balcony_area` is intentionally left as `None` because the API
   does not expose a balcony figure — the appraiser fills it manually
   per A.3 ("no fabricated data").

**Wiring.**

- New endpoint `POST /shuma/comparables` (`real_estate/web.py`).
  Accepts JSON `{address, radius_m, itm_x?, itm_y?}`. Never returns
  HTTP 5xx — failure paths emit HTTP 200 with `success=false` plus
  a Hebrew `message_he` and an `error_code` of either
  `GEOCODING_FAILED` or `NADLAN_UNAVAILABLE`. Empty results return
  `success=true, deals=[]` with a "increase the radius" message.
- New form card "עסקאות השוואה" between section 07 and 08 in
  `shuma.html`. Slider for radius (100-1000 m, default 300), "טען
  עסקאות השוואה" button, dynamic table with checkboxes (include /
  outlier) and editable cells. Manual ITM fallback fields appear only
  after a `GEOCODING_FAILED` response.
- `POST /shuma/generate` accepts new `comparable_address[]`,
  `comparable_rooms[]`, `comparable_floor[]`, `comparable_built_area[]`,
  `comparable_balcony_area[]`, `comparable_price[]`, `comparable_notes[]`,
  `comparable_is_outlier[]`, `comparables_fetched_at` form fields.
  Helper `_build_comparables(...)` zips them into a list of
  `ComparisonProperty` and stores it on `PropertyInput.comparison_properties`.

**Model changes.**

- `ComparisonProperty.balcony_area` is now `Optional[float]` and
  `is_outlier: bool = False` was added.
  `ComparisonProperty.equiv_area` treats `None` and `<= 0` identically
  (no balcony component).
- `PropertyInput.comparables_fetched_at: Optional[str] = None` records
  the date when comparables were fetched from `nadlan.gov.il`. The
  source-attribution footnote on the comparison table is rendered only
  when this field is non-empty.

**Report changes (`_section_06_valuation`).**

- Outlier rows are prefixed with `(*)` in the row-number column. When
  any row is marked `is_outlier=True` the outlier footnote is rendered
  below the table.
- The balcony / equivalent-area columns are *hidden* when fewer than
  half of the included rows have a balcony figure (per A.3 — better to
  drop the columns than to render misleading "—" placeholders).
- A new balcony-coefficient footnote is rendered when the columns are
  shown and at least one row has a balcony.
- A source-provenance footnote
  (`הנתונים הינם כפי שמפורסם בנדל"ן.gov.il, נמשך {date}.`) is
  rendered iff `comparables_fetched_at` is set.

**Snippets** (in `skills/06_valuation.md`):

- `section_06.comparison.footnote.outlier` (fixed)
- `section_06.comparison.footnote.balcony_coef` (fixed)
- `section_06.comparison.footnote.source` (semi)

**Geocoding helpers re-used.** Per the system owner's preference and
to avoid the same drift problem documented in C.5, the helpers in
`parcel_lookup.py` were re-exported as public `geocode(address)` /
`to_itm(lat, lon)` and imported by `nadlan_client.py`. No standalone
`geocoding.py` module was introduced.

**Live endpoint not verified in sandbox.** The published endpoint
returns the SPA `index.html` from CloudFront on every request from
the development sandbox (see `nadlan_integration_report.md` for the
full diagnostic and a manual `curl` command). The integration code
is built strictly to the documented request/response shape; manual
verification against the production environment is required, and
the current state is captured in C.12.

**Tests.** `tests/test_nadlan_integration.py` covers all the failure
paths the Web layer relies on plus an end-to-end check that the report
hides balcony columns and emits the outlier marker. The live probe
`test_live_endpoint_smoke` is `pytest.mark.skip`-d.

---

## Part C — Known Gaps

These are real issues in the current codebase. Some are bugs, some are
design tensions worth flagging. Don't fix them unless the current task
calls for it — but be aware of them.

### C.1 `payload` undefined bug in web.py — RESOLVED

The historical `payload.address` reference no longer exists in
`real_estate/web.py`. `generate(...)` uses the `address` form parameter
directly when computing the download filename. Verified by grep on the
visual-formatting pass; entry kept here for traceability and may be
removed on the next CLAUDE.md cleanup.

### C.2 Web form covers fewer fields than CLI form

The Web form collects a subset of the CLI fields. Missing fields are
filled with the literal string `"יש להשלים"` in `web.py`. The CLI
form covers parcel boundaries, land-use, planning plans, full
street-type details, full tenancy agreement dates, etc.

The parcel-lookup integration (B.12) was meant to close part of this
gap (block/parcel/land-use/plans/boundaries) but is currently hidden
from the UI — see C.10. So Web reports still render placeholders for
all of those today.

The comparables gap is *closed* by B.14: the new
"עסקאות השוואה" card lets the appraiser pull 10 recent transactions
from `nadlan.gov.il` and select which ones enter the report. Manual
entry is still possible by editing the auto-loaded rows.

### C.10 Parcel-lookup feature hidden — boundaries / land-use / plans still manual

The parcel-lookup module (`real_estate/parcel_lookup.py`) and the
`POST /shuma/lookup-parcel` endpoint are implemented and wired, but
the UI button and the five matching form fields were removed because
the iplan.gov.il service is not reachable from Railway / browsers
due to an SSL/TLS handshake issue on their side.

Practical effect: in Web reports, the four parcel boundaries, the
land-use designation, and the planning-plans list still render as
"יש להשלים" or remain empty — there is no UI path to fill them.
The supporting code is ready to re-enable when iplan fixes its TLS
or when we wire an alternative source. See B.12 and A.8.

### C.11 Sub-parcel (תת-חלקה) cannot be auto-filled

The Iplan Xplan service does not expose sub-parcel data, so even
when the parcel-lookup feature is re-enabled this field would stay
manual. The form keeps `sub_parcel` as a required text input.
Closing this gap likely requires Tabu (auth-gated) or another
commercial source and is out of scope for the open-data integration.

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

### C.12 Nadlan endpoint not verified live in development sandbox

The Nadlan client (B.14) targets
`https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals`. From
the development sandbox the URL returns the SPA `index.html`
(`text/html`, served from S3+CloudFront with
`x-cache: Error from cloudfront`) for every path under
`/Nadlan.REST/`. This may indicate (a) a CDN routing change, (b) the
endpoint moved to a different host, or (c) the public path now requires
a session/cookie obtained from the SPA bootstrap. Either way it
prevents an end-to-end live test from CI.

The integration code is built strictly to the documented payload and
response shape. **Manual verification on Railway after deploy is
required** — `nadlan_integration_report.md` contains the curl command
and the exact field mappings to confirm. If the live shape differs,
update `_to_comparison_property` in `real_estate/nadlan_client.py`
accordingly.

---

## Working with this file

When you finish a meaningful change to the codebase, propose updates
to **Part B only** as a diff. Do not edit Part A without an explicit
product decision from the user. Add new entries to Part C when you
discover gaps; remove entries when they are resolved.

Before starting any session that's been preceded by a break, read this
file, then scan the actual directory structure and verify Part B still
matches reality. If anything has drifted, flag it before starting work.
