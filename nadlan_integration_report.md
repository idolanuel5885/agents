# Nadlan.gov.il comparables integration — implementation report

Date written: 2026-05-07
Branch: `claude/integrate-real-estate-api-8r4gI`

## What was built

A new optional flow in the appraisal Web form lets the appraiser load
recent transactions from `nadlan.gov.il` around the subject property,
review them in a checkbox table, mark outliers, fill in balcony areas
where known, and have the selected rows flow into the report's section 6
comparison table on submit.

| Layer | File | Status |
|---|---|---|
| HTTP client | `real_estate/nadlan_client.py` | new |
| Geocoding | `real_estate/parcel_lookup.py` | added public `geocode` / `to_itm` wrappers |
| Data model | `real_estate/models.py` | added `ComparisonProperty.is_outlier`, `PropertyInput.comparables_fetched_at`, made `balcony_area` `Optional[float]` |
| Web endpoint | `real_estate/web.py` | new `POST /shuma/comparables`; `comparable_*[]` accepted by `/shuma/generate` |
| Form UI | `real_estate/shuma.html` | new "עסקאות השוואה" card between section 07 and 08 |
| Report | `real_estate/report_generator.py` | section 06: outlier marker, dynamic column hiding, source / coefficient / outlier footnotes |
| Snippets | `skills/06_valuation.md` | new `section_06.comparison.footnote.{outlier,balcony_coef,source}` |
| Tests | `tests/test_nadlan_integration.py` | 16 mock tests + 1 skipped live test |

No new dependencies were added — `requests` and `pyproj` were already
installed for `parcel_lookup.py`.

## Live endpoint verification — **not done in sandbox**

The brief asked for a single live call to confirm the endpoint shape.
The sandbox attempted that and failed: every path under
`https://www.nadlan.gov.il/Nadlan.REST/Main/...` returns the SPA
`index.html` (HTTP 200, `content-type: text/html`, served from
S3+CloudFront with `x-cache: Error from cloudfront`). This means the
documented endpoint is not reachable from outside the SPA in this
environment as of 2026-05-07 — it may have been moved, may be served
from a different host now reached only via the SPA's own fetch logic,
or may require a session/cookie I could not produce.

The code is built strictly to the documented payload and response shape
in the brief. **Manual verification after deploying to Railway is
required.** Steps:

1. SSH into the Railway environment (or run locally with the same
   Python deps installed).
2. Run the live curl below. Confirm the response is JSON with an
   `AllResults` array.

```bash
curl -sS -X POST 'https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals' \
  -H 'Content-Type: application/json;charset=UTF-8' \
  -H 'Accept: application/json' \
  -d '{
    "MoreAssestsType": 0,
    "FillterRoomNum": 0,
    "GridDisplayType": 0,
    "ResultLable": "רוטשילד 1, תל אביב",
    "ResultType": 1,
    "ObjectIDType": "text",
    "X": 180555,
    "Y": 663680,
    "QueryMapParams": {"QueryToRun": null, "SpacialWhereClause": null},
    "isHistorical": false,
    "PageNo": 1,
    "OrderByFilled": "DEALDATETIME",
    "OrderByDescending": true,
    "Distance": 300
  }' | head -c 800
```

3. If the response is JSON: confirm the field names used by
   `_to_comparison_property` match
   (`FULLADRESS`, `ASSETROOMNUM`, `FLOORNO`, `DEALNATURE`,
    `DEALAMOUNT`, `DEALDATETIME`, `BUILDINGYEAR`, `NEWPROJECTTEXT`).
4. If the response is HTML (SPA fallback) like in this sandbox:
   open the production site, browse to a property in DevTools'
   Network tab, find the actual fetch call, capture its URL + headers,
   and update `_NADLAN_URL` (and any required headers) in
   `real_estate/nadlan_client.py` accordingly.

Until that verification is done the code is *plumbing-correct*
but unconfirmed against the live service.

## Where mock tests cover the contract

`tests/test_nadlan_integration.py`:

- `test_address_to_itm_*` — geocoding success / failure / blank input.
- `test_fetch_recent_deals_*` — 503/429 → Hebrew `NadlanFetchError`,
  connection error → Hebrew `NadlanFetchError`, malformed JSON →
  Hebrew `NadlanFetchError`, empty `AllResults` → `[]`,
  happy path mapping (`FULLADRESS` → `address`, `DEALNATURE` →
  `built_area`, etc.), missing-field rows dropped (no fabrication),
  `max_results` cap respected.
- `test_comparables_endpoint_*` — `/shuma/comparables` returns HTTP
  200 with `success=false` + Hebrew `message_he` for both
  `GEOCODING_FAILED` and `NADLAN_UNAVAILABLE`; honours explicit
  `itm_x`/`itm_y` (skips geocoding); empty results return
  `success=true` with a "no transactions in radius" message.
- `test_report_renders_outlier_marker_and_hides_balcony_columns` —
  end-to-end: a 3-row report with one outlier and 2/3 missing balcony
  hides the balcony / equiv-area columns and emits the outlier
  footnote and the data-source footnote with the fetched date.

The live probe `test_live_endpoint_smoke` is `pytest.mark.skip`'d with
a message pointing back to this file.

## Known surprises and gotchas

1. **`balcony_area` is now `Optional[float]`.** The previous contract
   was `float` defaulting to `0.0`, but
   `nadlan.gov.il` does not expose a balcony figure and per CLAUDE.md
   A.3 we cannot fabricate one. The dataclass field type changed to
   `Optional[float]`; `equiv_area` was updated to treat `None` the
   same as `<= 0` (no balcony). Existing demo data and CLI form code
   continue to pass plain floats and are unaffected.
2. **Goldens regenerated.** Because the new
   `section_06.comparison.footnote.balcony_coef` paragraph is emitted
   whenever the balcony column is shown (and it is shown in all three
   demos), the section 06 text changed for every demo. `tests/golden.json`
   and `tests/golden_*.txt` were refreshed via `UPDATE_GOLDEN=1`. No
   *unintended* output changes; the diff is exactly the new footnote
   line.
3. **Geocoding helpers re-used, not duplicated.** Per the system
   owner's preference (and CLAUDE.md C.5 — duplicated mappings caused
   drift before), `_geocode` and `_to_itm` from `parcel_lookup.py`
   were re-exported as public `geocode` / `to_itm` and imported by
   `nadlan_client.py`. No standalone `geocoding.py` was introduced.
4. **`ItM` projection always-xy convention.** `to_itm(lat, lon)`
   returns `(x, y)` in metres. `Transformer.from_crs(... always_xy=True)`
   takes `(lon, lat)` order — the wrapper handles the swap so callers
   can keep the natural Hebrew lat/lon mental model.

## Suggested follow-ups (out of scope here)

- **Audit log.** When a comparable is auto-loaded, persist
  `(itm_x, itm_y, radius, fetched_at, count)` to a flat-file log so
  the appraiser can show provenance after-the-fact (CLAUDE.md C.6).
- **Map of comparables.** The brief flagged this as a future task
  and the report still renders the placeholder
  "מפת מיקומי עסקאות ההשוואה: [להוסיף מפה ידנית]".
- **CLI parity.** `real_estate/form.py` (CLI) still has its own
  comparison-property prompts; it has not been updated to use the new
  Nadlan client. Per the brief this was explicitly out of scope.

---

# Iteration 3 — Final solution via Govmap (2026-05)

## What changed

The Iteration 1/2 work above is now **superseded**. The
`Nadlan.REST` endpoint at
`https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals` was
removed by the Ministry of Justice some time before April 2026 and
now returns the SPA `index.html` for every request (the same
behaviour we'd seen from the sandbox). `nadlan_client.py` has been
deleted along with the matching test file.

The replacement is `real_estate/govmap_client.py`, which speaks to
three different endpoints — two on Govmap, one on a new
`api.nadlan.gov.il` host — discovered by combing the production
nadlan.gov.il site's Network tab and cross-referencing the
[`nitzpo/nadlan-mcp`](https://github.com/nitzpo/nadlan-mcp) open-source
MCP server.

## Discovery trail

PoC iterations under `/shuma/poc-test` (see git history; the script
itself has since been removed):

| # | Endpoint | Result |
|---|---|---|
| 1 | `POST /api/search-service/autocomplete` (govmap) | **200 JSON** — autocomplete works server-side, returns `id`, `text`, `shape: "POINT(x y)"` (Web-Mercator). |
| 2 | `GET /api/pages/settlement/buy/{id}.json` (data.nadlan) | 200 — settlement-level metadata only, no per-property deals. |
| 3 | `GET /api/layers-catalog/apps/parcel-search/...` (govmap) | Inconclusive; out of scope. |
| 4 | `GET /api/pages/neighborhood/buy/{id}.json` (data.nadlan) | 200 — neighbourhood metadata, no per-property deals either. |
| 5 | `/api/pages/street/buy/*`, `/api/pages/streets/buy/*` (data.nadlan, guesses) | 403/404 across the board. |
| 6 | `/api/pages/polygon/buy/*`, `/api/pages/address/buy/*`, … | 403/404. |
| 7 | `GET /api/real-estate/deals/(x y)/{radius}` (govmap) | 200 JSON. Works. |
| 8 | `GET /api/real-estate/street-deals/{polygon_id}` (govmap) | **200 JSON, 353 deals for Rothschild** — this is the chosen endpoint. |
| 9 | `POST /api/layers-catalog/entitiesByPoint` (govmap) | Speculative payload; not used. |

Tests 7 and 8 both returned real deal data from Railway; test 8 was
picked because its scope (street polygon) matches the appraiser's
actual question ("comparables on this street") better than a fixed
radius.

The missing step — `addr_id` (from autocomplete) → `polygon_id`
(needed by street-deals) — turned out to be the `api.nadlan.gov.il/deal-info`
endpoint that `nitzpo/nadlan-mcp` documents. A simple
`POST {"base_name": "addr_id", "base_id": "<id>"}` returns the
`polygon_id` for the address.

## Endpoints used today

| Step | Method | URL | Body / params |
|---|---|---|---|
| 1. Autocomplete | POST | `https://www.govmap.gov.il/api/search-service/autocomplete` | `{"searchText": q, "language": "he", "isAccurate": false, "maxResults": 10}` |
| 2. Polygon lookup | POST | `https://api.nadlan.gov.il/deal-info` | `{"base_name": "addr_id", "base_id": "<addr_id>"}` |
| 3. Street deals | GET | `https://www.govmap.gov.il/api/real-estate/street-deals/{polygon_id}` | — |

All three carry `Origin`/`Referer` set to the site they belong to and
a descriptive `User-Agent`. No auth, no key, no quota observed in
testing — but the appraiser only triggers steps 2/3 once per report,
so we are unlikely to be rate-limited even under heavy use.

## Manual verification commands

```bash
# 1. Autocomplete — confirm a single search returns address rows.
curl -s -X POST 'https://www.govmap.gov.il/api/search-service/autocomplete' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://www.govmap.gov.il' \
  -H 'Referer: https://www.govmap.gov.il/' \
  -d '{"searchText":"רוטשילד תל אביב","language":"he","isAccurate":false,"maxResults":10}' \
  | python -m json.tool | head -40

# 2. Polygon lookup — pick an addr_id from above (segment 3 of the
#    pipe-delimited `id` field on a `type:"address"` row).
curl -s -X POST 'https://api.nadlan.gov.il/deal-info' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://www.nadlan.gov.il' \
  -H 'Referer: https://www.nadlan.gov.il/' \
  -d '{"base_name":"addr_id","base_id":"64834989"}'

# 3. Street deals — feed the polygon_id from step 2.
curl -s 'https://www.govmap.gov.il/api/real-estate/street-deals/53292326' \
  -H 'Accept: application/json' \
  -H 'Origin: https://www.govmap.gov.il' \
  -H 'Referer: https://www.govmap.gov.il/' \
  | python -m json.tool | head -40
```

If the live response shape on the production environment differs
from the one assumed by `govmap_client._to_comparison_property` or
`govmap_client._extract_polygon_id`, update those helpers — they are
the only two places the wire-format is interpreted.

---

# Iteration 4 — Final radius-based pipeline (2026-05)

## What changed

Iteration 3 wired a working `autocomplete → deal-info → street-deals`
chain. After live testing, the appraiser discovered the chain only
returns deals from the **single building** the address sits in:
`deal-info`'s `polygon_id` (e.g. `"53292326"`) is parcel-scoped, so
street-deals on that id is essentially "deals on this parcel".

The fix is to drop `deal-info` and use Govmap's
`/real-estate/deals/{x},{y}/{radius}` endpoint instead, which returns
**polygon metadata in a radius** (each polygon corresponds to a
building / parcel block, identified as `"{gushNum}-{parcelNum}"`).
For each polygon we then call `street-deals/{polygon_id}` and merge
the results.

This is the call shape documented by [`nitzpo/nadlan-mcp`](https://github.com/nitzpo/nadlan-mcp)
(`nadlan_mcp/govmap/client.py:274`).

## Discovery trail (PoC 1–13)

| # | What it tried | What we learned |
|---|---|---|
| 1 | `POST search-service/autocomplete` | Works server-side. POINT in EPSG:3857. |
| 2 | `GET pages/settlement/buy/{id}.json` | Settlement-level metadata, no deals. |
| 3 | `apps/parcel-search/...` | Out of scope. |
| 4 | `pages/neighborhood/buy/{id}.json` | Neighborhood metadata, no deals. |
| 5–6 | Various `pages/.../buy/*` paths (street, polygon, address, deals) | 403/404 across the board. |
| 7 | `GET real-estate/deals/(x y)/{radius}` (parens form) | Returned JSON in early run; later returned [] consistently — wrong URL shape. |
| 8 | `GET real-estate/street-deals/{polygon_id}` | Works. Returns `{totalCount, data, …}`. 353 deals for our test polygon. |
| 9 | `POST layers-catalog/entitiesByPoint` | Speculative. Not used. |
| 10 | `deals/(x y)/{radius}` at radii 100/300/500/1000 | All empty — confirmed the `(x y)` URL shape doesn't work. |
| 11 | Tried multiple `polygon_id` field names against `street-deals` | Field is `polygon_id` (snake case) but the polygon endpoint itself was wrong. |
| 12 | **Cloned `nitzpo/nadlan-mcp` and read `client.py:274`** | URL uses **comma**, not space-in-parens. Headers are minimal. Confirmed `deals/{x},{y}/{radius}` returns polygons. |
| 13 | Larger radii + full deal-shape dump | 100m → 16 polygons / 6 streets; 200m → 78 polygons / 17 streets; 500m hits a 100-row server cap. **`streetNameHeb` and `houseNum` are null on the deal payload itself**; they live on the polygon metadata. |

## Final endpoints used

| Step | Method | URL | Notes |
|---|---|---|---|
| 1. Autocomplete | POST | `https://www.govmap.gov.il/api/search-service/autocomplete` | `{searchText, language, isAccurate, maxResults}` |
| 2. Polygons in radius | GET | `https://www.govmap.gov.il/api/real-estate/deals/{x},{y}/{radius}` | Comma between x and y. Returns list of polygon metadata. |
| 3. Deals on a polygon | GET | `https://www.govmap.gov.il/api/real-estate/street-deals/{polygon_id}` | Returns `{totalCount, data, ...}`. |

`api.nadlan.gov.il/deal-info` is **no longer used**.

Headers for all three: `Content-Type: application/json` +
`User-Agent: NadlanMCP/1.0.0`. Nothing else.

## Production wiring

* `find_comparable_deals(x, y, radius_m=200, max_deals=10)` in
  `real_estate/govmap_client.py` is the only entry point.
* Apartment-only filter (`propertyTypeDescription == "דירה"`).
* Top 10 polygons by `dealscount`.
* 0.2 s sleep between sequential street-deals calls.
* Polygon-level address enrichment overrides the deal's null
  `streetNameHeb` / `houseNum`.
* Polygon-level failures swallowed silently (partial success).

## Manual verification commands

```bash
# 1. Autocomplete — pick a result and grab its POINT(x y) coords.
curl -s -X POST 'https://www.govmap.gov.il/api/search-service/autocomplete' \
  -H 'Content-Type: application/json' \
  -H 'User-Agent: NadlanMCP/1.0.0' \
  -d '{"searchText":"רוטשילד 1 תל אביב","language":"he","isAccurate":false,"maxResults":10}' \
  | python -m json.tool | head -30

# 2. Polygons in radius — use the comma form, NOT (x y) with parens.
curl -s 'https://www.govmap.gov.il/api/real-estate/deals/3870469.135,3771587.622/200' \
  -H 'User-Agent: NadlanMCP/1.0.0' \
  | python -m json.tool | head -40

# 3. Deals on a polygon — uses the polygon_id from step 2.
curl -s 'https://www.govmap.gov.il/api/real-estate/street-deals/7422-116' \
  -H 'User-Agent: NadlanMCP/1.0.0' \
  | python -m json.tool | head -40
```

Acceptance: step 2 at radius 200 m around "רוטשילד 1 תל אביב"
should return at least 50 polygons spanning more than 10 distinct
`streetNameHeb`s; step 3 on any of them should return `totalCount` ≥ 1.
