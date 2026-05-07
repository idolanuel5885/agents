"""Auto-fill parcel and planning data from open external services.

Pipeline (one address in, structured data out):

1. Geocode the Hebrew address through OpenStreetMap Nominatim → (lat, lon).
2. Project (lat, lon) WGS84 → Israeli Transverse Mercator (EPSG:2039).
3. Query the iplan.gov.il "תכנון זמין" ArcGIS service for the parcel,
   neighbouring parcels, current land-use designation, and applicable
   plans at that point.
4. Reduce neighbouring parcel polygons into four cardinal boundary
   descriptions (north / south / east / west) for the report.

The whole chain is best-effort: any step may fail (network, missing
service, address not found) and the public entry point
:func:`lookup_parcel` always returns a structured result that the Web
form can show to the appraiser. Generation is never blocked — the
appraiser can always fall back to manual input.

Per CLAUDE.md A.7 the result must be presented to the appraiser with
its source visible; the Web layer adds the source attribution when
populating the form.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── External services ────────────────────────────────────────────────────────

# Nominatim requires a descriptive User-Agent identifying the application
# (anonymous calls are blocked). See https://operations.osmfoundation.org/policies/nominatim/
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "shuma-mekarkein/1.0 (real-estate appraisal automation)"

# Israeli Planning Administration "Xplan" public ArcGIS MapServer.
# Documentation: https://ags.iplan.gov.il/arcgis/rest/services/PlanningPublic/Xplan/MapServer
_XPLAN_BASE = (
    "https://ags.iplan.gov.il/arcgis/rest/services/PlanningPublic/Xplan/MapServer"
)

# Layer hints — the Xplan service publishes ~30+ layers and their IDs have
# changed across versions. Rather than hardcoding IDs we discover the
# right layer at runtime by matching the substring against each layer's
# name. The first match wins.
#
# These hints are based on the layer naming conventions used by the
# service ("PARCEL_ALL", "LandDesignation_ITM", "PlanMavat" / "תוכנית").
# If discovery fails the lookup degrades gracefully and the field
# remains empty for the appraiser to fill manually.
_LAYER_NAME_HINTS = {
    "parcel": ("parcel_all", "parcel", "חלק"),
    "land_use": ("designation", "landuse", "land_use", "ייעוד", "יעוד"),
    "plans":    ("planmavat", "plan", "תוכני", "תכני"),
}

# HTTP timeout (seconds). Web search has shown XPlan can be slow under
# load — keep the timeout long enough to be usable but short enough not
# to lock up the form for a minute.
_HTTP_TIMEOUT = 12.0

# A small buffer (in metres) used when querying ArcGIS for the parcel
# neighbours. The query uses an "intersects" geometry — a tiny envelope
# around the geocoded point catches the parcel even if the geocoder is
# slightly off.
_POINT_BUFFER_M = 1.0

# Buffer around the candidate parcel used to find neighbouring parcels
# for boundary description (in metres).
_NEIGHBOUR_BUFFER_M = 5.0


# ── Result types ─────────────────────────────────────────────────────────────


@dataclass
class PlanRef:
    """A single applicable plan."""
    number: str = ""
    name: str = ""
    designation: str = ""
    year: str = ""

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "designation": self.designation,
            "year": self.year,
        }


@dataclass
class ParcelLookupResult:
    """Structured result of a full address → parcel data lookup.

    All fields are best-effort. ``ok`` is True when at least the parcel
    identification (block + parcel) was retrieved. ``warnings`` is a
    list of Hebrew strings that the form can show to the appraiser.
    """
    ok: bool = False
    block: str = ""
    parcel: str = ""
    land_use: str = ""
    plans: list[PlanRef] = field(default_factory=list)
    north_boundary: str = ""
    south_boundary: str = ""
    east_boundary: str = ""
    west_boundary: str = ""
    warnings: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "block": self.block,
            "parcel": self.parcel,
            "land_use": self.land_use,
            "plans": [p.to_dict() for p in self.plans],
            "boundaries": {
                "north": self.north_boundary,
                "south": self.south_boundary,
                "east": self.east_boundary,
                "west": self.west_boundary,
            },
            "warnings": self.warnings,
            "error": self.error,
        }


class LookupError_(RuntimeError):
    """Raised internally when a step in the pipeline fails."""


# ── Step 1: geocoding ────────────────────────────────────────────────────────


def _geocode(address: str) -> tuple[float, float]:
    """Resolve a Hebrew address to (lat, lon) via Nominatim.

    Raises :class:`LookupError_` if the address is empty, the request
    fails, or no result is returned.
    """
    addr = (address or "").strip()
    if not addr:
        raise LookupError_("הכתובת ריקה")

    try:
        import requests  # local import — only needed when the feature is used
    except ImportError as e:
        raise LookupError_(f"חבילת requests אינה מותקנת: {e}") from e

    params = {
        "q": addr,
        "format": "json",
        "limit": 1,
        "countrycodes": "il",
        "accept-language": "he",
    }
    headers = {"User-Agent": _USER_AGENT}

    try:
        resp = requests.get(
            _NOMINATIM_URL, params=params, headers=headers,
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json()
    except Exception as e:
        raise LookupError_(f"שירות הגיאוקודינג אינו זמין: {e}") from e

    if not results:
        raise LookupError_("הכתובת לא זוהתה על ידי שירות המפות")

    try:
        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
    except (KeyError, TypeError, ValueError) as e:
        raise LookupError_(f"תשובת הגיאוקודינג בפורמט לא צפוי: {e}") from e

    return lat, lon


# ── Step 2: WGS84 → ITM (EPSG:2039) ──────────────────────────────────────────


def _to_itm(lat: float, lon: float) -> tuple[float, float]:
    """Project (lat, lon) WGS84 to Israeli Transverse Mercator (EPSG:2039).

    Returns (x, y) in metres. Raises :class:`LookupError_` if the
    pyproj package is missing.
    """
    try:
        from pyproj import Transformer
    except ImportError as e:
        raise LookupError_(f"חבילת pyproj אינה מותקנת: {e}") from e

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2039", always_xy=True)
    x, y = transformer.transform(lon, lat)
    return x, y


# ── Step 3: Xplan ArcGIS query ───────────────────────────────────────────────


def _list_layers() -> list[dict]:
    """Return the layer list (id + name) from the Xplan MapServer."""
    try:
        import requests
    except ImportError as e:
        raise LookupError_(f"חבילת requests אינה מותקנת: {e}") from e

    try:
        resp = requests.get(
            f"{_XPLAN_BASE}",
            params={"f": "json"},
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise LookupError_(f"שירות תכנון זמין אינו זמין: {e}") from e

    layers = data.get("layers") or []
    return [{"id": l.get("id"), "name": l.get("name") or ""} for l in layers]


def _find_layer_id(layers: list[dict], hints: tuple[str, ...]) -> Optional[int]:
    """Pick the first layer whose name contains any of the lower-cased hints."""
    for layer in layers:
        name = (layer.get("name") or "").lower()
        for hint in hints:
            if hint.lower() in name:
                return layer.get("id")
    return None


def _query_layer(
    layer_id: int,
    geometry: dict,
    geometry_type: str,
    out_fields: str = "*",
) -> list[dict]:
    """Run an ArcGIS spatial ``query`` and return the features list."""
    try:
        import requests
    except ImportError as e:
        raise LookupError_(f"חבילת requests אינה מותקנת: {e}") from e

    import json as _json

    params = {
        "f": "json",
        "geometry": _json.dumps(geometry),
        "geometryType": geometry_type,
        "inSR": "2039",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "true",
        "outSR": "2039",
    }

    try:
        resp = requests.get(
            f"{_XPLAN_BASE}/{layer_id}/query",
            params=params,
            timeout=_HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise LookupError_(f"שאילתה לשירות תכנון זמין נכשלה: {e}") from e

    if "error" in data:
        raise LookupError_(
            f"שירות תכנון זמין החזיר שגיאה: {data['error'].get('message', '')}"
        )

    return data.get("features") or []


def _point_envelope(x: float, y: float, buffer_m: float) -> dict:
    """Build an ArcGIS envelope geometry around (x, y)."""
    return {
        "xmin": x - buffer_m,
        "ymin": y - buffer_m,
        "xmax": x + buffer_m,
        "ymax": y + buffer_m,
        "spatialReference": {"wkid": 2039},
    }


# ── Step 4: boundary processing ──────────────────────────────────────────────


def _polygon_from_arcgis(geom: dict):
    """Convert an ArcGIS polygon dict to a shapely Polygon/MultiPolygon."""
    try:
        from shapely.geometry import Polygon, MultiPolygon
    except ImportError as e:
        raise LookupError_(f"חבילת shapely אינה מותקנת: {e}") from e

    rings = geom.get("rings") or []
    if not rings:
        return None
    polys = []
    for ring in rings:
        if len(ring) >= 4:
            polys.append(Polygon(ring))
    if not polys:
        return None
    if len(polys) == 1:
        return polys[0]
    return MultiPolygon(polys)


def _describe_neighbour(attrs: dict, fallback_label: str) -> str:
    """Build a Hebrew description of a neighbouring feature."""
    block = (
        attrs.get("GUSH_NUM")
        or attrs.get("gush_num")
        or attrs.get("GUSH")
        or attrs.get("Gush")
    )
    parcel = (
        attrs.get("PARCEL")
        or attrs.get("parcel")
        or attrs.get("HELKA")
        or attrs.get("Helka")
        or attrs.get("HELKA_NUM")
    )
    if block and parcel:
        return f"חלקה {parcel} בגוש {block}"
    street = (
        attrs.get("STREET_NAME")
        or attrs.get("street_name")
        or attrs.get("SHEM_RECHOV")
    )
    if street:
        return str(street)
    designation = (
        attrs.get("LandDesignation")
        or attrs.get("DESIGNATION")
        or attrs.get("ZONE")
        or attrs.get("designation")
    )
    if designation:
        return str(designation)
    return fallback_label


def _direction(dx: float, dy: float) -> str:
    """Return cardinal direction (north/south/east/west) for the offset.

    EPSG:2039 has +x=east and +y=north so this is a straightforward
    quadrant test based on the dominant axis. Falls back to "north"
    only when both deltas are zero, which doesn't happen for non-overlapping
    polygons.
    """
    if abs(dx) >= abs(dy):
        return "east" if dx >= 0 else "west"
    return "north" if dy >= 0 else "south"


def _process_boundaries(
    subject_polygon,
    neighbour_features: list[dict],
) -> dict[str, str]:
    """Reduce a list of neighbouring features into 4 boundary descriptions.

    For each neighbour we compute the centroid offset from the subject
    parcel's centroid, classify it into a cardinal quadrant by the
    dominant axis, and pick the closest neighbour per quadrant.

    This is the simplified strategy the brief calls out as acceptable —
    not pixel-perfect for irregular shapes, but reliable enough for the
    appraiser to verify before signing.
    """
    if subject_polygon is None:
        return {"north": "", "south": "", "east": "", "west": ""}

    sx, sy = subject_polygon.centroid.x, subject_polygon.centroid.y

    # candidate per direction: (distance, description)
    best: dict[str, tuple[float, str]] = {}

    for feat in neighbour_features:
        geom = feat.get("geometry") or {}
        attrs = feat.get("attributes") or {}
        npoly = _polygon_from_arcgis(geom)
        if npoly is None:
            continue
        # Skip the subject itself: same block+parcel == ours
        try:
            if npoly.intersection(subject_polygon).area / max(subject_polygon.area, 1e-6) > 0.5:
                continue
        except Exception:
            pass
        cx, cy = npoly.centroid.x, npoly.centroid.y
        dx, dy = cx - sx, cy - sy
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            continue
        direction = _direction(dx, dy)
        dist = math.hypot(dx, dy)
        desc = _describe_neighbour(attrs, fallback_label="")
        if not desc:
            continue
        cur = best.get(direction)
        if cur is None or dist < cur[0]:
            best[direction] = (dist, desc)

    return {
        "north": best.get("north", (0, ""))[1],
        "south": best.get("south", (0, ""))[1],
        "east":  best.get("east",  (0, ""))[1],
        "west":  best.get("west",  (0, ""))[1],
    }


# ── Plan attribute extraction ────────────────────────────────────────────────


def _extract_plan(attrs: dict) -> Optional[PlanRef]:
    """Build a PlanRef from an Xplan plans-layer feature attributes dict."""
    number = (
        attrs.get("PL_NUMBER")
        or attrs.get("plan_number")
        or attrs.get("PLAN_NUM")
        or attrs.get("pl_name")
        or attrs.get("PL_NAME")
        or ""
    )
    name = attrs.get("PL_NAME") or attrs.get("plan_name") or ""
    designation = (
        attrs.get("LandDesignation")
        or attrs.get("DESIGNATION")
        or attrs.get("ZONE")
        or ""
    )
    year = ""
    pub_date = (
        attrs.get("PL_DATE_ISHUR")
        or attrs.get("pl_date_ishur")
        or attrs.get("PUBLISH_DATE")
        or attrs.get("DATE_ISHUR")
    )
    if pub_date:
        try:
            # ArcGIS returns epoch milliseconds for date fields
            ts_ms = int(pub_date)
            from datetime import datetime
            year = str(datetime.utcfromtimestamp(ts_ms / 1000).year)
        except (ValueError, TypeError):
            year = str(pub_date)[:4]

    if not (number or name):
        return None
    return PlanRef(
        number=str(number),
        name=str(name),
        designation=str(designation),
        year=year,
    )


# ── Public entry point ───────────────────────────────────────────────────────


def lookup_parcel(address: str) -> ParcelLookupResult:
    """Run the full pipeline for an address. Always returns a result.

    Hebrew error/warning messages are placed on the result rather than
    raised — the caller (Web form) treats this as best-effort and
    surfaces the messages to the appraiser without blocking generation.
    """
    result = ParcelLookupResult()

    # Step 1: geocode
    try:
        lat, lon = _geocode(address)
    except LookupError_ as e:
        result.error = str(e)
        return result

    # Step 2: project to ITM
    try:
        x, y = _to_itm(lat, lon)
    except LookupError_ as e:
        result.error = str(e)
        return result

    # Step 3: discover layers + query the parcel at (x, y)
    try:
        layers = _list_layers()
    except LookupError_ as e:
        result.error = str(e)
        return result

    parcel_layer_id = _find_layer_id(layers, _LAYER_NAME_HINTS["parcel"])
    land_use_layer_id = _find_layer_id(layers, _LAYER_NAME_HINTS["land_use"])
    plans_layer_id = _find_layer_id(layers, _LAYER_NAME_HINTS["plans"])

    if parcel_layer_id is None:
        result.error = "לא נמצאה שכבת חלקות בשירות תכנון זמין"
        return result

    point_env = _point_envelope(x, y, _POINT_BUFFER_M)
    try:
        subject_features = _query_layer(parcel_layer_id, point_env, "esriGeometryEnvelope")
    except LookupError_ as e:
        result.error = str(e)
        return result

    if not subject_features:
        result.error = "לא נמצאה חלקה בנקודה זו"
        return result

    # Pick the first parcel as the subject
    subject = subject_features[0]
    s_attrs = subject.get("attributes") or {}
    s_geom  = subject.get("geometry") or {}
    subject_polygon = _polygon_from_arcgis(s_geom)

    block_val = (
        s_attrs.get("GUSH_NUM") or s_attrs.get("gush_num")
        or s_attrs.get("GUSH") or s_attrs.get("Gush") or ""
    )
    parcel_val = (
        s_attrs.get("PARCEL") or s_attrs.get("parcel")
        or s_attrs.get("HELKA") or s_attrs.get("Helka") or ""
    )
    result.block = str(block_val) if block_val != "" else ""
    result.parcel = str(parcel_val) if parcel_val != "" else ""

    # Step 3b: land-use designation at the same point
    if land_use_layer_id is not None:
        try:
            lu_features = _query_layer(land_use_layer_id, point_env, "esriGeometryEnvelope")
            if lu_features:
                lu_attrs = lu_features[0].get("attributes") or {}
                lu = (
                    lu_attrs.get("LandDesignation")
                    or lu_attrs.get("DESIGNATION")
                    or lu_attrs.get("ZONE")
                    or lu_attrs.get("LAND_USE")
                    or ""
                )
                result.land_use = str(lu)
        except LookupError_ as e:
            logger.warning("land-use query failed: %s", e)
            result.warnings.append("ייעוד הקרקע לא נטען — יש להשלים ידנית")
    else:
        result.warnings.append("שכבת ייעודי קרקע לא נמצאה בשירות")

    # Step 3c: applicable plans at the same point
    if plans_layer_id is not None:
        try:
            plan_features = _query_layer(plans_layer_id, point_env, "esriGeometryEnvelope")
            for feat in plan_features:
                plan = _extract_plan(feat.get("attributes") or {})
                if plan is not None:
                    result.plans.append(plan)
        except LookupError_ as e:
            logger.warning("plans query failed: %s", e)
            result.warnings.append("רשימת התוכניות לא נטענה — יש להשלים ידנית")
    else:
        result.warnings.append("שכבת תוכניות לא נמצאה בשירות")

    # Step 4: boundaries — query neighbours around the subject parcel
    if subject_polygon is not None:
        try:
            from shapely.geometry import box
            minx, miny, maxx, maxy = subject_polygon.bounds
            envelope = {
                "xmin": minx - _NEIGHBOUR_BUFFER_M,
                "ymin": miny - _NEIGHBOUR_BUFFER_M,
                "xmax": maxx + _NEIGHBOUR_BUFFER_M,
                "ymax": maxy + _NEIGHBOUR_BUFFER_M,
                "spatialReference": {"wkid": 2039},
            }
            neighbours = _query_layer(parcel_layer_id, envelope, "esriGeometryEnvelope")
            boundaries = _process_boundaries(subject_polygon, neighbours)
            result.north_boundary = boundaries["north"]
            result.south_boundary = boundaries["south"]
            result.east_boundary  = boundaries["east"]
            result.west_boundary  = boundaries["west"]
            if not any(boundaries.values()):
                result.warnings.append("גבולות החלקה לא זוהו — יש להשלים ידנית")
        except LookupError_ as e:
            logger.warning("boundary query failed: %s", e)
            result.warnings.append("גבולות החלקה לא נטענו — יש להשלים ידנית")
        except Exception as e:
            logger.warning("boundary processing failed: %s", e)
            result.warnings.append("עיבוד הגבולות נכשל — יש להשלים ידנית")
    else:
        result.warnings.append("פוליגון החלקה לא הוחזר — לא ניתן לחשב גבולות")

    result.ok = bool(result.block and result.parcel)
    return result
