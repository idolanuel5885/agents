"""Report generator — builds all sections of the Word document."""
import io
from docx import Document
from docx.shared import Cm

from .models import (
    PropertyInput, ReportPurpose, RightsType, FinishLevel, PermitStatus, ClientGender
)
from .docx_utils import (
    make_rtl_doc, add_para, add_heading, add_bullet, set_cell, make_table,
    FONT_BODY, FONT_HEADING1, FONT_HEADING2, FONT_TITLE,
)
from . import skill_loader

# ── Hebrew helpers ────────────────────────────────────────────────────────────

_ONES = {
    1: "אחד", 2: "שניים", 3: "שלושה", 4: "ארבעה", 5: "חמישה",
    6: "שישה", 7: "שבעה", 8: "שמונה", 9: "תשעה", 10: "עשרה",
    11: "אחד עשר", 12: "שניים עשר", 13: "שלושה עשר", 14: "ארבעה עשר",
    15: "חמישה עשר", 16: "שישה עשר", 17: "שבעה עשר", 18: "שמונה עשר",
    19: "תשעה עשר", 20: "עשרים",
}
_TENS = {
    2: "עשרים", 3: "שלושים", 4: "ארבעים", 5: "חמישים",
    6: "שישים", 7: "שבעים", 8: "שמונים", 9: "תשעים",
}
_HUNDREDS = {
    1: "מאה", 2: "מאתיים", 3: "שלוש מאות", 4: "ארבע מאות",
    5: "חמש מאות", 6: "שש מאות", 7: "שבע מאות", 8: "שמונה מאות",
    9: "תשע מאות",
}
_FLOOR_ORD = {
    1: "ראשונה", 2: "שנייה", 3: "שלישית", 4: "רביעית", 5: "חמישית",
    6: "שישית", 7: "שביעית", 8: "שמינית", 9: "תשיעית", 10: "עשירית",
    11: "אחת-עשרה", 12: "שתים-עשרה", 13: "שלוש-עשרה", 14: "ארבע-עשרה",
    15: "חמש-עשרה", 16: "שש-עשרה", 17: "שבע-עשרה", 18: "שמונה-עשרה",
    19: "תשע-עשרה", 20: "עשרים",
}


def _three_digit(n: int) -> str:
    if n <= 0:
        return ""
    if n in _ONES:
        return _ONES[n]
    h, rem = divmod(n, 100)
    t, u = divmod(rem, 10)
    parts = []
    if h:
        parts.append(_HUNDREDS[h])
    if t >= 2:
        parts.append(f"{_TENS[t]} ו{_ONES[u]}" if u else _TENS[t])
    elif t == 1:
        parts.append(_ONES[10 + u])
    elif u:
        parts.append(_ONES[u])
    return " ו".join(parts)


def num_to_words(n: int) -> str:
    if n == 0:
        return "אפס"
    billions = n // 1_000_000_000
    millions = (n % 1_000_000_000) // 1_000_000
    thousands = (n % 1_000_000) // 1_000
    remainder = n % 1_000
    parts = []
    if billions:
        parts.append(f"{_three_digit(billions)} מיליארד")
    if millions:
        mil_word = {1: "מיליון", 2: "שני מיליון"}.get(
            millions, f"{_three_digit(millions)} מיליון"
        )
        parts.append(mil_word)
    if thousands:
        if thousands == 1:
            parts.append("אלף")
        elif thousands == 2:
            parts.append("אלפיים")
        elif thousands <= 20:
            parts.append(f"{_ONES[thousands]} אלף")
        else:
            parts.append(f"{_three_digit(thousands)} אלף")
    if remainder:
        parts.append(_three_digit(remainder))
    return " ו".join(parts)


def fmt_ils(amount: float) -> str:
    return f"{amount:,.0f} ₪"


def _opt(val, field_name: str = "ערך חסר", suffix: str = "") -> str:
    """Return val+suffix or '[field_name]' for falsy values."""
    if val is None or val == "" or val == 0:
        return f"[{field_name}]"
    return f"{val}{suffix}"


def floor_ord(n: int) -> str:
    return _FLOOR_ORD.get(n, str(n))


def rights_display(rt: RightsType) -> str:
    return skill_loader.get({
        RightsType.PRIVATE: "rights.private",
        RightsType.LEASE_RAMI: "rights.lease_rami",
        RightsType.LEASE_COMPANY: "rights.lease_company",
    }[rt])


def purpose_display(p: ReportPurpose) -> str:
    return skill_loader.get({
        ReportPurpose.MARKET: "purpose.market",
        ReportPurpose.STANDARD_19: "purpose.standard_19",
        ReportPurpose.EVACUATION: "purpose.evacuation",
    }[p])


def finish_desc(level: FinishLevel) -> str:
    return skill_loader.get({
        FinishLevel.BASIC: "finish.basic",
        FinishLevel.GOOD: "finish.good",
    }.get(level, "finish.luxury"))


# ── Section builders ──────────────────────────────────────────────────────────

def _section_01_title(doc: Document, d: PropertyInput):
    """כותרת ופתיח"""
    full_suffix = (
        "" if d.report_purpose == ReportPurpose.MARKET
        else skill_loader.get("section_01.title_full_suffix")
    )
    prop_type = skill_loader.render("section_01.prop_type_apartment", rooms=d.rooms)

    # Header table (4 rows × 1 col)
    tbl = make_table(doc, 4, 1)
    set_cell(tbl.rows[0].cells[0],
             skill_loader.render("section_01.title", full_suffix=full_suffix),
             bold=True, font_size=FONT_TITLE)
    set_cell(tbl.rows[1].cells[0],
             skill_loader.render(
                 "section_01.subject_line",
                 purpose=purpose_display(d.report_purpose),
                 prop_type=prop_type,
             ),
             bold=True, font_size=FONT_HEADING2)
    set_cell(tbl.rows[2].cells[0],
             skill_loader.render(
                 "section_01.block_parcel",
                 block=d.block, parcel=d.parcel, sub_parcel=d.sub_parcel,
             ))
    set_cell(tbl.rows[3].cells[0], d.address)

    add_para(doc, "", space_after=12)

    # Opening letter
    add_para(doc, d.report_date, space_after=4)
    add_para(doc, skill_loader.render("section_01.report_number", report_number=d.report_number),
             space_after=12)
    add_para(doc, skill_loader.get("section_01.lekavod"), space_after=2)

    if d.client_gender == ClientGender.COMPANY:
        add_para(doc, skill_loader.render("section_01.client.company", client_name=d.client_name),
                 space_after=2)
        salutation = skill_loader.get("section_01.salutation.formal")
        you = skill_loader.get("section_01.you.plural")
    elif d.client_gender == ClientGender.BANK:
        add_para(doc, skill_loader.render("section_01.client.bank", client_name=d.client_name),
                 space_after=2)
        salutation = skill_loader.get("section_01.salutation.formal")
        you = skill_loader.get("section_01.you.plural")
    elif d.client_gender == ClientGender.FEMALE:
        add_para(doc, skill_loader.render("section_01.client.female", client_name=d.client_name),
                 space_after=2)
        salutation = skill_loader.get("section_01.salutation.female")
        you = skill_loader.get("section_01.you.singular")
    else:
        add_para(doc, skill_loader.render("section_01.client.male", client_name=d.client_name),
                 space_after=2)
        salutation = skill_loader.get("section_01.salutation.formal")
        you = skill_loader.get("section_01.you.singular")

    add_para(doc, salutation, space_after=12)
    add_para(
        doc,
        skill_loader.render(
            "section_01.opening",
            you=you, purpose=purpose_display(d.report_purpose),
        ),
        space_after=8,
    )


def _section_02_details_table(doc: Document, d: PropertyInput):
    """טבלת פרטי הנכס"""
    add_heading(doc, skill_loader.get("section_02.heading"), level=2)

    floor_o = floor_ord(d.floor)
    apt_desc = skill_loader.render("section_02.apt_desc", rooms=d.rooms, floor_ord=floor_o)

    attachments = []
    if d.has_parking:
        attachments.append(d.parking_description
                           or skill_loader.get("section_02.attachment.parking_default"))
    if d.has_storage:
        attachments.append(d.storage_description
                           or skill_loader.get("section_02.attachment.storage_default"))
    if d.has_garden:
        attachments.append(skill_loader.render(
            "section_02.attachment.garden", garden_area=d.garden_area))

    rows = [
        (skill_loader.get("section_02.label.purpose"), purpose_display(d.report_purpose), False),
        (skill_loader.get("section_02.label.client"), d.client_name, False),
        (skill_loader.get("section_02.label.rights_owner"), d.rights_owner, False),
        (skill_loader.get("section_02.label.determining_date"), d.determining_date, False),
        (skill_loader.get("section_02.label.visit_date"), d.visit_date, False),
        (skill_loader.get("section_02.label.block"), d.block, False),
        (skill_loader.get("section_02.label.parcel"), d.parcel, False),
        (skill_loader.get("section_02.label.sub_parcel"), d.sub_parcel, False),
        (skill_loader.get("section_02.label.building"),
         skill_loader.render(
             "section_02.building_desc",
             total_floors=d.total_floors, units_count=d.units_count,
         ),
         False),
        (skill_loader.get("section_02.label.apartment"), apt_desc, True),
        (skill_loader.get("section_02.label.registered_area"),
         skill_loader.render("section_02.value.registered_area", area=d.registered_area), False),
        (skill_loader.get("section_02.label.built_area"),
         skill_loader.render("section_02.value.built_area", area=d.built_area), False),
        (skill_loader.get("section_02.label.location"), d.address, False),
        (skill_loader.get("section_02.label.rights"), rights_display(d.rights_type), False),
    ]
    if attachments:
        rows.append((skill_loader.get("section_02.label.attachments"),
                     ", ".join(attachments), False))

    tbl = make_table(doc, len(rows), 2, col_widths_cm=[4.5, 11.5])
    for i, (label, value, bold_val) in enumerate(rows):
        set_cell(tbl.rows[i].cells[0], label, bold=True)
        set_cell(tbl.rows[i].cells[1], value, bold=bold_val)

    add_para(doc, "")


def _embed_images(doc: Document, images: list, width_cm: float = 7.5):
    """Embed a list of image bytes in a 2-column table."""
    if not images:
        return
    n_rows = (len(images) + 1) // 2
    tbl = make_table(doc, n_rows, 2, col_widths_cm=[width_cm, width_cm])
    for idx, img_bytes in enumerate(images):
        cell = tbl.rows[idx // 2].cells[idx % 2]
        try:
            cell.paragraphs[0].add_run().add_picture(io.BytesIO(img_bytes), width=Cm(width_cm))
        except Exception:
            cell.paragraphs[0].add_run("[תמונה לא תקינה]")
    add_para(doc, "")


def _section_03_description(doc: Document, d: PropertyInput):
    """תיאור הנכס והסביבה"""
    add_heading(doc, skill_loader.get("section_03.heading"))

    # ── 3 environment paragraphs ──────────────────────────────────
    add_heading(doc, skill_loader.get("section_03.environment.heading"), level=2)
    add_para(doc, d.city_description or skill_loader.get("section_03.placeholder.city"))
    add_para(doc, d.neighborhood_description or skill_loader.get("section_03.placeholder.neighborhood"))
    street_para = d.street_description or skill_loader.render(
        "section_03.street.default",
        street=d.street, street_type=d.street_type, street_direction=d.street_direction,
    )
    add_para(doc, street_para)
    add_para(doc, skill_loader.get("section_03.env_development"))

    # ── Lot ──────────────────────────────────────────────────────
    add_heading(doc, skill_loader.get("section_03.lot.heading"), level=2)
    add_para(
        doc,
        skill_loader.render(
            "section_03.lot.description",
            parcel=d.parcel, block=d.block,
            topography=d.topography, lot_shape=d.lot_shape, lot_area=d.lot_area,
        )
    )

    btbl = make_table(doc, 4, 2, col_widths_cm=[3, 13])
    for i, (dir_id, desc) in enumerate([
        ("section_03.boundary.north", d.north_boundary),
        ("section_03.boundary.south", d.south_boundary),
        ("section_03.boundary.east",  d.east_boundary),
        ("section_03.boundary.west",  d.west_boundary),
    ]):
        set_cell(btbl.rows[i].cells[0], skill_loader.get(dir_id), bold=True)
        set_cell(btbl.rows[i].cells[1], desc)

    add_para(doc, "")
    add_para(
        doc,
        skill_loader.render(
            "section_03.building.summary",
            build_year=_opt(d.build_year, 'שנת בנייה'),
            total_floors=_opt(d.total_floors, 'קומות'),
            ground_floor_use=d.ground_floor_use,
            units_count=_opt(d.units_count, 'יחידות דיור'),
            condition=d.building_physical_condition,
        )
    )

    # ── Apartment — 2-paragraph structure ────────────────────────
    add_heading(doc, skill_loader.get("section_03.apt.heading"), level=2)
    floor_o = floor_ord(d.floor)
    air = d.air_directions or skill_loader.get("section_03.apt.placeholder.air_directions")
    # § 1 — bold opening
    add_para(
        doc,
        skill_loader.render(
            "section_03.apt.opening",
            rooms=d.rooms, floor_ord=floor_o, air=air,
        ),
        bold=True,
    )
    # § 2 — detail paragraph
    area_str = skill_loader.render("section_03.apt.area_built", built_area=d.built_area)
    if d.balcony_area > 0:
        area_str += skill_loader.render("section_03.apt.area_balcony", balcony_area=d.balcony_area)
    else:
        area_str += skill_loader.get("section_03.apt.area_balcony_missing")
    area_str += "."

    att_parts = []
    if d.has_parking:
        att_parts.append(d.parking_description
                         or skill_loader.get("section_03.apt.attachment.parking_default"))
    if d.has_storage:
        att_parts.append(d.storage_description
                         or skill_loader.get("section_03.apt.attachment.storage_default"))
    if d.has_garden:
        att_parts.append(skill_loader.render(
            "section_03.apt.attachment.garden", garden_area=d.garden_area))
    att_str = (
        skill_loader.render("section_03.apt.attachments", att_str=', '.join(att_parts))
        if att_parts else ""
    )

    rooms_int = int(d.rooms)
    interior = (
        skill_loader.render("section_03.apt.interior.multi", bedrooms=rooms_int - 1)
        if rooms_int >= 2 else skill_loader.get("section_03.apt.interior.single")
    )

    if d.permit_status == PermitStatus.PERMIT:
        permit_str = skill_loader.get(
            "section_03.apt.permit.with_balcony_unpermitted"
            if d.balcony_closed_without_permit
            else "section_03.apt.permit.normal"
        )
    else:
        permit_str = skill_loader.get("section_03.apt.permit.violations")

    rental_str = (
        skill_loader.render(
            "section_03.apt.rental",
            tenant_name=d.tenant_name, rent=fmt_ils(d.monthly_rent),
        )
        if d.is_rented else ""
    )

    ceiling = (
        skill_loader.render("section_03.apt.ceiling.value", ceiling_height=d.ceiling_height)
        if d.ceiling_height
        else skill_loader.get("section_03.apt.ceiling.placeholder")
    )
    add_para(
        doc,
        skill_loader.render(
            "section_03.apt.detail",
            area_str=area_str, att_str=att_str, interior=interior,
            finish_desc=finish_desc(d.finish_level),
            ceiling=ceiling, permit_str=permit_str, rental_str=rental_str,
        )
    )


def _section_04_planning(doc: Document, d: PropertyInput):
    """הרקע התכנוני"""
    add_heading(doc, skill_loader.get("section_04.heading"))
    add_heading(doc, skill_loader.get("section_04.plans.heading"), level=2)

    if not d.planning_plans:
        add_para(doc, skill_loader.get("common.placeholder.todo"))
    else:
        for plan in d.planning_plans:
            add_para(
                doc,
                skill_loader.render(
                    "section_04.plan.entry",
                    plan_number=plan.plan_number,
                    gazette_number=plan.gazette_number,
                    gazette_date=plan.gazette_date,
                    zoning=plan.zoning,
                )
            )
            if plan.notes:
                add_para(doc, plan.notes)

    add_heading(doc, skill_loader.get("section_04.permit.heading"), level=2)
    add_para(doc, skill_loader.get("section_04.permit.intro"))

    if not d.has_original_permit:
        add_bullet(doc, skill_loader.get("section_04.permit.missing"))
    else:
        add_bullet(
            doc,
            skill_loader.render(
                "section_04.permit.entry",
                permit_number=_opt(d.building_permit_number, 'מספר היתר'),
                permit_date=_opt(d.building_permit_date, 'תאריך היתר'),
                permit_allowed=_opt(d.building_permit_allowed, 'מה הותר'),
            )
        )
        if d.has_completion_cert:
            add_bullet(doc, skill_loader.render(
                "section_04.permit.completion",
                date=_opt(d.completion_cert_date, 'תאריך תעודת גמר'),
            ))

    if d.balcony_closed_without_permit:
        add_para(doc, skill_loader.get("section_04.permit.balcony_closed"))

    imgs = [b for t, b in d.planning_images if t == "04"]
    _embed_images(doc, imgs)


def _section_05_legal(doc: Document, d: PropertyInput):
    """המצב המשפטי"""
    add_heading(doc, "המצב המשפטי")
    add_heading(doc, "א. נסח רישום מקרקעין", level=2)

    add_para(
        doc,
        f"על פי העתק רישום מפנקס הבתים המשותפים, אשר הופק על ידי הח\"מ "
        f"בתאריך {d.registration_date} באמצעות האינטרנט, "
        f"עולים, בין היתר, הפרטים הבאים:"
    )

    reg_rows = [
        ("גוש", d.block),
        ("חלקה", d.parcel),
        ("תת חלקה", d.sub_parcel),
        ("תיאור קומה", d.floor_description),
        ("שטח", f"{d.registered_area:.0f} מ\"ר"),
        ("החלק ברכוש המשותף", d.common_property_share),
        ("בעלויות", d.rights_owner),
        ("הערות", "לא נרשמו הערות"),
    ]
    rtbl = make_table(doc, len(reg_rows), 2, col_widths_cm=[4.5, 11.5])
    for i, (lbl, val) in enumerate(reg_rows):
        set_cell(rtbl.rows[i].cells[0], lbl, bold=True)
        set_cell(rtbl.rows[i].cells[1], val)

    add_para(doc, "")
    add_heading(doc, "ב. תשריט בית משותף", level=2)
    add_para(
        doc,
        f"להלן תכנית קומה {d.floor} מתוך תשריט הבית המשותף: [הכנס תמונה]"
    )

    if d.is_rented:
        add_heading(doc, "ג. הסכם שכירות", level=2)
        add_para(
            doc,
            f"בהתאם להסכם שכירות בלתי מוגנת אשר נחתם בתאריך "
            f"{d.rental_agreement_date}, בין {d.landlord_name} לבין "
            f"{d.tenant_name}, עולים הפרטים הבאים:"
        )
        rent_rows = [
            ("המושכר", d.address),
            ("תקופת השכירות", f"{d.rental_start_date} — {d.rental_end_date}"),
            ("דמי השכירות", f"{fmt_ils(d.monthly_rent)} לחודש"),
        ]
        rnttbl = make_table(doc, len(rent_rows), 2, col_widths_cm=[4.5, 11.5])
        for i, (lbl, val) in enumerate(rent_rows):
            set_cell(rnttbl.rows[i].cells[0], lbl, bold=True)
            set_cell(rnttbl.rows[i].cells[1], val)

    imgs = [b for t, b in d.planning_images if t == "05"]
    _embed_images(doc, imgs)


def _section_06_valuation(doc: Document, d: PropertyInput):
    """עקרונות + נתוני השוואה + שומה"""
    add_heading(doc, "עקרונות ושיקולים, נתוני השוואה ושומה")

    # ── A: Principles ────────────────────────────────────────────
    add_heading(doc, "א. עקרונות, גורמים ושיקולים", level=2)

    add_para(doc, "1. כללי", bold=True, font_size=FONT_BODY)
    floor_o = floor_ord(d.floor)
    general = [
        f"מיקום הנכס: {d.address}.",
        f"אופי הסביבה: {d.neighborhood_name} ב{d.city}.",
        f"שנת בניית הבניין: {d.build_year}. מספר יחידות הדיור בבניין: {d.units_count}.",
        f"הדירה ממוקמת בקומה ה-{floor_o}, בת {d.rooms} חדרים, פונה לכיוון {d.air_directions}.",
        (f"שטח הדירה הבנוי הינו כ-{d.built_area:.0f} מ\"ר"
         + (f", ומרפסת בשטח כ-{d.balcony_area:.0f} מ\"ר" if d.balcony_area > 0 else "")
         + "."),
        f"גובה פנים: כ-{d.ceiling_height:.1f} מ'.",
        (("הדירה בנויה בהתאם להיתר" + (" (למעט סגירת המרפסת)" if d.balcony_closed_without_permit else ""))
         if d.permit_status == PermitStatus.PERMIT
         else "נמצאו חריגות בנייה.") + " — מצב היתר.",
        f"רמת גמר: {d.finish_level.value}.",
    ]
    attachments = []
    if d.has_parking:
        attachments.append("חניה")
    if d.has_storage:
        attachments.append("מחסן")
    if d.has_garden:
        attachments.append("גינה")
    if attachments:
        general.append(f"הצמדות: {', '.join(attachments)}.")
    for item in general:
        add_bullet(doc, item)

    add_para(doc, "2. תכנון ורישוי", bold=True, font_size=FONT_BODY, space_before=6)
    planning_bullets = [
        f"בהתאם לתכניות בניין עיר שבתוקף החלקה מסווגת ביעוד '{d.zoning_for_principles}'.",
    ]
    if d.has_original_permit:
        planning_bullets.append(
            f"הדירה שבנדון בנויה בהתאם להיתר בנייה משנת {_opt(d.build_year, 'שנת בנייה')}."
        )
    else:
        planning_bullets.append("לא אותר היתר הבנייה המקורי של הבניין.")
    if d.has_completion_cert and d.completion_cert_date:
        year = d.completion_cert_date.split("/")[-1] if "/" in d.completion_cert_date else d.completion_cert_date
        planning_bullets.append(f"תעודת גמר לבניין ניתנה בשנת {year}.")
    for item in planning_bullets:
        add_bullet(doc, item)

    add_para(doc, "3. מצב משפטי", bold=True, font_size=FONT_BODY, space_before=6)
    legal_bullets = [
        "החלקה נרשמה בפנקס הבתים המשותפים, באופן בו כל תת חלקה מהווה יחידה עצמאית.",
        f"הדירה שבנדון רשומה על שם {d.rights_owner}.",
        "נכון למועד הביקור, הדירה מושכרת בשכירות חופשית."
        if d.is_rented
        else "נכון למועד הביקור, הדירה אינה מושכרת.",
    ]
    for item in legal_bullets:
        add_bullet(doc, item)

    add_para(doc, "4. עקרונות התחשיב", bold=True, font_size=FONT_BODY, space_before=6)
    for item in [
        "אומדן השווי נערך לנכס שבנדון כחופשי מכל הערה, חוב ושעבוד.",
        "הובא בחשבון מצב שוק המקרקעין ומחירי נכסים דומים ורלוונטיים בסביבת הנכס.",
    ]:
        add_bullet(doc, item)

    add_para(doc, "")

    # ── B: Comparison data ───────────────────────────────────────
    add_heading(doc, "ב. נתוני השוואה", level=2)

    if d.comparison_properties:
        headers = [
            "מס'", "כתובת", "קומה", "חד'",
            "שטח בנוי מ\"ר", "מרפסת מ\"ר", "שטח אקו' מ\"ר",
            "מחיר", "₪/מ\"ר אקו'", "הערות",
        ]
        ctbl = make_table(doc, len(d.comparison_properties) + 1, len(headers))
        for i, h in enumerate(headers):
            set_cell(ctbl.rows[0].cells[i], h, bold=True, font_size=10)

        for j, prop in enumerate(d.comparison_properties):
            vals = [
                str(j + 1),
                prop.address,
                prop.floor,
                prop.rooms,
                f"{prop.built_area:.0f}",
                f"{prop.balcony_area:.0f}" if prop.balcony_area else "—",
                f"{prop.equiv_area:.1f}",
                fmt_ils(prop.price),
                f"{prop.price_per_sqm:,.0f} ₪",
                prop.notes or "—",
            ]
            for i, v in enumerate(vals):
                set_cell(ctbl.rows[j + 1].cells[i], v, font_size=10)

        add_para(doc, "")
        add_para(
            doc,
            f"לאור הנתונים שהוצגו לעיל, ובהתחשב במאפייני הנכס שבנדון ובמיקומו "
            f"נראה כסביר לאמוד שווי מ\"ר אקו' בנכס שבנדון בסך של כ- "
            f"{d.sqm_equiv_price:,.0f} ₪ / מ\"ר אקו'."
        )
    else:
        add_para(doc, "יש להשלים — נתוני עסקאות השוואה יש להוסיף ידנית.")

    add_para(doc, "")

    # ── C: Valuation ─────────────────────────────────────────────
    add_heading(doc, "ג. שומה", level=2)

    value_words = num_to_words(int(d.final_value))
    add_para(
        doc,
        f"בהתבסס על כל האמור לעיל ובמיקומו של הנכס המהווה את תת חלקה "
        f"{d.sub_parcel} בחלקה מספר {d.parcel} בגוש {d.block}, "
        f"ברחוב {d.address}:",
        font_size=FONT_BODY,
    )
    add_para(
        doc,
        f"אומדן שווי הזכויות בנכס שבנדון הינו סביב "
        f"{fmt_ils(d.final_value)} "
        f"({value_words} שקלים חדשים) כולל מע\"מ.",
        bold=True,
        font_size=FONT_BODY + 1,
    )

    if d.report_purpose == ReportPurpose.STANDARD_19:
        rapid = d.final_value * 0.85
        add_para(
            doc,
            f"לצורך מימוש מהיר בדרך של מכירה באילוץ, ניתן להעמיד את שווי הנכס "
            f"על סך של 85% מהשווי הנקוב לעיל, קרי: "
            f"{fmt_ils(rapid)} ({num_to_words(int(rapid))} שקלים חדשים)."
        )

    if d.report_purpose == ReportPurpose.EVACUATION:
        for label, val in [
            ("חלופה א' — שווי קיים", d.future_value_a),
            ("חלופה ב' — שווי עתידי", d.future_value_b),
        ]:
            words = num_to_words(int(val))
            add_para(doc, f"{label}: {fmt_ils(val)} ({words} שקלים חדשים).")

    add_para(doc, "")

    # Closing declarations
    add_heading(doc, "הצהרות", level=2)
    for decl in [
        "הננו מצהירים כי אין לנו עניין אישי עם הנכס שבנדון, "
        "בעלי הזכויות בנכס או עם מזמין חוות הדעת.",

        "חוות הדעת נערכה על פי תקנות שמאי המקרקעין (אתיקה מקצועית) "
        "התשכ\"ו – 1966 ועל פי התקנים המקצועיים של הועדה לתקינה שמאית "
        "במועצת שמאי המקרקעין.",

        "שומה זו הוכנה עבור מזמינה ולמטרתה בלבד. אין היא מהווה תחליף "
        "לייעוץ משפטי ואין להסתמך עליה לכל מטרה אחרת.",
    ]:
        add_para(doc, decl)


def _section_07_tax(doc: Document, d: PropertyInput):
    """נספח מיסוי — תקן 19 בלבד"""
    if d.report_purpose != ReportPurpose.STANDARD_19:
        return

    doc.add_page_break()
    add_heading(doc, "נספח מיסוי")

    add_para(
        doc,
        "בהתאם לבקשתכם, להלן תחשיב שווי הנכס נטו לאחר הפחתות "
        "בגין עלויות צפויות בעת מימוש:"
    )

    gain = d.final_value - d.purchase_price
    tax = gain * 0.25 if gain > 0 else 0.0
    net = d.final_value - tax

    add_para(
        doc,
        f"הנכס שבנדון נרכש בתאריך {d.purchase_date} בתמורה לסך של "
        f"כ-{fmt_ils(d.purchase_price)}. שווי הנכס גבוה מעלותו באופן בו "
        f"צפויה לחול חבות במס בעת מימוש "
        f"(הובא בחשבון מס שבח בשיעור של 25%)."
    )

    tax_rows = [
        ("שווי השוק (ברוטו)", fmt_ils(d.final_value), False),
        ("הפחתת מס שבח (25%)", f"({fmt_ils(tax)})", False),
        ("שווי נטו למימוש", fmt_ils(net), True),
    ]
    ttbl = make_table(doc, len(tax_rows), 2, col_widths_cm=[8, 8])
    for i, (lbl, val, bold_row) in enumerate(tax_rows):
        set_cell(ttbl.rows[i].cells[0], lbl, bold=bold_row)
        set_cell(ttbl.rows[i].cells[1], val, bold=bold_row)


def _section_photos(doc: Document, d: PropertyInput):
    if not d.property_images:
        return
    add_heading(doc, "תצלומי הנכס")
    _embed_images(doc, d.property_images, width_cm=7.5)


def _section_notes(doc: Document, d: PropertyInput):
    """הערות מיוחדות — appears only when special_notes is set."""
    if not d.special_notes:
        return
    doc.add_page_break()
    add_heading(doc, "הערות מיוחדות")
    add_para(doc, d.special_notes)


# ── Main entry point ──────────────────────────────────────────────────────────

def _build_doc(data: PropertyInput) -> Document:
    doc = make_rtl_doc()
    _section_01_title(doc, data)
    doc.add_page_break()
    _section_02_details_table(doc, data)
    doc.add_page_break()
    _section_03_description(doc, data)
    if data.property_images:
        doc.add_page_break()
        _section_photos(doc, data)
    doc.add_page_break()
    _section_04_planning(doc, data)
    doc.add_page_break()
    _section_05_legal(doc, data)
    doc.add_page_break()
    _section_06_valuation(doc, data)
    _section_07_tax(doc, data)
    _section_notes(doc, data)
    return doc


def generate_report(data: PropertyInput, output_path: str):
    """Build and save the Word document to a file path."""
    doc = _build_doc(data)
    doc.save(output_path)
    print(f"\n  הדוח נשמר: {output_path}")


def generate_report_bytes(data: PropertyInput) -> bytes:
    """Build the Word document and return raw bytes (for HTTP download)."""
    doc = _build_doc(data)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()
