"""Data models for real estate appraisal reports."""
from dataclasses import dataclass, field
from typing import List
from enum import Enum


class ReportPurpose(str, Enum):
    MARKET = "שוק"
    STANDARD_19 = "תקן_19"
    EVACUATION = "פינוי_בינוי"


class RightsType(str, Enum):
    PRIVATE = "בעלות_פרטית"
    LEASE_RAMI = "חכירה_רמי"
    LEASE_COMPANY = "חכירה_חברה"


class FinishLevel(str, Enum):
    BASIC = "בסיסית"
    GOOD = "טובה"
    VERY_GOOD = "טובה מאוד"


class PermitStatus(str, Enum):
    PERMIT = "על פי היתר"
    DEVIATIONS = "חריגות"


class ClientGender(str, Enum):
    MALE = "זכר"
    FEMALE = "נקבה"
    COMPANY = "חברה"
    BANK = "בנק"


@dataclass
class ComparisonProperty:
    address: str
    floor: str
    rooms: str
    built_area: float
    balcony_area: float
    price: float
    notes: str = ""

    @property
    def equiv_area(self) -> float:
        b = self.balcony_area
        if b <= 0:
            return self.built_area
        elif b <= 50:
            return self.built_area + b * 0.5
        elif b <= 100:
            return self.built_area + 50 * 0.5 + (b - 50) * 0.25
        else:
            return self.built_area + 50 * 0.5 + 50 * 0.25 + (b - 100) * 0.1

    @property
    def price_per_sqm(self) -> float:
        ea = self.equiv_area
        return self.price / ea if ea > 0 else 0


@dataclass
class PlanningPlan:
    plan_number: str
    gazette_number: str
    gazette_date: str
    zoning: str
    notes: str = ""


@dataclass
class PropertyInput:
    # Report metadata
    report_number: str
    report_date: str              # DD/MM/YYYY
    determining_date: str         # written in words (e.g. "6 ביולי 2025")
    visit_date: str               # DD/MM/YYYY
    report_purpose: ReportPurpose

    # Client
    client_name: str
    client_gender: ClientGender

    # Property identification
    city: str
    street: str
    house_number: str
    address: str                  # full address string
    block: str
    parcel: str
    sub_parcel: str

    # Rights
    rights_type: RightsType
    rights_owner: str
    common_property_share: str    # e.g. "2500/100000"
    registration_date: str        # date of tabu extract
    floor_description: str        # as appears in tabu

    # Building
    build_year: int
    total_floors: int
    units_count: int
    ground_floor_use: str
    building_physical_condition: str

    # Apartment
    rooms: float
    floor: int
    air_directions: str
    registered_area: float
    built_area: float
    balcony_area: float
    ceiling_height: float
    permit_status: PermitStatus
    finish_level: FinishLevel

    # Attachments
    has_parking: bool
    parking_description: str
    has_storage: bool
    storage_description: str
    has_garden: bool
    garden_area: float

    # Rental
    is_rented: bool
    tenant_name: str
    landlord_name: str
    rental_agreement_date: str
    rental_start_date: str
    rental_end_date: str
    monthly_rent: float

    # Environment
    city_description: str
    neighborhood_name: str
    neighborhood_description: str
    street_type: str              # פנימי / ראשי
    street_direction: str         # חד-סטרי / דו-סטרי

    # Lot
    lot_area: float
    topography: str
    lot_shape: str
    north_boundary: str
    south_boundary: str
    east_boundary: str
    west_boundary: str

    # Planning
    planning_plans: List[PlanningPlan]
    has_original_permit: bool
    building_permit_number: str
    building_permit_date: str
    building_permit_allowed: str
    has_completion_cert: bool
    completion_cert_date: str
    balcony_closed_without_permit: bool

    # Valuation
    zoning_for_principles: str
    comparison_properties: List[ComparisonProperty]
    sqm_equiv_price: float
    final_value: float

    # Tax annex (תקן_19 only)
    purchase_date: str = ""
    purchase_price: float = 0.0

    # פינוי_בינוי
    future_value_a: float = 0.0
    future_value_b: float = 0.0

    # Free-text notes appended to the report
    special_notes: str = ""
