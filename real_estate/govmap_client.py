"""HTTP client for Govmap address-autocomplete + deals-by-radius.

Two public functions plus a Hebrew-aware exception:

* :func:`autocomplete_address` — Hebrew text → list of address
  candidates (each with ITM Web-Mercator coords). Uses Govmap's
  ``search-service/autocomplete``.
* :func:`find_comparable_deals` — ITM coords → up to ``max_deals``
  apartment (``דירה``) transactions in radius, enriched with the
  street/house number that comes back on the polygon metadata (the
  per-deal payload has ``streetNameHeb=null``). Pipeline:

    1. ``GET /real-estate/deals/{x},{y}/{radius}`` → polygon metadata.
    2. Keep top 10 polygons by ``dealscount``.
    3. For each polygon, ``GET /real-estate/street-deals/{polygon_id}``.
    4. Filter to ``propertyTypeDescription == "דירה"``.
    5. Attach polygon-level ``streetNameHeb`` / ``houseNum`` onto each
       deal (the deal payload has them null when the polygon is in
       gush-parcel form, e.g. ``"7422-116"``).
    6. Sort by ``dealDate`` desc, take top ``max_deals``.

The shape of the calls (URL comma format, minimal headers) follows the
upstream `nitzpo/nadlan-mcp <https://github.com/nitzpo/nadlan-mcp>`_
project (MIT licensed). Discovery trail: ``nadlan_integration_report.md``
"Iteration 4".

Per CLAUDE.md A.8 "polite failure": :class:`GovmapFetchError` is the
only exception that escapes — it carries a Hebrew ``message_he`` the
Web layer can show directly to the appraiser.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from .models import ComparisonProperty


# ── Debug toggle ─────────────────────────────────────────────────────────────

DEBUG_NADLAN = os.environ.get("DEBUG_NADLAN") == "1"

if DEBUG_NADLAN:
    print(
        f"[GOVMAP DEBUG] module loaded at import; "
        f"DEBUG_NADLAN={DEBUG_NADLAN}",
        flush=True,
    )


# ── Constants ────────────────────────────────────────────────────────────────

_BASE = "https://www.govmap.gov.il/api"
_AUTOCOMPLETE_URL = f"{_BASE}/search-service/autocomplete"
_DEALS_RADIUS_URL_TPL = _BASE + "/real-estate/deals/{x},{y}/{radius}"
_STREET_DEALS_URL_TPL = _BASE + "/real-estate/street-deals/{polygon_id}"

_HTTP_TIMEOUT = 15.0
_MIN_QUERY_LEN = 2

# Cap on how many polygons we drill into per find_comparable_deals call.
# Matches nitzpo's GOVMAP_MAX_POLYGONS=10 default; protects the appraiser
# (and us) from a 200-polygon-radius pulling 200 sequential HTTP calls.
_MAX_POLYGONS = 10

# Polite delay between sequential street-deals calls. With _MAX_POLYGONS=10
# this adds up to ~2 s in the worst case — invisible to the appraiser
# who already expects "טוען..." to take a few seconds.
_STREET_DEALS_DELAY = 0.2

# Apartments only — the same radius may surface stores, parking lots,
# new-build stalls, etc. The appraisal section 6 is specifically for
# residential comparables (A.3 + brief).
_APARTMENT_TYPE = "דירה"

# nitzpo/nadlan-mcp uses only Content-Type + User-Agent. PoC #12 confirmed
# this is enough for both autocomplete and deals-by-radius; the previous
# Origin/Referer/Accept headers (kept for our prior nadlan_client) were
# never actually required and may even have triggered different routing
# at the CDN.
_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "NadlanMCP/1.0.0",
}

_session = requests.Session()
_session.headers.update(_HEADERS)

# Hebrew floor words → numeric value. Floors 0–20 cover ~all of the
# residential corpus; anything else renders as ``""`` and the appraiser
# fills it in (A.3 — no fabrication).
_HE_FLOOR_TO_INT: dict[str, int] = {
    "קומת קרקע": 0,
    "קרקע": 0,
    "אחת": 1, "ראשונה": 1,
    "שתיים": 2, "שתים": 2, "שניה": 2, "שנייה": 2,
    "שלוש": 3, "שלישית": 3,
    "ארבע": 4, "רביעית": 4,
    "חמש": 5, "חמישית": 5,
    "שש": 6, "שישית": 6,
    "שבע": 7, "שביעית": 7,
    "שמונה": 8, "שמינית": 8,
    "תשע": 9, "תשיעית": 9,
    "עשר": 10, "עשירית": 10,
    "אחת עשרה": 11,
    "שתיים עשרה": 12, "שתים עשרה": 12,
    "שלוש עשרה": 13,
    "ארבע עשרה": 14,
    "חמש עשרה": 15,
    "שש עשרה": 16,
    "שבע עשרה": 17,
    "שמונה עשרה": 18,
    "תשע עשרה": 19,
    "עשרים": 20,
}

_POINT_RE = re.compile(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)")


# ── Exception ────────────────────────────────────────────────────────────────


class GovmapFetchError(Exception):
    """Recoverable failure with a Hebrew message for the Web layer.

    ``code`` is a stable string the Web layer surfaces as ``error_code``.
    ``message_he`` is one Hebrew sentence the appraiser sees.
    """

    def __init__(self, code: str, message_he: str):
        self.code = code
        self.message_he = message_he
        super().__init__(f"{code}: {message_he}")


_HE_ERR = {
    "AUTOCOMPLETE_UNAVAILABLE": (
        "שירות השלמת כתובות לא זמין כרגע. אנא נסה שוב בעוד דקה."
    ),
    "POLYGONS_FETCH_FAILED": (
        "שירות עסקאות נדל\"ן לא זמין כרגע. אנא נסה שוב בעוד דקה."
    ),
}


def _raise(code: str) -> None:
    raise GovmapFetchError(code, _HE_ERR[code])


# ── 1. Autocomplete ──────────────────────────────────────────────────────────


def autocomplete_address(query: str) -> list[dict]:
    """Hebrew query → list of address candidates.

    Each result dict has:
      * ``display_name`` (str) — the human-readable label.
      * ``type`` (str) — usually ``"address"``, ``"street"``, ``"poi"``.
      * ``itm_x`` / ``itm_y`` (float) — Web-Mercator EPSG:3857 from the
        ``shape: "POINT(x y)"`` field.
      * ``addr_id`` (str or None) — pipe-segment 3 of the API's ``id``
        when type is address; carried in the response for forward-compat
        even though the new pipeline doesn't need it.

    Queries shorter than 2 chars short-circuit to ``[]``. Network /
    parse failures raise ``GovmapFetchError(AUTOCOMPLETE_UNAVAILABLE)``.
    """
    q = (query or "").strip()
    if len(q) < _MIN_QUERY_LEN:
        return []

    payload = {
        "searchText": q,
        "language": "he",
        "isAccurate": False,
        "maxResults": 10,
    }

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] autocomplete POST query={q!r}", flush=True)

    try:
        resp = _session.post(_AUTOCOMPLETE_URL, json=payload, timeout=_HTTP_TIMEOUT)
    except Exception as e:
        if DEBUG_NADLAN:
            print(f"[GOVMAP DEBUG] autocomplete connection error: {type(e).__name__}: {e}", flush=True)
        _raise("AUTOCOMPLETE_UNAVAILABLE")

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] autocomplete status={resp.status_code}", flush=True)

    if not resp.ok:
        _raise("AUTOCOMPLETE_UNAVAILABLE")

    try:
        body = resp.json()
    except ValueError:
        _raise("AUTOCOMPLETE_UNAVAILABLE")

    raw_results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(raw_results, list):
        return []

    out: list[dict] = []
    for raw in raw_results:
        parsed = _parse_autocomplete_result(raw)
        if parsed is not None:
            out.append(parsed)
    return out


def _parse_autocomplete_result(raw) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None

    m = _POINT_RE.search(str(raw.get("shape") or ""))
    if not m:
        return None
    try:
        x = float(m.group(1))
        y = float(m.group(2))
    except (TypeError, ValueError):
        return None

    raw_type = (raw.get("type") or "").strip().lower()

    addr_id: Optional[str] = None
    parts = str(raw.get("id") or "").split("|")
    if raw_type == "address" and len(parts) >= 3 and parts[2].strip():
        addr_id = parts[2].strip()

    return {
        "display_name": (raw.get("text") or "").strip(),
        "type": raw_type or "unknown",
        "itm_x": x,
        "itm_y": y,
        "addr_id": addr_id,
    }


# ── 2. Radius-based deals pipeline ───────────────────────────────────────────


def find_comparable_deals(
    point_x: float,
    point_y: float,
    radius_m: int = 200,
    max_deals: int = 10,
) -> list[ComparisonProperty]:
    """Return up to ``max_deals`` apartment deals around an ITM point.

    Multi-step pipeline (see module docstring for the rationale).
    Polygon-level failures are swallowed silently (partial success — one
    flaky polygon shouldn't blank the whole table). The radius query
    itself is the only step whose HTTP failure raises
    ``GovmapFetchError(POLYGONS_FETCH_FAILED)``; an empty radius result
    is a valid answer that returns ``[]``.
    """
    polygons = _fetch_polygons_in_radius(point_x, point_y, radius_m)
    if not polygons:
        return []

    # Pick the polygons with the most deals — best signal that an area
    # has real residential turnover, vs. an industrial polygon with one
    # historical transaction.
    polygons = sorted(
        polygons,
        key=lambda p: _coerce_int(p.get("dealscount")) or 0,
        reverse=True,
    )[:_MAX_POLYGONS]

    pairs: list[tuple[Optional[datetime], ComparisonProperty]] = []

    for idx, poly in enumerate(polygons):
        polygon_id = poly.get("polygon_id")
        if not polygon_id:
            continue

        if idx > 0:
            time.sleep(_STREET_DEALS_DELAY)

        street_name = poly.get("streetNameHeb") or ""
        house_num = poly.get("houseNum") or ""

        deals = _fetch_street_deals(polygon_id)
        if not deals:
            continue

        for raw_deal in deals:
            if not isinstance(raw_deal, dict):
                continue
            if raw_deal.get("propertyTypeDescription") != _APARTMENT_TYPE:
                continue
            mapped = _deal_to_comparison_property(
                raw_deal,
                street_override=street_name,
                house_override=house_num,
            )
            if mapped is None:
                continue
            sort_dt = _parse_iso_date(raw_deal.get("dealDate"))
            pairs.append((sort_dt, mapped))

    # Sort by date desc; None dates go to the bottom.
    pairs.sort(key=lambda p: p[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return [cp for _, cp in pairs[:max_deals]]


def _fetch_polygons_in_radius(x: float, y: float, radius: int) -> list[dict]:
    """Step 1 of the pipeline. Empty list is a valid answer (no deals)."""
    url = _DEALS_RADIUS_URL_TPL.format(x=x, y=y, radius=int(radius))

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] deals-by-radius GET {url}", flush=True)

    try:
        resp = _session.get(url, timeout=_HTTP_TIMEOUT)
    except Exception as e:
        if DEBUG_NADLAN:
            print(f"[GOVMAP DEBUG] deals-by-radius connection error: {type(e).__name__}: {e}", flush=True)
        _raise("POLYGONS_FETCH_FAILED")

    if DEBUG_NADLAN:
        print(
            f"[GOVMAP DEBUG] deals-by-radius status={resp.status_code} "
            f"size={len(resp.content)}",
            flush=True,
        )

    if not resp.ok:
        _raise("POLYGONS_FETCH_FAILED")

    try:
        body = resp.json()
    except ValueError:
        _raise("POLYGONS_FETCH_FAILED")

    return body if isinstance(body, list) else []


def _fetch_street_deals(polygon_id: str) -> list[dict]:
    """Step 3 of the pipeline. Silent on failure — partial success."""
    url = _STREET_DEALS_URL_TPL.format(polygon_id=polygon_id)

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] street-deals GET {url}", flush=True)

    try:
        resp = _session.get(url, timeout=_HTTP_TIMEOUT)
    except Exception as e:
        if DEBUG_NADLAN:
            print(f"[GOVMAP DEBUG] street-deals connection error: {type(e).__name__}: {e}", flush=True)
        return []

    if not resp.ok:
        return []

    try:
        body = resp.json()
    except ValueError:
        return []

    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            return data
    return []


# ── Field-level helpers ──────────────────────────────────────────────────────


def _deal_to_comparison_property(
    deal: dict,
    *,
    street_override: str = "",
    house_override: str = "",
) -> Optional[ComparisonProperty]:
    """Map one Govmap deal dict to a ``ComparisonProperty`` row.

    Address-side: per Test 13b the deal payload itself has
    ``streetNameHeb=null`` and ``houseNum=null`` when ``polygon_id`` is
    in gush-parcel form ("7422-116"). We therefore prefer the polygon
    metadata's address fields, falling back to the deal's only if the
    polygon ones were empty. The deal's ``neighborhood`` is appended
    when neither street nor polygon yielded an address (so the row is
    at least geographically situated rather than fully blank).
    """
    price = _coerce_float(deal.get("dealAmount"))
    built_area = _coerce_float(deal.get("assetArea"))
    if price is None or built_area is None or price <= 0 or built_area <= 0:
        return None

    street = (street_override or deal.get("streetNameHeb") or "").strip()
    house_raw = house_override if house_override else deal.get("houseNum")
    house = str(house_raw).strip() if house_raw not in (None, "", "0") else ""

    if street:
        address = f"{street} {house}".strip()
    else:
        # Fall back to neighborhood + settlement so the row isn't blank.
        neighborhood = (deal.get("neighborhood") or "").strip()
        settlement = (deal.get("settlementNameHeb") or "").strip()
        parts = [p for p in (neighborhood, settlement) if p]
        address = ", ".join(parts) if parts else ""

    return ComparisonProperty(
        address=address,
        floor=_format_floor(deal.get("floorNo")),
        rooms=_format_rooms(deal.get("assetRoomNum")),
        built_area=built_area,
        balcony_area=None,
        price=price,
        notes=_format_deal_date(deal.get("dealDate")),
        is_outlier=False,
    )


def _coerce_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _coerce_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v)))
    except (TypeError, ValueError):
        return None


def _format_rooms(v) -> str:
    f = _coerce_float(v)
    if f is None or f <= 0:
        return ""
    # Govmap returns 3.0 / 3.5 etc — drop trailing .0 for table tidiness.
    return f"{f:g}"


def _format_floor(v) -> str:
    """Govmap returns Hebrew words like ``"עשרים"`` or sometimes an int.

    Returns the digit as a string when known, ``""`` otherwise (the
    appraiser fills it manually — never fabricated).
    """
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""

    f = _coerce_float(s)
    if f is not None:
        return f"{int(f)}"

    return str(_HE_FLOOR_TO_INT.get(s, ""))


def _parse_iso_date(v) -> Optional[datetime]:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    # Strip "Z" / fractional seconds: "2024-06-19T00:00:00.000Z"
    s = s.replace("Z", "+00:00")
    if "." in s:
        head, tail = s.split(".", 1)
        # Re-attach any TZ that lived past the fractional seconds.
        plus_idx = tail.find("+")
        minus_idx = tail.find("-")
        idx = next((i for i in (plus_idx, minus_idx) if i >= 0), -1)
        s = head + (tail[idx:] if idx >= 0 else "")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _format_deal_date(v) -> str:
    """ISO 8601 → ``D.M.YYYY`` (Israeli convention, not zero-padded)."""
    dt = _parse_iso_date(v)
    if dt is None:
        return ""
    return f"{dt.day}.{dt.month}.{dt.year}"
