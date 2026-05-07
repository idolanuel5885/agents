"""FastAPI router — serves the web form and handles report generation."""
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from typing import List

from .models import (
    PropertyInput, ReportPurpose, RightsType, FinishLevel,
    PermitStatus, ClientGender, ComparisonProperty,
)
from .report_generator import generate_report_bytes
from . import claude_descriptions
from . import parcel_lookup
from . import nadlan_client

import logging

logger = logging.getLogger(__name__)

def _bool(v: str) -> bool:
    return str(v).lower() in ("true", "1", "on", "yes")

router = APIRouter(prefix="/shuma", tags=["shuma"])

_FORM_HTML = (Path(__file__).parent / "shuma.html").read_text(encoding="utf-8")

_HE_MONTHS = [
    "", "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
]


def _today_str() -> str:
    return date.today().strftime("%d/%m/%Y")


def _today_hebrew() -> str:
    d = date.today()
    return f"{d.day} ב{_HE_MONTHS[d.month]} {d.year}"


def _parse_address(address: str):
    """Best-effort split of 'רחוב X N, CITY' → (city, street, house_num)."""
    m = re.match(r"(?:רחוב\s+)?(.+?)\s+(\d+[א-תA-Za-z]?)\s*,\s*(.+)$",
                 address.strip())
    if m:
        return m.group(3).strip(), m.group(1).strip(), m.group(2).strip()
    parts = address.rsplit(",", 1)
    return (parts[-1].strip() if len(parts) > 1 else address), "", ""


def _date_html_to_display(d: str) -> str:
    """Convert 'YYYY-MM-DD' → 'DD/MM/YYYY', pass through other formats."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", d.strip())
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else d


def _f(v: Any, default=0.0) -> float:
    try:
        return float(str(v).replace(",", "")) if v not in ("", None) else default
    except (ValueError, TypeError):
        return default


def _i(v: Any, default=0) -> int:
    return int(_f(v, default))


# ── Form endpoint ─────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def get_form():
    return _FORM_HTML


# ── Parcel lookup endpoint ────────────────────────────────────────────────────


@router.post("/lookup-parcel")
async def lookup_parcel_endpoint(address: str = Form(...)):
    """Best-effort parcel + planning data lookup for an address.

    Returns JSON shaped like ``ParcelLookupResult.to_dict()``. The
    handler never raises — even on failure it returns ``ok=false`` with
    a Hebrew ``error`` so the form can show the reason and let the
    appraiser keep filling manually.
    """
    try:
        result = parcel_lookup.lookup_parcel(address)
    except Exception as e:
        logger.exception("parcel_lookup raised unexpectedly")
        return {
            "ok": False,
            "block": "",
            "parcel": "",
            "land_use": "",
            "plans": [],
            "boundaries": {"north": "", "south": "", "east": "", "west": ""},
            "warnings": [],
            "error": f"שגיאה לא צפויה בבדיקת הנתונים: {e}",
        }
    return result.to_dict()


# ── PoC endpoint (temporary) ──────────────────────────────────────────────────
# Probes the new endpoints discovered in nadlan.gov.il's Network tab to
# learn whether Railway can reach them at all and what they return.
# Removed once we know the answer. Returns text/plain so the result is
# readable in a browser without devtools. See tests/poc_new_endpoints.py.


@router.get("/poc-test", response_class=Response)
async def poc_test_endpoint():
    from tests.poc_new_endpoints import run_poc
    return Response(content=run_poc(), media_type="text/plain; charset=utf-8")


# ── Comparable transactions endpoint ──────────────────────────────────────────
class _ComparablesRequest(BaseModel):
    """Body for ``POST /shuma/comparables``.

    Either ``address`` (geocoded server-side) or ``itm_x``+``itm_y`` are
    required. ``itm_x``/``itm_y`` win if both are provided so the
    appraiser can override a wrong geocoding result by entering ITM
    coordinates manually.
    """
    address: str = ""
    radius_m: int = 300
    itm_x: Optional[float] = None
    itm_y: Optional[float] = None


def _serialise_deal(cp: ComparisonProperty) -> dict:
    return {
        "address": cp.address,
        "rooms": cp.rooms,
        "floor": cp.floor,
        "built_area": cp.built_area,
        "balcony_area": cp.balcony_area,
        "price": cp.price,
        "notes": cp.notes,
    }


@router.post("/comparables")
async def comparables_endpoint(req: _ComparablesRequest):
    """Best-effort fetch of recent transactions around a coordinate.

    The handler never returns 5xx — every failure path emits HTTP 200
    with ``success=false`` plus a Hebrew ``message_he`` so the form can
    show the user a sentence they can act on (per CLAUDE.md A.8).
    """
    # Unconditional entry print: prove the endpoint was reached at all.
    # Even with DEBUG_NADLAN=0 this single line per click gives us "yes,
    # the request hit the server" without spamming the logs.
    print(
        f"[NADLAN DEBUG] /shuma/comparables ENTERED "
        f"address={req.address!r} radius={req.radius_m} "
        f"itm=({req.itm_x},{req.itm_y})",
        flush=True,
    )

    radius = max(50, min(int(req.radius_m or 300), 5000))

    if req.itm_x is not None and req.itm_y is not None:
        itm_x, itm_y = float(req.itm_x), float(req.itm_y)
    else:
        coords = nadlan_client.address_to_itm(req.address)
        if coords is None:
            print(
                "[NADLAN DEBUG] /shuma/comparables → GEOCODING_FAILED "
                "(address_to_itm returned None)",
                flush=True,
            )
            return {
                "success": False,
                "error_code": "GEOCODING_FAILED",
                "message_he": (
                    "לא הצלחנו לזהות את הכתובת. אנא הזן גוש/חלקה או "
                    "קואורדינטות ידנית."
                ),
            }
        itm_x, itm_y = coords

    try:
        deals = nadlan_client.fetch_recent_deals(
            itm_x, itm_y, radius, address_label=(req.address or "").strip(),
        )
    except nadlan_client.NadlanFetchError as e:
        return {
            "success": False,
            "error_code": "NADLAN_UNAVAILABLE",
            "message_he": str(e),
        }
    except Exception as e:
        logger.exception("nadlan fetch raised unexpectedly")
        return {
            "success": False,
            "error_code": "NADLAN_UNAVAILABLE",
            "message_he": (
                "שירות נדל\"ן.gov.il לא זמין כרגע. אנא הזן עסקאות ידנית "
                "או נסה שוב בעוד דקה."
            ),
        }

    if not deals:
        return {
            "success": True,
            "deals": [],
            "fetched_at": date.today().isoformat(),
            "source": "nadlan.gov.il",
            "message_he": "לא נמצאו עסקאות ברדיוס שבחרת. נסה להגדיל את הרדיוס.",
        }

    return {
        "success": True,
        "deals": [_serialise_deal(d) for d in deals],
        "fetched_at": date.today().isoformat(),
        "source": "nadlan.gov.il",
    }


# ── Generation endpoint ───────────────────────────────────────────────────────

def _build_comparables(
    addresses: List[str],
    rooms: List[str],
    floors: List[str],
    built_areas: List[str],
    balcony_areas: List[str],
    prices: List[str],
    notes_: List[str],
    outliers: List[str],
) -> List[ComparisonProperty]:
    """Zip parallel ``comparable_*[]`` form arrays into ``ComparisonProperty`` rows.

    The form only sends rows the appraiser kept ticked, so an empty
    ``addresses`` list means "no comparables this report" — return ``[]``
    rather than synthesising rows. ``balcony_area`` stays ``None`` when
    blank; A.3 forbids fabricating zero where the source has nothing.
    """
    n = len(addresses)
    if n == 0:
        return []

    def _at(arr: List[str], i: int, default: str = "") -> str:
        return arr[i] if i < len(arr) else default

    out: List[ComparisonProperty] = []
    for i in range(n):
        built = _f(_at(built_areas, i), 0.0)
        price = _f(_at(prices, i), 0.0)
        if built <= 0 or price <= 0:
            # No usable area or price → skip rather than render a junk row.
            continue
        balcony_raw = _at(balcony_areas, i).strip()
        balcony: Optional[float] = (
            _f(balcony_raw) if balcony_raw not in ("", "None") else None
        )
        if balcony is not None and balcony <= 0:
            balcony = None
        out.append(
            ComparisonProperty(
                address=_at(addresses, i).strip(),
                floor=_at(floors, i).strip(),
                rooms=_at(rooms, i).strip(),
                built_area=built,
                balcony_area=balcony,
                price=price,
                notes=_at(notes_, i).strip(),
                is_outlier=_bool(_at(outliers, i, "false")),
            )
        )
    return out


_PURPOSE_MAP = {
    "שוק": ReportPurpose.MARKET,
    "תקן_19": ReportPurpose.STANDARD_19,
    "פינוי_בינוי": ReportPurpose.EVACUATION,
}
_RIGHTS_MAP = {
    "בעלות_פרטית": RightsType.PRIVATE,
    "חכירה_רמי": RightsType.LEASE_RAMI,
    "חכירה_חברה": RightsType.LEASE_COMPANY,
}
_GENDER_MAP = {
    "זכר": ClientGender.MALE,
    "נקבה": ClientGender.FEMALE,
    "חברה": ClientGender.COMPANY,
    "בנק": ClientGender.BANK,
}
_FINISH_MAP = {
    "בסיסית": FinishLevel.BASIC,
    "טובה": FinishLevel.GOOD,
    "טובה מאוד": FinishLevel.VERY_GOOD,
}


@router.post("/generate")
async def generate(
    purpose: str = Form(...),
    rights_type: str = Form(...),
    client_gender: str = Form(...),
    client_name: str = Form(...),
    address: str = Form(...),
    block: str = Form(...),
    parcel: str = Form(...),
    sub_parcel: str = Form(...),
    rooms: str = Form(...),
    floor: str = Form(...),
    registered_area: str = Form(...),
    built_area: str = Form(...),
    final_value: str = Form(...),
    air_directions: str = Form(""),
    build_year: str = Form(""),
    total_floors: str = Form(""),
    units_count: str = Form(""),
    ceiling_height: str = Form(""),
    balcony_area: str = Form(""),
    finish_level: str = Form(""),
    has_parking: str = Form("false"),
    has_storage: str = Form("false"),
    has_garden: str = Form("false"),
    tenant_name: str = Form(""),
    monthly_rent: str = Form(""),
    rental_end_date: str = Form(""),
    purchase_date: str = Form(""),
    purchase_price: str = Form(""),
    notes: str = Form(""),
    street_description: str = Form(""),
    city_description: str = Form(""),
    neighborhood_name: str = Form(""),
    neighborhood_description: str = Form(""),
    land_use: str = Form(""),
    north_boundary: str = Form(""),
    south_boundary: str = Form(""),
    east_boundary: str = Form(""),
    west_boundary: str = Form(""),
    property_images: List[UploadFile] = File([]),
    plan_docs: List[UploadFile] = File([]),
    plan_types: List[str] = Form([]),
    comparable_address: List[str] = Form([]),
    comparable_rooms: List[str] = Form([]),
    comparable_floor: List[str] = Form([]),
    comparable_built_area: List[str] = Form([]),
    comparable_balcony_area: List[str] = Form([]),
    comparable_price: List[str] = Form([]),
    comparable_notes: List[str] = Form([]),
    comparable_is_outlier: List[str] = Form([]),
    comparables_fetched_at: str = Form(""),
):
    today = _today_str()
    city, street, house_num = _parse_address(address)

    is_rented = bool(tenant_name.strip())
    parking = _bool(has_parking)
    storage = _bool(has_storage)
    garden = _bool(has_garden)

    rental_end = _date_html_to_display(rental_end_date) if rental_end_date else ""
    purch_date = _date_html_to_display(purchase_date) if purchase_date else ""

    img_bytes: List[bytes] = []
    for f in property_images:
        if f.filename:
            img_bytes.append(await f.read())

    _IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff")
    plan_imgs: List[tuple] = []
    for f, t in zip(plan_docs, plan_types):
        if not f.filename:
            continue
        ctype = (f.content_type or "").lower()
        ext_ok = f.filename.lower().endswith(_IMAGE_EXTS)
        if not ctype.startswith("image/") and not ext_ok:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"הקובץ '{f.filename}' אינו תמונה. ניתן להעלות "
                    "כמסמכי תכנון רק קבצי תמונה (JPG/PNG/GIF/WebP/TIFF)."
                ),
            )
        plan_imgs.append((t, await f.read()))

    # Auto-fill city/neighborhood descriptions via Claude if the appraiser
    # left them blank. Failures degrade gracefully to the existing
    # "יש להשלים" placeholder — generation never blocks on the API.
    DEFAULT_CITY = f"{city} — יש להשלים תיאור עיר."
    DEFAULT_NBHD_NAME = "יש להשלים"
    DEFAULT_NBHD_DESC = "יש להשלים — תיאור השכונה."

    def _is_empty_or_default(val: str, default: str) -> bool:
        v = (val or "").strip()
        return (not v) or v == default.strip() or "יש להשלים" in v

    final_city_desc = (city_description or "").strip() or DEFAULT_CITY
    if _is_empty_or_default(city_description, DEFAULT_CITY) and city:
        generated = claude_descriptions.try_describe_city(city)
        if generated:
            final_city_desc = claude_descriptions.with_footnote(generated)
            logger.info("city_description auto-filled via Claude for %r", city)

    final_nbhd_name = (neighborhood_name or "").strip() or DEFAULT_NBHD_NAME
    nbhd_for_api = (neighborhood_name or "").strip()
    final_nbhd_desc = (neighborhood_description or "").strip() or DEFAULT_NBHD_DESC
    if (
        _is_empty_or_default(neighborhood_description, DEFAULT_NBHD_DESC)
        and city
        and nbhd_for_api
    ):
        generated = claude_descriptions.try_describe_neighborhood(city, nbhd_for_api)
        if generated:
            final_nbhd_desc = claude_descriptions.with_footnote(generated)
            logger.info(
                "neighborhood_description auto-filled via Claude for %r/%r",
                city, nbhd_for_api,
            )

    data = PropertyInput(
        report_number=f"WEB-{date.today().strftime('%Y%m%d')}",
        report_date=today,
        determining_date=_today_hebrew(),
        visit_date=today,
        report_purpose=_PURPOSE_MAP.get(purpose, ReportPurpose.MARKET),
        client_name=client_name.strip(),
        client_gender=_GENDER_MAP.get(client_gender, ClientGender.MALE),
        city=city,
        street=street,
        house_number=house_num,
        address=address.strip(),
        block=block.strip(),
        parcel=parcel.strip(),
        sub_parcel=sub_parcel.strip(),
        rights_type=_RIGHTS_MAP.get(rights_type, RightsType.PRIVATE),
        rights_owner=client_name.strip(),
        common_property_share="יש להשלים",
        registration_date=today,
        floor_description=f"קומה {floor}",
        build_year=_i(build_year),
        total_floors=_i(total_floors),
        units_count=_i(units_count),
        ground_floor_use="כניסה ולובי",
        building_physical_condition="תקין",
        rooms=_f(rooms, 3.0),
        floor=_i(floor),
        air_directions=air_directions.strip(),
        registered_area=_f(registered_area),
        built_area=_f(built_area),
        balcony_area=_f(balcony_area, 0.0),
        ceiling_height=_f(ceiling_height, 2.7) or 2.7,
        permit_status=PermitStatus.PERMIT,
        finish_level=_FINISH_MAP.get(finish_level, FinishLevel.GOOD),
        has_parking=parking,
        parking_description="חניה" if parking else "",
        has_storage=storage,
        storage_description="מחסן" if storage else "",
        has_garden=garden,
        garden_area=0.0,
        is_rented=is_rented,
        tenant_name=tenant_name.strip(),
        landlord_name=client_name.strip(),
        rental_agreement_date="יש להשלים" if is_rented else "",
        rental_start_date="יש להשלים" if is_rented else "",
        rental_end_date=rental_end,
        monthly_rent=_f(monthly_rent, 0.0),
        city_description=final_city_desc,
        neighborhood_name=final_nbhd_name,
        neighborhood_description=final_nbhd_desc,
        street_description=street_description.strip(),
        street_type="פנימי",
        street_direction="דו-סטרי",
        lot_area=0.0,
        topography="מישורית",
        lot_shape="רגולרית",
        north_boundary=north_boundary.strip() or "יש להשלים",
        south_boundary=south_boundary.strip() or "יש להשלים",
        east_boundary=east_boundary.strip() or "יש להשלים",
        west_boundary=west_boundary.strip() or "יש להשלים",
        planning_plans=[],
        has_original_permit=False,
        building_permit_number="",
        building_permit_date="",
        building_permit_allowed="",
        has_completion_cert=False,
        completion_cert_date="",
        balcony_closed_without_permit=False,
        zoning_for_principles=land_use.strip() or "יש להשלים",
        comparison_properties=_build_comparables(
            addresses=comparable_address,
            rooms=comparable_rooms,
            floors=comparable_floor,
            built_areas=comparable_built_area,
            balcony_areas=comparable_balcony_area,
            prices=comparable_price,
            notes_=comparable_notes,
            outliers=comparable_is_outlier,
        ),
        sqm_equiv_price=_f(final_value) / (_f(built_area) or 1),
        final_value=_f(final_value),
        purchase_date=purch_date,
        purchase_price=_f(purchase_price, 0.0),
        special_notes=notes.strip(),
        comparables_fetched_at=(comparables_fetched_at.strip() or None),
        property_images=img_bytes,
        planning_images=plan_imgs,
    )

    docx_bytes = generate_report_bytes(data)
    safe_address = re.sub(r'[\\/:*?"<>|]', "-", address)[:50]
    filename_he = f"שומת_מקרקעין_{safe_address}.docx"
    # RFC 5987: UTF-8 percent-encode for non-ASCII filenames
    from urllib.parse import quote
    filename_encoded = quote(filename_he, safe="")
    content_disposition = (
        f"attachment; filename=\"report.docx\"; "
        f"filename*=UTF-8''{filename_encoded}"
    )

    return Response(
        content=docx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": content_disposition,
            "Content-Length": str(len(docx_bytes)),
        },
    )
