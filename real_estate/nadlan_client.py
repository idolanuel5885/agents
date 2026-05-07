"""HTTP client for the public nadlan.gov.il transactions API.

The Israeli Ministry of Justice publishes transaction data through the
unofficial-but-public ``Nadlan.REST`` endpoint at
``https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals``. The API
expects a point in Israeli Transverse Mercator (EPSG:2039) coordinates and
a search radius in metres, and returns a paged list of transactions
sorted by deal date.

This module exposes :func:`fetch_recent_deals` which:

* sends one POST against the endpoint,
* parses up to ``max_results`` transactions out of the response,
* maps each transaction to a :class:`real_estate.models.ComparisonProperty`,
* and raises :class:`NadlanFetchError` (with a Hebrew-readable message)
  on any network / parsing / quota failure.

Per CLAUDE.md A.8 ("polite failure is mandatory") the caller is expected
to catch the exception and surface the Hebrew message to the appraiser
without ever leaking a stack trace to the UI.

Geocoding (Hebrew address → ITM) is delegated to the helpers re-exported
from :mod:`real_estate.parcel_lookup` so we don't keep two parallel
copies of the Nominatim + ``pyproj`` pipeline (per CLAUDE.md C.5 — drift
between duplicated mappings already burned us once).
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

from .models import ComparisonProperty
from .parcel_lookup import geocode, to_itm

logger = logging.getLogger(__name__)

# Temporary diagnostic toggle. Set DEBUG_NADLAN=1 in Railway to dump the
# raw request/response of every fetch_recent_deals call to stdout so we
# can see what nadlan.gov.il actually returned (the /shuma/comparables
# endpoint always returns HTTP 200 to the form, which hides the truth).
# Uses print(flush=True) instead of the logger because uvicorn on
# Railway sometimes swallows logger.info but always forwards prints.
DEBUG_NADLAN = os.environ.get("DEBUG_NADLAN") == "1"


# ── Constants ────────────────────────────────────────────────────────────────

_NADLAN_URL = (
    "https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals"
)

# 15 s is the upper bound the brief asks for. The endpoint sometimes
# answers in 4-6 s under load; 15 s leaves headroom without locking the
# form for too long.
_HTTP_TIMEOUT = 15.0

# Polite delay between successive calls (the brief asks for 0.5 s, and
# the endpoint occasionally returns 429 under bursts).
_INTER_REQUEST_DELAY = 0.5
_last_request_at: float = 0.0

# Up to N transactions returned per call. The form table is fixed at 10
# rows so the appraiser doesn't drown in irrelevant data.
_MAX_RESULTS_DEFAULT = 10


# ── Public exception ─────────────────────────────────────────────────────────


class NadlanFetchError(RuntimeError):
    """Raised when the nadlan.gov.il call cannot complete.

    The argument is a Hebrew sentence the Web layer can show directly to
    the appraiser. Never construct this with a stack trace or English
    technical detail.
    """


# ── Public helper: address → ITM ─────────────────────────────────────────────


def address_to_itm(address: str) -> Optional[tuple[float, float]]:
    """Hebrew address → (itm_x, itm_y) or ``None`` on any failure.

    Wraps the two-step pipeline (Nominatim geocoding → WGS84/ITM
    projection) into a single best-effort call. Per CLAUDE.md A.8 this
    function never raises — failures are signalled by ``None`` so the
    caller can ask the appraiser to enter coordinates manually.

    Includes the Nominatim 1 req/s rate-limit sleep so callers don't
    have to remember it.
    """
    addr = (address or "").strip()
    if not addr:
        return None

    _rate_limit()

    coords = geocode(addr)
    if coords is None:
        return None

    lat, lon = coords
    try:
        return to_itm(lat, lon)
    except Exception:
        # to_itm only fails when pyproj is missing (very unusual in
        # production) — degrade gracefully rather than surface the
        # ImportError to the appraiser.
        logger.exception("address_to_itm: ITM projection failed")
        return None


# ── Public helper: fetch transactions ────────────────────────────────────────


def fetch_recent_deals(
    itm_x: float,
    itm_y: float,
    radius_m: int,
    address_label: str = "",
    max_results: int = _MAX_RESULTS_DEFAULT,
) -> list[ComparisonProperty]:
    """Return up to ``max_results`` recent transactions around (itm_x, itm_y).

    Sorted by deal date descending (the API does this server-side via
    ``OrderByFilled=DEALDATETIME`` + ``OrderByDescending=true``).

    ``balcony_area`` is intentionally left as ``None`` on every returned
    record because the API does not expose a balcony field — the
    appraiser fills it manually in the form. Per CLAUDE.md A.3 we never
    invent values that aren't in the source.

    Raises :class:`NadlanFetchError` with a Hebrew-readable message on
    any failure (network, HTTP error, JSON shape change).
    """
    try:
        import requests
    except ImportError as e:
        raise NadlanFetchError(
            f"חבילת requests אינה מותקנת: {e}"
        ) from e

    payload = {
        "MoreAssestsType": 0,
        "FillterRoomNum": 0,
        "GridDisplayType": 0,
        "ResultLable": address_label or "",
        "ResultType": 1,
        "ObjectIDType": "text",
        "X": float(itm_x),
        "Y": float(itm_y),
        "QueryMapParams": {
            "QueryToRun": None,
            "SpacialWhereClause": None,
        },
        "isHistorical": False,
        "PageNo": 1,
        "OrderByFilled": "DEALDATETIME",
        "OrderByDescending": True,
        "Distance": int(radius_m),
    }
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
    }

    _rate_limit()

    if DEBUG_NADLAN:
        print(f"[NADLAN DEBUG] Request URL: {_NADLAN_URL}", flush=True)
        print(f"[NADLAN DEBUG] Request payload: {json.dumps(payload, ensure_ascii=False)}", flush=True)
        print(f"[NADLAN DEBUG] Request headers: {dict(headers)}", flush=True)

    try:
        resp = requests.post(
            _NADLAN_URL,
            json=payload,
            headers=headers,
            timeout=_HTTP_TIMEOUT,
        )
    except Exception as e:
        # Connection error, DNS, TLS, timeout — anything below HTTP.
        if DEBUG_NADLAN:
            print(f"[NADLAN DEBUG] Request raised before response: {type(e).__name__}: {e}", flush=True)
        raise NadlanFetchError(
            "שירות נדל\"ן.gov.il לא זמין כרגע. אנא הזן עסקאות ידנית "
            "או נסה שוב בעוד דקה."
        ) from e

    if DEBUG_NADLAN:
        print(f"[NADLAN DEBUG] Response status: {resp.status_code}", flush=True)
        print(f"[NADLAN DEBUG] Response headers: {dict(resp.headers)}", flush=True)
        print(f"[NADLAN DEBUG] Response final URL: {resp.url}", flush=True)
        print(f"[NADLAN DEBUG] Response Content-Type: {resp.headers.get('content-type')}", flush=True)
        print(f"[NADLAN DEBUG] Response body (first 800 chars): {resp.text[:800]}", flush=True)

    if resp.status_code in (429, 503):
        raise NadlanFetchError(
            "שירות נדל\"ן.gov.il לא זמין כרגע, נסה שוב בעוד דקה."
        )
    if not resp.ok:
        raise NadlanFetchError(
            f"שירות נדל\"ן.gov.il החזיר שגיאה (HTTP {resp.status_code}). "
            "אנא נסה שוב בעוד דקה."
        )

    try:
        body = resp.json()
    except ValueError as e:
        raise NadlanFetchError(
            "תשובת נדל\"ן.gov.il לא הוחזרה בפורמט צפוי."
        ) from e

    raw_deals = _extract_results(body)
    deals = []
    for raw in raw_deals[:max_results]:
        cp = _to_comparison_property(raw)
        if cp is not None:
            deals.append(cp)
    return deals


# ── Internals ────────────────────────────────────────────────────────────────


def _rate_limit() -> None:
    """Sleep just long enough to respect the inter-request delay.

    Uses module-level state — this is a single-process FastAPI server,
    so a process-local minimum interval is sufficient.
    """
    global _last_request_at
    now = time.monotonic()
    wait = _INTER_REQUEST_DELAY - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _extract_results(body) -> list[dict]:
    """Locate the transaction list inside the API response.

    The endpoint historically returns ``{"AllResults": [...]}``. Older
    snapshots have used ``ResultSet`` or ``Data``; we try a small set of
    known keys before giving up. An empty list is a normal answer
    (no transactions in radius) and is returned as ``[]`` not an error.
    """
    if not isinstance(body, dict):
        return []
    for key in ("AllResults", "ResultSet", "Data", "data"):
        val = body.get(key)
        if isinstance(val, list):
            return val
    return []


def _to_comparison_property(raw: dict) -> Optional[ComparisonProperty]:
    """Map one raw transaction dict to :class:`ComparisonProperty`.

    Returns ``None`` when a transaction is missing the bare-minimum
    fields required for a comparable row (price + area). All other
    fields degrade to empty / ``None`` per the no-fabrication rule.
    """
    if not isinstance(raw, dict):
        return None

    price = _coerce_float(raw.get("DEALAMOUNT"))
    built_area = _coerce_float(raw.get("DEALNATURE"))
    if price is None or built_area is None or price <= 0 or built_area <= 0:
        return None

    rooms = _format_rooms(raw.get("ASSETROOMNUM"))
    floor = _format_floor(raw.get("FLOORNO"))
    address = (raw.get("FULLADRESS") or "").strip()
    notes = _format_notes(raw)

    return ComparisonProperty(
        address=address,
        floor=floor,
        rooms=rooms,
        built_area=built_area,
        balcony_area=None,  # API does not expose a balcony field
        price=price,
        notes=notes,
        is_outlier=False,
    )


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
    # API returns 4.0, 3.5 etc. Drop trailing .0 for tidier table cells.
    return f"{f:g}"


def _format_floor(v) -> str:
    """Normalise a floor value into the short string shape used elsewhere.

    The table column is ``str``; CLI input writes ``"קומה N"`` while the
    API returns just an integer. We keep a bare integer string so the
    column stays narrow; the appraiser can edit it if they want.
    """
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    # If the API ever returns "קומה N" already, pass it through.
    if s.startswith("קומה"):
        return s
    f = _coerce_float(s)
    if f is None:
        return s
    return f"{int(f)}"


def _format_notes(raw: dict) -> str:
    """Build the freeform notes column from the secondary fields.

    Order: deal date · build year · contractor flag. Each component is
    optional; we only join those that the API actually returned, so
    nothing is fabricated when a field is empty.
    """
    parts: list[str] = []

    deal_date = _format_deal_date(raw.get("DEALDATETIME") or raw.get("DEALDATE"))
    if deal_date:
        parts.append(deal_date)

    build_year = raw.get("BUILDINGYEAR")
    if build_year:
        # Some payloads return "1995" as a string, others as int.
        s = str(build_year).strip()
        if s and s != "0":
            parts.append(f"שנת בנייה {s}")

    if _is_contractor_deal(raw):
        parts.append("עסקת קבלן")

    return ", ".join(parts)


def _format_deal_date(v) -> str:
    """Convert the API's deal date to a short DD.MM.YYYY string.

    The endpoint returns either ``"2025-02-11T00:00:00"`` (ISO) or
    ``"11/02/2025"``. We normalise to ``DD.MM.YYYY`` for the report;
    when the format is unrecognised the value is dropped (no
    fabrication).
    """
    if not v:
        return ""
    s = str(v).strip()
    # ISO: "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DD"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        y, m, d = s[:4], s[5:7], s[8:10]
        if y.isdigit() and m.isdigit() and d.isdigit():
            return f"{d}.{m}.{y}"
    # DD/MM/YYYY
    if len(s) >= 10 and s[2] == "/" and s[5] == "/":
        return s[:10].replace("/", ".")
    return ""


def _is_contractor_deal(raw: dict) -> bool:
    """Best-effort detection of a developer-sold (קבלן) transaction."""
    txt = raw.get("NEWPROJECTTEXT")
    if isinstance(txt, str) and txt.strip():
        return True
    flag = raw.get("ISNEWPROJECT")
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, (int, float)):
        return flag != 0
    return False


