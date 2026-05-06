"""Sample PropertyInput for smoke-testing without filling the form."""
from .models import (
    PropertyInput, ComparisonProperty, PlanningPlan,
    ReportPurpose, RightsType, FinishLevel, PermitStatus, ClientGender,
)


def sample_standard19() -> PropertyInput:
    """Demo: 4-room apartment, Ramat Gan, תקן 19."""
    return PropertyInput(
        report_number="2025/123",
        report_date="06/05/2025",
        determining_date="6 במאי 2025",
        visit_date="01/05/2025",
        report_purpose=ReportPurpose.STANDARD_19,
        client_name="ישראל ישראלי",
        client_gender=ClientGender.MALE,
        city="רמת גן",
        street="ביאליק",
        house_number="15",
        address="רחוב ביאליק 15, רמת גן",
        block="6130",
        parcel="27",
        sub_parcel="8",
        rights_type=RightsType.PRIVATE,
        rights_owner="ישראל ישראלי (1/1)",
        common_property_share="2847/100000",
        registration_date="01/05/2025",
        floor_description="קומה 3",
        build_year=1985,
        total_floors=8,
        units_count=32,
        ground_floor_use="כניסה ולובי",
        building_physical_condition="תקין",
        rooms=4.0,
        floor=3,
        air_directions="מזרח ומערב",
        registered_area=94.0,
        built_area=92.0,
        balcony_area=12.0,
        ceiling_height=2.7,
        permit_status=PermitStatus.PERMIT,
        finish_level=FinishLevel.GOOD,
        has_parking=True,
        parking_description="חניה תת-קרקעית מס' 8",
        has_storage=True,
        storage_description="מחסן מס' 8 בקומת מרתף",
        has_garden=False,
        garden_area=0.0,
        is_rented=True,
        tenant_name="רחל כהן",
        landlord_name="ישראל ישראלי",
        rental_agreement_date="01/10/2024",
        rental_start_date="01/10/2024",
        rental_end_date="30/09/2025",
        monthly_rent=6500.0,
        city_description=(
            "רמת גן הינה עיר בלב גוש דן, הגובלת בתל אביב ממערב, "
            "בבני ברק מצפון ובגבעתיים מדרום. העיר מונה כ-170,000 תושבים "
            "ומאופיינת בגידול שנתי מתון."
        ),
        neighborhood_name="נווה עופר",
        neighborhood_description=(
            "שכונת נווה עופר ממוקמת בצפון-מערב רמת גן, בסמוך לגבול תל אביב. "
            "גבולות השכונה: מצפון רחוב ז'בוטינסקי, מדרום רחוב ביאליק, "
            "ממזרח רחוב ארלוזורוב וממערב רחוב הירקון. "
            "אופי הבנייה מעורב — בניינים ישנים ומגדלים חדשים. "
            "בשכונה פארק עירוני, בתי ספר ומרכז מסחרי שכונתי."
        ),
        street_description=(
            "רחוב הרצל הינו רחוב שכונתי שקט, דו-סטרי, המחבר בין רחוב ז'בוטינסקי "
            "בצפון לרחוב ביאליק בדרום. לאורכו בנייני מגורים בני 4-6 קומות, ללא "
            "מסחר. בקצהו הצפוני גן ילדים עירוני."
        ),
        street_type="פנימי",
        street_direction="דו-סטרי",
        lot_area=1240.0,
        topography="מישורית",
        lot_shape="רגולרית",
        north_boundary="חלקה 26 — בניין מגורים",
        south_boundary="רחוב ביאליק",
        east_boundary="חלקה 28 — בניין מגורים",
        west_boundary="חלקה 25 — בניין מגורים",
        planning_plans=[
            PlanningPlan(
                plan_number="רג/2000",
                gazette_number="5823",
                gazette_date="15/03/2008",
                zoning="מגורים ג' מיוחד",
                notes="הבניין ממוקם באזור המאפשר בנייה עד 8 קומות.",
            )
        ],
        has_original_permit=True,
        building_permit_number="1985/4521",
        building_permit_date="12/06/1985",
        building_permit_allowed="בניין מגורים בן 8 קומות הכולל 32 יחידות דיור",
        has_completion_cert=True,
        completion_cert_date="03/11/1987",
        balcony_closed_without_permit=False,
        zoning_for_principles="מגורים ג' מיוחד",
        comparison_properties=[
            ComparisonProperty(
                address="רחוב ביאליק 10, רמת גן",
                floor="2",
                rooms="4",
                built_area=88.0,
                balcony_area=10.0,
                price=2_150_000,
                notes="מכירה 03/2025",
            ),
            ComparisonProperty(
                address="רחוב ביאליק 22, רמת גן",
                floor="5",
                rooms="4",
                built_area=95.0,
                balcony_area=14.0,
                price=2_420_000,
                notes="מכירה 02/2025",
            ),
            ComparisonProperty(
                address="רחוב ארלוזורוב 8, רמת גן",
                floor="4",
                rooms="4",
                built_area=90.0,
                balcony_area=0.0,
                price=2_100_000,
                notes="מכירה 01/2025",
            ),
            ComparisonProperty(
                address="רחוב הירקון 5, רמת גן",
                floor="3",
                rooms="4",
                built_area=93.0,
                balcony_area=12.0,
                price=2_280_000,
                notes="מכירה 04/2025",
            ),
        ],
        sqm_equiv_price=23_500,
        final_value=2_300_000,
        purchase_date="15/06/2010",
        purchase_price=900_000,
    )


def sample_market() -> PropertyInput:
    """Demo: 3-room apartment, Tel Aviv, שוק."""
    base = sample_standard19()
    base.report_purpose = ReportPurpose.MARKET
    base.rooms = 3.0
    base.registered_area = 72.0
    base.built_area = 70.0
    base.balcony_area = 8.0
    base.final_value = 1_850_000
    base.sqm_equiv_price = 25_000
    base.purchase_date = ""
    base.purchase_price = 0.0
    return base


def sample_evacuation() -> PropertyInput:
    """Demo: 3-room apartment, פינוי-בינוי."""
    base = sample_standard19()
    base.report_purpose = ReportPurpose.EVACUATION
    base.future_value_a = 1_900_000
    base.future_value_b = 2_800_000
    return base
