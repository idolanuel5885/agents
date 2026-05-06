"""FastAPI router — serves the web form and handles report generation."""
import re
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from .models import (
    PropertyInput, ReportPurpose, RightsType, FinishLevel,
    PermitStatus, ClientGender,
)
from .report_generator import generate_report_bytes

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


# ── Generation endpoint ───────────────────────────────────────────────────────

class FormPayload(BaseModel):
    # Required
    purpose: str
    rights_type: str
    client_gender: str
    client_name: str
    address: str
    block: str
    parcel: str
    sub_parcel: str
    rooms: str
    floor: str
    registered_area: str
    built_area: str
    final_value: str
    # Optional
    air_directions: str = ""
    build_year: str = ""
    total_floors: str = ""
    units_count: str = ""
    ceiling_height: str = ""
    balcony_area: str = ""
    finish_level: str = ""
    has_parking: bool = False
    has_storage: bool = False
    has_garden: bool = False
    tenant_name: str = ""
    monthly_rent: str = ""
    rental_end_date: str = ""
    purchase_date: str = ""
    purchase_price: str = ""
    notes: str = ""


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
async def generate(payload: FormPayload):
    today = _today_str()
    city, street, house_num = _parse_address(payload.address)

    is_rented = bool(payload.tenant_name.strip())

    rental_end = (
        _date_html_to_display(payload.rental_end_date)
        if payload.rental_end_date else ""
    )
    purchase_date = (
        _date_html_to_display(payload.purchase_date)
        if payload.purchase_date else ""
    )

    data = PropertyInput(
        report_number=f"WEB-{date.today().strftime('%Y%m%d')}",
        report_date=today,
        determining_date=_today_hebrew(),
        visit_date=today,
        report_purpose=_PURPOSE_MAP.get(payload.purpose, ReportPurpose.MARKET),
        client_name=payload.client_name.strip(),
        client_gender=_GENDER_MAP.get(payload.client_gender, ClientGender.MALE),
        city=city,
        street=street,
        house_number=house_num,
        address=payload.address.strip(),
        block=payload.block.strip(),
        parcel=payload.parcel.strip(),
        sub_parcel=payload.sub_parcel.strip(),
        rights_type=_RIGHTS_MAP.get(payload.rights_type, RightsType.PRIVATE),
        rights_owner=payload.client_name.strip(),
        common_property_share="יש להשלים",
        registration_date=today,
        floor_description=f"קומה {payload.floor}",
        build_year=_i(payload.build_year),
        total_floors=_i(payload.total_floors),
        units_count=_i(payload.units_count),
        ground_floor_use="כניסה ולובי",
        building_physical_condition="תקין",
        rooms=_f(payload.rooms, 3.0),
        floor=_i(payload.floor),
        air_directions=payload.air_directions.strip() or "יש להשלים",
        registered_area=_f(payload.registered_area),
        built_area=_f(payload.built_area),
        balcony_area=_f(payload.balcony_area, 0.0),
        ceiling_height=_f(payload.ceiling_height, 2.7) or 2.7,
        permit_status=PermitStatus.PERMIT,
        finish_level=_FINISH_MAP.get(payload.finish_level, FinishLevel.GOOD),
        has_parking=payload.has_parking,
        parking_description="חניה" if payload.has_parking else "",
        has_storage=payload.has_storage,
        storage_description="מחסן" if payload.has_storage else "",
        has_garden=payload.has_garden,
        garden_area=0.0,
        is_rented=is_rented,
        tenant_name=payload.tenant_name.strip(),
        landlord_name=payload.client_name.strip(),
        rental_agreement_date="יש להשלים" if is_rented else "",
        rental_start_date="יש להשלים" if is_rented else "",
        rental_end_date=rental_end,
        monthly_rent=_f(payload.monthly_rent, 0.0),
        city_description=f"{city} — יש להשלים תיאור עיר.",
        neighborhood_name="יש להשלים",
        neighborhood_description="יש להשלים — תיאור השכונה.",
        street_type="פנימי",
        street_direction="דו-סטרי",
        lot_area=0.0,
        topography="מישורית",
        lot_shape="רגולרית",
        north_boundary="יש להשלים",
        south_boundary="יש להשלים",
        east_boundary="יש להשלים",
        west_boundary="יש להשלים",
        planning_plans=[],
        has_original_permit=False,
        building_permit_number="",
        building_permit_date="",
        building_permit_allowed="",
        has_completion_cert=False,
        completion_cert_date="",
        balcony_closed_without_permit=False,
        zoning_for_principles="יש להשלים",
        comparison_properties=[],
        sqm_equiv_price=_f(payload.final_value) / (_f(payload.built_area) or 1),
        final_value=_f(payload.final_value),
        purchase_date=purchase_date,
        purchase_price=_f(payload.purchase_price, 0.0),
        special_notes=payload.notes.strip(),
    )

    docx_bytes = generate_report_bytes(data)
    safe_address = re.sub(r'[\\/:*?"<>|]', "-", payload.address)[:50]
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
