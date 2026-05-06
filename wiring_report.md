# Wiring report — skills → report generator

## 1. Summary

Branch: `wire-skills-to-generator` (off `main`).

The migration described in CLAUDE.md C.8 ("skills directory exists but
is not yet wired into the generator") is now complete.

- **Snippet format:** `<!-- snippet: id -->` … `<!-- /snippet -->`
  blocks inside each `skills/*.md` file. Templates use Python
  `str.format`-style `{var}` placeholders.
- **Loader:** `real_estate/skill_loader.py` exposes `get(id)` (literal
  text) and `render(id, **vars)` (template). Loads all skill files on
  first call and raises `KeyError` for unknown IDs.
- **Snippets identified and migrated:** **179** total, distributed:
    - 01 header — 19
    - 02 property details — 26
    - 03 description — 35
    - 04 planning — 10
    - 05 legal — 22
    - 06 valuation — 57
    - 07 tax annex — 10
- **Sections converted:** all eight (`_section_01_title`,
  `_section_02_details_table`, `_section_03_description`,
  `_section_04_planning`, `_section_05_legal`, `_section_06_valuation`,
  `_section_07_tax`, plus `_section_photos` and `_section_notes`),
  along with the three enum→label helpers (`purpose_display`,
  `rights_display`, `finish_desc`).
- **Tests:** `tests/test_golden.py` (added) generates the three demo
  reports (`market`, `standard19`, `evacuation`), extracts the text
  content (paragraphs + table cells) from the docx, and hashes it.
  `pytest >= 8.0.0` added to `requirements.txt`. Goldens were
  baselined before any wiring, then updated once after the
  skill-conflict commit. **All six tests pass.** Sidecar text
  files (`tests/golden_*.txt`) make hash mismatches readable.
- **Character markers:** every snippet carries a
  `<!-- character: fixed | semi | variable -->` line per
  CLAUDE.md A.5. Pure literals → `fixed`; templates with `{var}` →
  `semi`; placeholders for fresh-prose user fields
  (city/neighborhood/air-directions/ceiling) → `variable`.
- **CLAUDE.md updated:** B.6 now describes the loader and points at
  `skills/`; B.7 states the migration is complete; B.10 mentions the
  golden-test suite; C.7 was rewritten ("limited coverage" rather
  than "no tests"); C.8 was removed; old C.9 renumbered to C.8.

## 2. Conflicts (skill wording chosen over code wording)

Per the user's decision rule, every wording difference was resolved
in favor of the skill text. None of the conflicts touched a fact
(percentages, formulas, regulation numbers) — only wording. They are
listed roughly in order of impact on the rendered report.

### 2.1 Section 06 — declarations.scope (high impact)
- Code: `שומה זו הוכנה עבור מזמינה ולמטרתה בלבד. אין היא מהווה תחליף לייעוץ משפטי ואין להסתמך עליה לכל מטרה אחרת.`
- Skill (`skills/06_valuation.md` line 125): adds a third sentence —
  `השימוש בשומה נאסר על כל צד שלישי שהוא, אשר אינו המזמין ועורך השומה לא יהא אחראי להסתמכות כלשהי כאמור.`
- Picked: skill (extra third-party non-reliance sentence appended).

### 2.2 Section 06 — principles.legal.registered (medium)
- Code: `החלקה נרשמה בפנקס הבתים המשותפים, באופן בו כל תת חלקה מהווה יחידה עצמאית.`
- Skill: `החלקה בה ממוקמת הדירה שבנדון נרשמה בפנקס הבתים המשותפים, באופן בו כל תת חלקה מהווה יחידה עצמאית מבחינה משפטית.`
- Picked: skill.

### 2.3 Section 06 — principles.calc.market (medium)
- Code: `הובא בחשבון מצב שוק המקרקעין ומחירי נכסים דומים ורלוונטיים בסביבת הנכס.`
- Skill: `הובא בחשבון מצב שוק המקרקעין ומחירי נכסים דומים ורלוונטיים בסביבת הנכס וסביב המועד הקובע לחוות הדעת.`
- Picked: skill (adds "וסביב המועד הקובע לחוות הדעת").

### 2.4 Section 06 — principles.planning.zoning (medium)
- Code: `בהתאם לתכניות בניין עיר שבתוקף החלקה מסווגת ביעוד '{zoning}'.`
- Skill: `בהתאם לתכניות בניין עיר שבתוקף החלקה בה ממוקמת הדירה שבנדון מסווגת ביעוד '{zoning}'.`
- Picked: skill.

### 2.5 Section 04 — permit.missing (medium)
- Code: `לא אותר היתר הבנייה המקורי של הבניין. יש להשלים.`
- Skill (`skills/04_planning.md` line 61): `לא אותר היתר הבניה המקורי של הבנין.`
- Picked: skill. Two changes — Hebrew spelling (`בנייה`/`בניין` →
  `בניה`/`בנין`) and the trailing `יש להשלים.` reminder is dropped.
  The reminder was a hint to the appraiser; if it is still wanted,
  surface it in the review UI rather than the docx.

### 2.6 Section 04 — permit.entry (low)
- Code: `היתר בנייה מספר X מתאריך Y, אשר התיר Z.`
- Skill: `היתר בניה מספר X מתאריך Y, אשר התיר Z.`
- Picked: skill (spelling).

### 2.7 Section 06 — principles.planning.permit (low)
- Code: `הדירה שבנדון בנויה בהתאם להיתר בנייה משנת X.`
- Skill: `הדירה שבנדון בנויה בהתאם להיתר בניה משנת X.`
- Picked: skill (spelling).

### 2.8 Section 01 — title (cosmetic)
- Code: `חוות דעת — שומת מקרקעין` (em-dash).
- Skill (`skills/01_header.md` lines 24, 39): `חוות דעת - שומת מקרקעין`
  (ASCII hyphen). Note: the skill mixes ASCII hyphen in the title
  example and em-dash elsewhere in the same file; possibly an
  oversight. Picked the title wording verbatim from the skill (hyphen).

## 3. Things noticed but out of scope

These are observations during the migration. **Nothing was changed
on their account** — they are recorded only so the appraiser/owner
can decide whether to act on them.

1. **Skill 06 references unapproved sources.** `skills/06_valuation.md`
   §52-57 lists `yad2` and `madlan` as comparison-data sources, but
   CLAUDE.md C.8 (now renumbered C.8) and `skills/00_index.md` say
   yad2/madlan are not approved (only nadlan.gov.il is). The skill
   prose was not edited; only the snippet-marked blocks below the
   `## Generator snippets` divider are wired into the generator.
2. **Generator-only "יש להשלים" placeholders remain in code.** The
   `_opt(...)` helper still produces literal `[שם השדה]` and the
   demo data falls through to `יש להשלים` strings in the Web flow.
   Per CLAUDE.md A.3 these are intentional sentinels for missing
   data and were left in code rather than promoted into snippets.
   They are user-visible and editable in the docx — that is the
   point. Worth deciding whether the bare `[…]` form should also
   live in skills for consistency.
3. **Skill 03 finish-level wording is described as a list.** The
   skill describes "טובה" and "טובה מאוד" by reference ("כנ"ל +
   תוספות כגון תריסים חשמליים…"). The wired snippets keep the
   generator's prose form (which contains the same items as a
   complete sentence) because the skill does not give a complete
   sentence. If the appraiser wants a different exact phrasing for
   "טובה" / "טובה מאוד", the snippets are
   `finish.basic` / `finish.good` / `finish.luxury` in
   `skills/03_description.md`.
4. **Pre-existing `payload.address` bug in `web.py:235`** (CLAUDE.md
   C.1) was not touched.
5. **`_section_03_description` building summary uses `_opt(...)`
   inside a templated string.** The placeholders that are inserted
   (`[שנת בנייה]`, `[קומות]`, `[יחידות דיור]`) are produced in code
   and rendered into the snippet. Acceptable, but if the placeholder
   exact wording is part of the appraiser's voice, those would
   eventually want their own snippets too.
6. **No CI / pre-commit hook runs `pytest`.** A user-side hook on
   commit would catch unintentional wording drift.
7. **`demo_data.py` was missing the now-required `street_description`
   field** (the model added it but demo wasn't updated). Fixed
   minimally so the golden tests can run. Unrelated to the wiring
   itself but blocked it.

— end of report —
