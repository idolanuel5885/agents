"""Interactive CLI form for collecting all appraisal data."""
from .models import (
    PropertyInput, ComparisonProperty, PlanningPlan,
    ReportPurpose, RightsType, FinishLevel, PermitStatus, ClientGender,
)


# ── Low-level prompt helpers ─────────────────────────────────────────────────

def ask(label: str, default: str = "", required: bool = True) -> str:
    display = f"  {label}"
    if default:
        display += f" [{default}]"
    display += ": "
    while True:
        val = input(display).strip()
        if not val and default:
            return default
        if not val and required:
            print("    *** שדה חובה — יש להזין ערך ***")
            continue
        return val if val else default


def ask_float(label: str, default: float = 0.0, required: bool = True) -> float:
    while True:
        raw = ask(label, str(default) if default else "", required)
        if not raw and not required:
            return default
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            print("    *** יש להזין מספר ***")


def ask_int(label: str, default: int = 0) -> int:
    while True:
        raw = ask(label, str(default))
        try:
            return int(raw)
        except ValueError:
            print("    *** יש להזין מספר שלם ***")


def ask_bool(label: str, default: bool = False) -> bool:
    default_str = "כן" if default else "לא"
    while True:
        val = ask(f"{label} (כן/לא)", default_str)
        if val.lower() in ("כן", "y", "yes", "1"):
            return True
        if val.lower() in ("לא", "n", "no", "0"):
            return False
        print("    *** יש להזין כן או לא ***")


def ask_choice(label: str, choices: list, default_idx: int = 0) -> str:
    print(f"\n  {label}:")
    for i, c in enumerate(choices):
        marker = " ◄" if i == default_idx else ""
        print(f"    {i + 1}. {c}{marker}")
    while True:
        raw = input(f"  בחר מספר [{default_idx + 1}]: ").strip()
        if not raw:
            return choices[default_idx]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print("    *** בחירה לא תקינה ***")


def section(title: str):
    print(f"\n{'─' * 55}")
    print(f"  {title}")
    print(f"{'─' * 55}")


# ── Sub-form collectors ───────────────────────────────────────────────────────

def collect_planning_plans() -> list:
    plans = []
    print("\n  הזן תוכניות מתאר (לפחות 1):")
    while True:
        num = len(plans) + 1
        print(f"\n  — תוכנית מתאר #{num} —")
        plans.append(PlanningPlan(
            plan_number=ask("מספר תוכנית"),
            gazette_number=ask("מספר ילקוט פרסומים"),
            gazette_date=ask("תאריך ילקוט הפרסומים"),
            zoning=ask("ייעוד"),
            notes=ask("הוראות בנייה נוספות", "", required=False),
        ))
        if num >= 1 and not ask_bool("הוסף תוכנית נוספת?", False):
            break
    return plans


def collect_comparison_properties() -> list:
    props = []
    print("\n  הזן נתוני השוואה (לפחות 3 נכסים):")
    while True:
        num = len(props) + 1
        print(f"\n  — נכס השוואה #{num} —")
        props.append(ComparisonProperty(
            address=ask("כתובת"),
            floor=ask("קומה"),
            rooms=ask("חדרים"),
            built_area=ask_float("שטח בנוי (מ\"ר)"),
            balcony_area=ask_float("שטח מרפסת (מ\"ר)", 0.0, required=False),
            price=ask_float("מחיר עסקה (₪)"),
            notes=ask("הערות", "", required=False),
        ))
        if num >= 3 and not ask_bool("הוסף נכס נוסף?", False):
            break
        elif num < 3:
            print(f"  (נדרשים לפחות 3 נכסים — עוד {3 - num} נשארים)")
    return props


# ── Main form ─────────────────────────────────────────────────────────────────

def collect_form() -> PropertyInput:
    print("\n" + "=" * 55)
    print("   מערכת אוטומציה לדוחות שמאות מקרקעין")
    print("=" * 55)
    print("  מלא את הפרטים הבאים. לאישור ברירת מחדל — לחץ Enter.")

    # ── 01: Report metadata ──────────────────────────────────────
    section("01. פרטי הדוח")
    report_number = ask("מספר חוות דעת")
    report_date = ask("תאריך הדוח (DD/MM/YYYY)")
    determining_date = ask("המועד הקובע (בכתיב מילים, לדוגמה: 6 ביולי 2025)")
    visit_date = ask("מועד ביקור בנכס (DD/MM/YYYY)")

    purpose_map = {
        "שוק — אומדן שווי שוק": ReportPurpose.MARKET,
        "תקן 19 — בטוחה למתן אשראי": ReportPurpose.STANDARD_19,
        "פינוי-בינוי": ReportPurpose.EVACUATION,
    }
    purpose_choice = ask_choice("מטרת חוות הדעת", list(purpose_map.keys()))
    report_purpose = purpose_map[purpose_choice]

    # ── 02: Client ───────────────────────────────────────────────
    section("02. פרטי מזמין")
    gender_map = {"מר": ClientGender.MALE, "גב'": ClientGender.FEMALE, "חברה בע\"מ": ClientGender.COMPANY}
    gender_choice = ask_choice("תואר הלקוח", list(gender_map.keys()))
    client_gender = gender_map[gender_choice]
    client_name = ask("שם הלקוח")

    # ── 03: Property identification ──────────────────────────────
    section("03. זיהוי הנכס")
    city = ask("עיר")
    street = ask("רחוב")
    house_number = ask("מספר בית")
    address = f"רחוב {street} {house_number}, {city}"

    block = ask("גוש")
    parcel = ask("חלקה")
    sub_parcel = ask("תת חלקה")

    # ── 04: Rights ───────────────────────────────────────────────
    section("04. זכויות")
    rights_map = {
        "בעלות פרטית": RightsType.PRIVATE,
        "חכירה מרמ\"י": RightsType.LEASE_RAMI,
        "חכירה מחברה משכנת": RightsType.LEASE_COMPANY,
    }
    rights_choice = ask_choice("סוג הזכויות", list(rights_map.keys()))
    rights_type = rights_map[rights_choice]
    rights_owner = ask("בעלי הזכויות (שם + חלק יחסי אם רלוונטי)")
    common_property_share = ask("חלק ברכוש המשותף (לדוגמה: 2500/100000)")
    registration_date = ask("תאריך הפקת נסח טאבו (DD/MM/YYYY)")
    floor_description = ask("תיאור קומה בנסח (לדוגמה: קומה 3)")

    # ── 05: Building ─────────────────────────────────────────────
    section("05. פרטי הבניין")
    build_year = ask_int("שנת בניית הבניין")
    total_floors = ask_int("מספר קומות מעל קומת כניסה")
    units_count = ask_int("מספר יח\"ד בבניין")
    ground_floor_use = ask("שימוש בקומת קרקע", "כניסה ולובי")
    building_physical_condition = ask("מצב פיזי של הבניין", "תקין")

    # ── 06: Apartment ────────────────────────────────────────────
    section("06. פרטי הדירה")
    rooms = ask_float("מספר חדרים")
    floor = ask_int("קומה")
    air_directions = ask("כיווני אוויר (לדוגמה: מזרח ומערב)")
    registered_area = ask_float("שטח דירה רשום (מ\"ר)")
    built_area = ask_float("שטח דירה בנוי (מ\"ר)")
    balcony_area = ask_float("שטח מרפסת (מ\"ר)", 0.0, required=False)
    ceiling_height = ask_float("גובה פנים (מ')", 2.7)

    permit_status = (
        PermitStatus.PERMIT
        if ask_choice("מצב היתר", ["על פי היתר", "חריגות"]) == "על פי היתר"
        else PermitStatus.DEVIATIONS
    )

    finish_map = {
        "בסיסית": FinishLevel.BASIC,
        "טובה": FinishLevel.GOOD,
        "טובה מאוד": FinishLevel.VERY_GOOD,
    }
    finish_choice = ask_choice("רמת גמר", list(finish_map.keys()), default_idx=1)
    finish_level = finish_map[finish_choice]

    # ── 07: Attachments ──────────────────────────────────────────
    section("07. הצמדות")
    has_parking = ask_bool("האם יש חניה?")
    parking_description = ask("תיאור החניה", "", required=False) if has_parking else ""
    has_storage = ask_bool("האם יש מחסן?")
    storage_description = ask("תיאור המחסן", "", required=False) if has_storage else ""
    has_garden = ask_bool("האם יש גינה?")
    garden_area = ask_float("שטח גינה (מ\"ר)") if has_garden else 0.0

    # ── 08: Rental ───────────────────────────────────────────────
    section("08. שכירות")
    is_rented = ask_bool("האם הדירה מושכרת?")
    tenant_name = landlord_name = rental_agreement_date = ""
    rental_start_date = rental_end_date = ""
    monthly_rent = 0.0
    if is_rented:
        tenant_name = ask("שם השוכר")
        landlord_name = ask("שם המשכיר")
        rental_agreement_date = ask("תאריך חתימת הסכם השכירות")
        rental_start_date = ask("תחילת תקופת השכירות")
        rental_end_date = ask("סיום תקופת השכירות")
        monthly_rent = ask_float("דמי שכירות חודשיים (₪)")

    # ── 09: Environment ──────────────────────────────────────────
    section("09. תיאור הסביבה")
    print("  (הזן פסקה מלאה לכל שדה)")
    city_description = ask("תיאור העיר")
    neighborhood_name = ask("שם השכונה")
    neighborhood_description = ask("תיאור השכונה")
    street_type = ask_choice("סוג הרחוב", ["פנימי", "ראשי"])
    street_direction = ask_choice("כיוון הרחוב", ["דו-סטרי", "חד-סטרי"])

    # ── 10: Lot ──────────────────────────────────────────────────
    section("10. פרטי החלקה")
    lot_area = ask_float("שטח חלקה רשום (מ\"ר)")
    topography = ask_choice("טופוגרפיה", ["מישורית", "משופעת"])
    lot_shape = ask_choice("צורת חלקה", ["רגולרית", "אי-רגולרית"])
    north_boundary = ask("גבול צפון")
    south_boundary = ask("גבול דרום")
    east_boundary = ask("גבול מזרח")
    west_boundary = ask("גבול מערב")

    # ── 11: Planning ─────────────────────────────────────────────
    section("11. הרקע התכנוני")
    planning_plans = collect_planning_plans()

    has_original_permit = ask_bool("האם נמצא היתר בנייה מקורי?", True)
    building_permit_number = building_permit_date = building_permit_allowed = ""
    has_completion_cert = False
    completion_cert_date = ""
    balcony_closed_without_permit = False

    if has_original_permit:
        building_permit_number = ask("מספר היתר הבנייה")
        building_permit_date = ask("תאריך היתר הבנייה")
        building_permit_allowed = ask("מה הותר בהיתר (לדוגמה: בנייה בת 4 קומות)")
        has_completion_cert = ask_bool("האם יש תעודת גמר?")
        if has_completion_cert:
            completion_cert_date = ask("תאריך תעודת הגמר")

    if balcony_area > 0:
        balcony_closed_without_permit = ask_bool("האם המרפסת סגורה ללא היתר?", False)

    zoning_for_principles = planning_plans[0].zoning if planning_plans else ask("ייעוד לחלק העקרונות")

    # ── 12: Comparison data ──────────────────────────────────────
    section("12. נתוני השוואה")
    comparison_properties = collect_comparison_properties()

    # ── 13: Valuation ────────────────────────────────────────────
    section("13. שומה")
    sqm_equiv_price = ask_float("מחיר למ\"ר אקו' (₪)")
    final_value = ask_float("שווי סופי (₪)")

    # ── 14: Purpose-specific extras ──────────────────────────────
    purchase_date = purchase_price = ""
    purchase_price_val = 0.0
    future_value_a = future_value_b = 0.0

    if report_purpose == ReportPurpose.STANDARD_19:
        section("14. נספח מיסוי")
        purchase_date = ask("תאריך רכישת הנכס")
        purchase_price_val = ask_float("מחיר הרכישה (₪)")

    if report_purpose == ReportPurpose.EVACUATION:
        section("14. פינוי-בינוי — חלופות")
        future_value_a = ask_float("שווי חלופה א' (₪)")
        future_value_b = ask_float("שווי חלופה ב' (₪)")

    return PropertyInput(
        report_number=report_number,
        report_date=report_date,
        determining_date=determining_date,
        visit_date=visit_date,
        report_purpose=report_purpose,
        client_name=client_name,
        client_gender=client_gender,
        city=city,
        street=street,
        house_number=house_number,
        address=address,
        block=block,
        parcel=parcel,
        sub_parcel=sub_parcel,
        rights_type=rights_type,
        rights_owner=rights_owner,
        common_property_share=common_property_share,
        registration_date=registration_date,
        floor_description=floor_description,
        build_year=build_year,
        total_floors=total_floors,
        units_count=units_count,
        ground_floor_use=ground_floor_use,
        building_physical_condition=building_physical_condition,
        rooms=rooms,
        floor=floor,
        air_directions=air_directions,
        registered_area=registered_area,
        built_area=built_area,
        balcony_area=balcony_area,
        ceiling_height=ceiling_height,
        permit_status=permit_status,
        finish_level=finish_level,
        has_parking=has_parking,
        parking_description=parking_description,
        has_storage=has_storage,
        storage_description=storage_description,
        has_garden=has_garden,
        garden_area=garden_area,
        is_rented=is_rented,
        tenant_name=tenant_name,
        landlord_name=landlord_name,
        rental_agreement_date=rental_agreement_date,
        rental_start_date=rental_start_date,
        rental_end_date=rental_end_date,
        monthly_rent=monthly_rent,
        city_description=city_description,
        neighborhood_name=neighborhood_name,
        neighborhood_description=neighborhood_description,
        street_type=street_type,
        street_direction=street_direction,
        lot_area=lot_area,
        topography=topography,
        lot_shape=lot_shape,
        north_boundary=north_boundary,
        south_boundary=south_boundary,
        east_boundary=east_boundary,
        west_boundary=west_boundary,
        planning_plans=planning_plans,
        has_original_permit=has_original_permit,
        building_permit_number=building_permit_number,
        building_permit_date=building_permit_date,
        building_permit_allowed=building_permit_allowed,
        has_completion_cert=has_completion_cert,
        completion_cert_date=completion_cert_date,
        balcony_closed_without_permit=balcony_closed_without_permit,
        zoning_for_principles=zoning_for_principles,
        comparison_properties=comparison_properties,
        sqm_equiv_price=sqm_equiv_price,
        final_value=final_value,
        purchase_date=purchase_date,
        purchase_price=purchase_price_val,
        future_value_a=future_value_a,
        future_value_b=future_value_b,
    )
