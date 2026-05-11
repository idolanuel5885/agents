"""HTTP client for Govmap and nadlan deal-info APIs.

Three public functions wrap the chain used to pull comparable
transactions from the Israeli government's public real-estate services:

* :func:`autocomplete_address` — Hebrew text → list of candidate
  addresses, each with an ``addr_id`` we can carry forward. Uses
  Govmap's ``search-service/autocomplete`` endpoint.
* :func:`get_polygon_id_for_address` — ``addr_id`` → street polygon id
  via ``api.nadlan.gov.il/deal-info``.
* :func:`get_street_deals` — polygon id → list of recent
  :class:`real_estate.models.ComparisonProperty`. Uses Govmap's
  ``real-estate/street-deals`` endpoint.

All three are wired through :class:`GovmapFetchError` on failure. The
exception carries a Hebrew user-facing ``message_he`` so the Web layer
can render it directly without leaking technical detail (per CLAUDE.md
A.8 "polite failure is mandatory").

Replaces ``nadlan_client.py`` from B.14, which targeted the deprecated
``Nadlan.REST`` endpoint that now returns the SPA HTML. See
``nadlan_integration_report.md`` (Iteration 3) for the discovery trail.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
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

_AUTOCOMPLETE_URL = "https://www.govmap.gov.il/api/search-service/autocomplete"
_DEAL_INFO_URL = "https://api.nadlan.gov.il/deal-info"
_STREET_DEALS_URL_TPL = (
    "https://www.govmap.gov.il/api/real-estate/street-deals/{polygon_id}"
)

_HTTP_TIMEOUT = 15.0
_MIN_QUERY_LEN = 2

_GOVMAP_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.govmap.gov.il",
    "Referer": "https://www.govmap.gov.il/",
    "User-Agent": "Mozilla/5.0 (AlapAppraisalSystem)",
}

_NADLAN_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.nadlan.gov.il",
    "Referer": "https://www.nadlan.gov.il/",
    "User-Agent": "Mozilla/5.0 (AlapAppraisalSystem)",
}

# Shared session so connection pool / TLS handshake is reused.
_session = requests.Session()

# Hebrew floor words → numeric value. Floors above 20 are rare in the
# residential corpus; anything else falls back to 0 and the appraiser
# fills it manually (A.3 — no fabrication).
_HE_FLOOR_TO_INT: dict[str, int] = {
    "קרקע": 0,
    "ראשונה": 1, "שניה": 2, "שנייה": 2, "שלישית": 3, "רביעית": 4,
    "חמישית": 5, "שישית": 6, "שביעית": 7, "שמינית": 8, "תשיעית": 9,
    "עשירית": 10, "אחת עשרה": 11, "שתיים עשרה": 12, "שתים עשרה": 12,
    "שלוש עשרה": 13, "ארבע עשרה": 14, "חמש עשרה": 15, "שש עשרה": 16,
    "שבע עשרה": 17, "שמונה עשרה": 18, "תשע עשרה": 19, "עשרים": 20,
}

_POINT_RE = re.compile(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)")


# ── Exception ────────────────────────────────────────────────────────────────


class GovmapFetchError(Exception):
    """Raised when Govmap or nadlan APIs fail in a recoverable way.

    ``code`` is a stable string the Web layer maps to ``error_code``.
    ``message_he`` is a single Hebrew sentence shown to the appraiser.
    """

    def __init__(self, code: str, message_he: str):
        self.code = code
        self.message_he = message_he
        super().__init__(f"{code}: {message_he}")


# Per-code Hebrew messages — kept centrally so the wording stays
# consistent across the three failure paths.
_HE_ERR = {
    "AUTOCOMPLETE_UNAVAILABLE": (
        "שירות השלמת כתובות לא זמין כרגע. אנא נסה שוב בעוד דקה."
    ),
    "POLYGON_LOOKUP_FAILED": (
        "לא הצלחנו לזהות את הרחוב של הכתובת. "
        "נסה לבחור כתובת אחרת מההצעות."
    ),
    "DEALS_FETCH_FAILED": (
        "שירות עסקאות נדל\"ן לא זמין כרגע. אנא נסה שוב בעוד דקה."
    ),
}


def _raise(code: str) -> None:
    raise GovmapFetchError(code, _HE_ERR[code])


# ── 1. Autocomplete ──────────────────────────────────────────────────────────


def autocomplete_address(query: str) -> list[dict]:
    """Hebrew query → list of candidate locations from Govmap.

    Each returned dict has:
      * ``display_name`` (str) — the human-readable label from Govmap
      * ``type`` (str) — usually ``"address"``, ``"street"`` or ``"poi"``
      * ``itm_x`` (float) — Web-Mercator X parsed from the ``shape`` field
      * ``itm_y`` (float) — Web-Mercator Y
      * ``addr_id`` (str or None) — pipe-segment-3 of the API's ``id``
        field when ``type=="address"``. None for other types (we can
        only run deal-info on a fully-resolved address).

    A query shorter than two chars short-circuits to ``[]`` so we don't
    flood Govmap on every keystroke.

    Raises :class:`GovmapFetchError` with ``code=AUTOCOMPLETE_UNAVAILABLE``
    on any HTTP / parsing failure.
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
        print(f"[GOVMAP DEBUG] autocomplete POST {_AUTOCOMPLETE_URL} query={q!r}", flush=True)

    try:
        resp = _session.post(
            _AUTOCOMPLETE_URL,
            json=payload,
            headers={**_GOVMAP_HEADERS, "Content-Type": "application/json"},
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        if DEBUG_NADLAN:
            print(f"[GOVMAP DEBUG] autocomplete connection error: {type(e).__name__}: {e}", flush=True)
        _raise("AUTOCOMPLETE_UNAVAILABLE")

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] autocomplete status={resp.status_code} ct={resp.headers.get('content-type')}", flush=True)
        print(f"[GOVMAP DEBUG] autocomplete body (first 400 chars): {resp.text[:400]}", flush=True)

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

    shape = raw.get("shape") or ""
    m = _POINT_RE.search(str(shape))
    if not m:
        return None
    try:
        x = float(m.group(1))
        y = float(m.group(2))
    except (TypeError, ValueError):
        return None

    raw_type = (raw.get("type") or "").strip().lower()
    id_str = str(raw.get("id") or "")
    addr_id: Optional[str] = None

    # id format: "address|ADDRESS|64834989|רוטשילד 1|תל אביב"
    # or         "street|STREET_MID_POINT|36595|רוטשילד|תל אביב"
    # We only carry addr_id forward when the third segment looks usable
    # AND the type is address — street/poi rows cannot be passed to
    # deal-info.
    parts = id_str.split("|")
    if raw_type == "address" and len(parts) >= 3 and parts[2].strip():
        addr_id = parts[2].strip()

    return {
        "display_name": (raw.get("text") or "").strip(),
        "type": raw_type or "unknown",
        "itm_x": x,
        "itm_y": y,
        "addr_id": addr_id,
    }


# ── 2. Polygon-id lookup via deal-info ───────────────────────────────────────


def get_polygon_id_for_address(addr_id: str) -> Optional[str]:
    """Return the street polygon id for an address id, or ``None`` if absent.

    Calls ``POST api.nadlan.gov.il/deal-info`` with
    ``{"base_name": "addr_id", "base_id": <addr_id>}`` and extracts
    ``polygon_id`` from the response (the response shape varies by
    address; we try a few common locations).

    Raises :class:`GovmapFetchError` with ``code=POLYGON_LOOKUP_FAILED``
    on network / HTTP / parse failure.
    """
    aid = (addr_id or "").strip()
    if not aid:
        _raise("POLYGON_LOOKUP_FAILED")

    payload = {"base_name": "addr_id", "base_id": aid}

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] deal-info POST {_DEAL_INFO_URL} payload={payload}", flush=True)

    try:
        resp = _session.post(
            _DEAL_INFO_URL,
            json=payload,
            headers={**_NADLAN_HEADERS, "Content-Type": "application/json"},
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        if DEBUG_NADLAN:
            print(f"[GOVMAP DEBUG] deal-info connection error: {type(e).__name__}: {e}", flush=True)
        _raise("POLYGON_LOOKUP_FAILED")

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] deal-info status={resp.status_code}", flush=True)
        print(f"[GOVMAP DEBUG] deal-info body (first 600 chars): {resp.text[:600]}", flush=True)

    if not resp.ok:
        _raise("POLYGON_LOOKUP_FAILED")

    try:
        body = resp.json()
    except ValueError:
        _raise("POLYGON_LOOKUP_FAILED")

    return _extract_polygon_id(body)


def _extract_polygon_id(body) -> Optional[str]:
    """Best-effort extraction of polygon_id from the deal-info response.

    The endpoint's payload isn't formally documented; we look in the
    most likely places. Returning ``None`` is a valid outcome (the
    address has no associated street polygon — e.g. for newly developed
    blocks); the caller treats that as "no comparables available".
    """
    if not isinstance(body, dict):
        return None

    # Direct top-level keys first.
    for key in ("polygon_id", "polygonId", "PolygonId", "POLYGON_ID"):
        v = body.get(key)
        if v:
            return str(v)

    # Nested under a single wrapping object.
    for wrap in ("data", "result", "response"):
        nested = body.get(wrap)
        if isinstance(nested, dict):
            for key in ("polygon_id", "polygonId", "PolygonId", "POLYGON_ID"):
                v = nested.get(key)
                if v:
                    return str(v)

    return None


# ── 3. Street-level deals ────────────────────────────────────────────────────


def get_street_deals(polygon_id: str, limit: int = 10) -> list[ComparisonProperty]:
    """Return up to ``limit`` most-recent deals on a street polygon.

    Sorted by ``dealDate`` descending. Field mapping:

    * ``streetNameHeb`` + " " + ``houseNum`` → ``address``
    * ``assetRoomNum`` → ``rooms``
    * ``floorNo``     → ``floor`` (Hebrew → digit when known; else ``""``)
    * ``assetArea``   → ``built_area``
    * ``None``        → ``balcony_area`` (Govmap doesn't expose this)
    * ``dealAmount``  → ``price``
    * ``dealDate``    → ``notes`` (formatted ``D.M.YYYY``)

    A 200 OK with an empty list returns ``[]`` (not an error). All other
    failures raise :class:`GovmapFetchError` with
    ``code=DEALS_FETCH_FAILED``.
    """
    pid = (polygon_id or "").strip()
    if not pid:
        _raise("DEALS_FETCH_FAILED")

    url = _STREET_DEALS_URL_TPL.format(polygon_id=pid)

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] street-deals GET {url}", flush=True)

    try:
        resp = _session.get(url, headers=_GOVMAP_HEADERS, timeout=_HTTP_TIMEOUT)
    except Exception as e:
        if DEBUG_NADLAN:
            print(f"[GOVMAP DEBUG] street-deals connection error: {type(e).__name__}: {e}", flush=True)
        _raise("DEALS_FETCH_FAILED")

    if DEBUG_NADLAN:
        print(f"[GOVMAP DEBUG] street-deals status={resp.status_code} size={len(resp.content)}", flush=True)

    if not resp.ok:
        _raise("DEALS_FETCH_FAILED")

    try:
        body = resp.json()
    except ValueError:
        _raise("DEALS_FETCH_FAILED")

    raw_deals = _extract_deals_list(body)
    if not raw_deals:
        return []

    # Sort by parsed dealDate descending (None dates sink to the bottom).
    def _sort_key(r):
        d = _parse_iso_date(r.get("dealDate") if isinstance(r, dict) else None)
        # datetime.min as fallback so None sorts last under reverse=True.
        return d or datetime.min

    raw_deals = sorted(raw_deals, key=_sort_key, reverse=True)

    out: list[ComparisonProperty] = []
    for raw in raw_deals:
        cp = _to_comparison_property(raw)
        if cp is not None:
            out.append(cp)
            if len(out) >= limit:
                break
    return out


def _extract_deals_list(body) -> list:
    """The endpoint may wrap the list in a couple of common shapes."""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("deals", "Deals", "results", "data"):
            v = body.get(key)
            if isinstance(v, list):
                return v
    return []


def _to_comparison_property(raw) -> Optional[ComparisonProperty]:
    if not isinstance(raw, dict):
        return None

    price = _coerce_float(raw.get("dealAmount"))
    built_area = _coerce_float(raw.get("assetArea"))
    if price is None or built_area is None or price <= 0 or built_area <= 0:
        return None

    street = (raw.get("streetNameHeb") or "").strip()
    house = str(raw.get("houseNum") or "").strip()
    address = f"{street} {house}".strip()

    rooms = _format_rooms(raw.get("assetRoomNum"))
    floor = _format_floor(raw.get("floorNo"))
    deal_date_str = _format_deal_date(raw.get("dealDate"))

    return ComparisonProperty(
        address=address,
        floor=floor,
        rooms=rooms,
        built_area=built_area,
        balcony_area=None,
        price=price,
        notes=deal_date_str,
        is_outlier=False,
    )


# ── Field-level helpers ──────────────────────────────────────────────────────


def _coerce_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _format_rooms(v) -> str:
    f = _coerce_float(v)
    if f is None:
        return ""
    return f"{f:g}"


def _format_floor(v) -> str:
    """Hebrew floor name → digit string; pass numerics through unchanged.

    Unknown Hebrew strings render as ``""`` so the appraiser sees the
    field is empty and fills it manually. We never invent a number.
    """
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""

    # Numeric already?
    f = _coerce_float(s)
    if f is not None:
        return f"{int(f)}"

    # Hebrew word → digit
    return str(_HE_FLOOR_TO_INT.get(s, ""))


def _parse_iso_date(v) -> Optional[datetime]:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    # Strip trailing Z / fractional seconds: "2015-02-15T00:00:00.000Z"
    s = s.rstrip("Z")
    if "." in s:
        s = s.split(".", 1)[0]
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # Sometimes the API returns just "YYYY-MM-DD".
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _format_deal_date(v) -> str:
    """ISO date → ``D.M.YYYY`` (Israeli convention, not zero-padded)."""
    dt = _parse_iso_date(v)
    if dt is None:
        return ""
    return f"{dt.day}.{dt.month}.{dt.year}"
