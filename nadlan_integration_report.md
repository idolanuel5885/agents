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
