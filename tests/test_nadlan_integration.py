"""Mock-based tests for the nadlan.gov.il comparables integration.

These cover the failure paths the Web layer relies on for graceful
degradation (per CLAUDE.md A.8): geocoding error, HTTP 503/429, empty
result set, malformed payload. Network-level tests are skipped by
default — see :func:`test_live_endpoint_smoke` for the live probe and
``nadlan_integration_report.md`` for the manual verification commands.
"""
from __future__ import annotations

import json
import os
import sys
import io
from unittest.mock import patch, MagicMock

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from real_estate import nadlan_client  # noqa: E402
from real_estate.nadlan_client import (  # noqa: E402
    NadlanFetchError,
    address_to_itm,
    fetch_recent_deals,
)
from real_estate.models import ComparisonProperty  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_response(status: int = 200, body=None, raise_on_json: bool = False):
    """Build a minimal stand-in for ``requests.Response``."""
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 400
    if raise_on_json:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = body if body is not None else {}
    return resp


# ── address_to_itm ───────────────────────────────────────────────────────────


def test_address_to_itm_returns_none_when_geocoding_fails():
    """Nominatim down → caller gets None and the form can ask for ITM manually."""
    with patch.object(nadlan_client, "geocode", return_value=None):
        assert address_to_itm("רוטשילד 1, תל אביב") is None


def test_address_to_itm_returns_none_for_blank_address():
    assert address_to_itm("") is None
    assert address_to_itm("   ") is None


def test_address_to_itm_happy_path():
    """Geocoding + ITM projection chain returns an (x, y) tuple."""
    with patch.object(nadlan_client, "geocode", return_value=(32.064, 34.774)), \
         patch.object(nadlan_client, "to_itm", return_value=(180555.0, 663680.0)):
        result = address_to_itm("רוטשילד 1, תל אביב")
    assert result == (180555.0, 663680.0)


# ── fetch_recent_deals: failure modes ────────────────────────────────────────


def test_fetch_recent_deals_503_raises_hebrew_error():
    """503 is the documented "service overloaded" path → Hebrew error message."""
    fake_resp = _mock_response(status=503)
    with patch("requests.post", return_value=fake_resp):
        with pytest.raises(NadlanFetchError) as exc:
            fetch_recent_deals(180555.0, 663680.0, 300)
    assert "נדל" in str(exc.value)  # Hebrew (contains "נדל")


def test_fetch_recent_deals_429_raises_hebrew_error():
    fake_resp = _mock_response(status=429)
    with patch("requests.post", return_value=fake_resp):
        with pytest.raises(NadlanFetchError):
            fetch_recent_deals(180555.0, 663680.0, 300)


def test_fetch_recent_deals_connection_error_raises_hebrew():
    """A pre-HTTP error (DNS/TLS/timeout) is wrapped as NadlanFetchError."""
    with patch("requests.post", side_effect=ConnectionError("boom")):
        with pytest.raises(NadlanFetchError) as exc:
            fetch_recent_deals(180555.0, 663680.0, 300)
    assert "ידנית" in str(exc.value) or "נדל" in str(exc.value)


def test_fetch_recent_deals_malformed_json_raises_hebrew():
    fake_resp = _mock_response(status=200, raise_on_json=True)
    with patch("requests.post", return_value=fake_resp):
        with pytest.raises(NadlanFetchError):
            fetch_recent_deals(180555.0, 663680.0, 300)


# ── fetch_recent_deals: empty / happy paths ──────────────────────────────────


def test_fetch_recent_deals_empty_results():
    """A "no transactions in radius" answer is success-with-empty-list."""
    fake_resp = _mock_response(status=200, body={"AllResults": []})
    with patch("requests.post", return_value=fake_resp):
        result = fetch_recent_deals(180555.0, 663680.0, 300)
    assert result == []


def test_fetch_recent_deals_happy_path_maps_to_comparison_property():
    body = {
        "AllResults": [
            {
                "FULLADRESS": "אורי צבי גרינברג 11, תל אביב",
                "ASSETROOMNUM": 4.0,
                "FLOORNO": "4",
                "DEALNATURE": 113.0,
                "DEALAMOUNT": 4850000,
                "DEALDATETIME": "2025-02-11T00:00:00",
                "BUILDINGYEAR": "1995",
                "NEWPROJECTTEXT": "",
            },
            {
                "FULLADRESS": "אורי צבי גרינברג 7, תל אביב",
                "ASSETROOMNUM": 3.0,
                "FLOORNO": 2,
                "DEALNATURE": 80.0,
                "DEALAMOUNT": 3300000,
                "DEALDATETIME": "2024-11-04T00:00:00",
                "BUILDINGYEAR": 1985,
                "NEWPROJECTTEXT": "פרויקט פינוי בינוי X",
            },
        ]
    }
    fake_resp = _mock_response(status=200, body=body)
    with patch("requests.post", return_value=fake_resp):
        result = fetch_recent_deals(180555.0, 663680.0, 300)

    assert len(result) == 2
    a, b = result
    assert isinstance(a, ComparisonProperty)
    assert a.address == "אורי צבי גרינברג 11, תל אביב"
    assert a.rooms == "4"
    assert a.floor == "4"
    assert a.built_area == 113.0
    assert a.balcony_area is None  # never fabricated
    assert a.price == 4850000
    assert "11.02.2025" in a.notes
    assert "1995" in a.notes
    # contractor flag picked up from NEWPROJECTTEXT
    assert "קבלן" in b.notes


def test_fetch_recent_deals_drops_rows_missing_required_fields():
    """A row with no price or no area is dropped, not synthesised."""
    body = {
        "AllResults": [
            {"FULLADRESS": "x", "DEALAMOUNT": 0, "DEALNATURE": 100},
            {"FULLADRESS": "y", "DEALAMOUNT": 1000000, "DEALNATURE": None},
            {"FULLADRESS": "z", "DEALAMOUNT": 1000000, "DEALNATURE": 50},
        ]
    }
    fake_resp = _mock_response(status=200, body=body)
    with patch("requests.post", return_value=fake_resp):
        result = fetch_recent_deals(180555.0, 663680.0, 300)
    assert len(result) == 1
    assert result[0].address == "z"


def test_fetch_recent_deals_respects_max_results():
    body = {"AllResults": [
        {"FULLADRESS": f"row {i}", "DEALAMOUNT": 1_000_000 + i,
         "DEALNATURE": 60 + i, "ASSETROOMNUM": 3, "FLOORNO": 1}
        for i in range(25)
    ]}
    fake_resp = _mock_response(status=200, body=body)
    with patch("requests.post", return_value=fake_resp):
        result = fetch_recent_deals(180555.0, 663680.0, 300, max_results=10)
    assert len(result) == 10


# ── /shuma/comparables endpoint (FastAPI) ────────────────────────────────────


def test_comparables_endpoint_geocoding_failure_returns_200_with_error_code():
    """The endpoint never returns 5xx — geocoding failure is 200 + error_code."""
    from fastapi.testclient import TestClient
    from real_estate.web import router

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)

    with patch.object(nadlan_client, "address_to_itm", return_value=None):
        client = TestClient(app)
        resp = client.post(
            "/shuma/comparables",
            json={"address": "כתובת לא קיימת", "radius_m": 300},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error_code"] == "GEOCODING_FAILED"
    assert "כתובת" in body["message_he"]


def test_comparables_endpoint_nadlan_failure_returns_200_with_error_code():
    from fastapi.testclient import TestClient
    from real_estate.web import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)

    with patch.object(nadlan_client, "address_to_itm", return_value=(180555.0, 663680.0)), \
         patch.object(nadlan_client, "fetch_recent_deals",
                      side_effect=NadlanFetchError("שירות נדל\"ן לא זמין")):
        client = TestClient(app)
        resp = client.post(
            "/shuma/comparables",
            json={"address": "רוטשילד 1, תל אביב", "radius_m": 300},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error_code"] == "NADLAN_UNAVAILABLE"


def test_comparables_endpoint_empty_results_is_success_with_message():
    from fastapi.testclient import TestClient
    from real_estate.web import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)

    with patch.object(nadlan_client, "address_to_itm", return_value=(180555.0, 663680.0)), \
         patch.object(nadlan_client, "fetch_recent_deals", return_value=[]):
        client = TestClient(app)
        resp = client.post(
            "/shuma/comparables",
            json={"address": "כתובת ריקה", "radius_m": 300},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["deals"] == []
    assert "רדיוס" in body["message_he"]


def test_comparables_endpoint_uses_explicit_itm_when_provided():
    """Manual ITM coordinates bypass geocoding entirely."""
    from fastapi.testclient import TestClient
    from real_estate.web import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)

    fake_deal = ComparisonProperty(
        address="x", floor="1", rooms="3",
        built_area=80.0, balcony_area=None, price=2_000_000, notes="",
    )
    with patch.object(nadlan_client, "address_to_itm") as geo, \
         patch.object(nadlan_client, "fetch_recent_deals", return_value=[fake_deal]):
        client = TestClient(app)
        resp = client.post(
            "/shuma/comparables",
            json={"itm_x": 180555, "itm_y": 663680, "radius_m": 300},
        )
    assert geo.called is False
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["deals"]) == 1
    assert "fetched_at" in body


# ── Live endpoint smoke (skipped — see nadlan_integration_report.md) ─────────


@pytest.mark.skip(
    reason=(
        "Requires network access to nadlan.gov.il. The published endpoint "
        "https://www.nadlan.gov.il/Nadlan.REST/Main/GetAssestAndDeals returns "
        "the SPA HTML (CloudFront fallback) from this sandbox; verify "
        "manually after deploy. See nadlan_integration_report.md."
    )
)
def test_live_endpoint_smoke():  # pragma: no cover — manual verification only
    """Optional live probe — run manually with `pytest -k live --no-skip`."""
    deals = fetch_recent_deals(180555.0, 663680.0, 300, address_label="רוטשילד 1")
    assert isinstance(deals, list)


# ── End-to-end: report renders outlier marker + hides balcony cols ───────────


def test_report_renders_outlier_marker_and_hides_balcony_columns():
    """A 3-deal report with one outlier and 2/3 missing balcony hides the
    balcony / equiv-area columns and emits the outlier footnote.
    """
    from real_estate.demo_data import sample_market
    from real_estate.report_generator import generate_report_bytes
    from docx import Document

    data = sample_market()
    data.comparables_fetched_at = "2025-11-12"
    data.comparison_properties = [
        ComparisonProperty(
            address="רוטשילד 5, תל אביב", floor="3", rooms="3",
            built_area=80.0, balcony_area=None, price=3_000_000,
            notes="11.02.2025", is_outlier=True,
        ),
        ComparisonProperty(
            address="רוטשילד 7, תל אביב", floor="2", rooms="3",
            built_area=85.0, balcony_area=None, price=3_200_000,
            notes="04.11.2024", is_outlier=False,
        ),
        ComparisonProperty(
            address="רוטשילד 9, תל אביב", floor="4", rooms="3",
            built_area=82.0, balcony_area=12.0, price=3_350_000,
            notes="03.10.2024", is_outlier=False,
        ),
    ]

    docx_bytes = generate_report_bytes(data)
    doc = Document(io.BytesIO(docx_bytes))
    text = "\n".join(p.text for p in doc.paragraphs) + "\n" + "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )

    # Outlier marker on row 1 + outlier footnote
    assert "(*) 1" in text
    assert "חריגות ביחס למקובל" in text
    # Source provenance footnote with the fetched date
    assert "2025-11-12" in text
    assert "נדל" in text
    # Balcony columns hidden because only 1 of 3 had a balcony figure;
    # the body of the table should not contain the literal header.
    table_headers = [
        cell.text
        for table in doc.tables
        for cell in table.rows[0].cells
    ]
    assert "מרפסת מ\"ר" not in table_headers
