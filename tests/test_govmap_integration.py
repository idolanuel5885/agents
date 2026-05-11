"""Mock-based tests for the Govmap deals integration.

Replaces the old ``test_nadlan_integration.py``. Covers:

* :mod:`real_estate.govmap_client` — autocomplete parsing, polygon lookup,
  street-deals mapping (units 1–10 below).
* :mod:`real_estate.web` — the two new endpoints and how they degrade
  on each error code (units 11–15).
* End-to-end report rendering — kept from the previous suite — verifies
  outlier marker + balcony-column hiding still work (unit 16).
* A live smoke test, skipped by default (unit 17).
"""
from __future__ import annotations

import io
import os
import sys
from unittest.mock import patch, MagicMock

import pytest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from real_estate import govmap_client  # noqa: E402
from real_estate.govmap_client import (  # noqa: E402
    GovmapFetchError,
    autocomplete_address,
    get_polygon_id_for_address,
    get_street_deals,
    _format_floor,
)
from real_estate.models import ComparisonProperty  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_response(status: int = 200, body=None, raise_on_json: bool = False):
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 400
    resp.content = b"x"
    resp.text = "x"
    if raise_on_json:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = body if body is not None else {}
    return resp


# ── 1. autocomplete_address — happy path ─────────────────────────────────────


def test_autocomplete_returns_parsed_results():
    body = {
        "resultsCount": 2,
        "results": [
            {
                "id": "address|ADDRESS|64834989|רוטשילד 1|תל אביב",
                "text": "רוטשילד 1, תל אביב",
                "type": "address",
                "shape": "POINT(3871406.911 3772053.769)",
            },
            {
                "id": "street|STREET_MID_POINT|36595|רוטשילד|תל אביב",
                "text": "רוטשילד, תל אביב",
                "type": "street",
                "shape": "POINT(3871500.0 3772100.0)",
            },
        ],
    }
    with patch.object(govmap_client._session, "post", return_value=_mock_response(body=body)):
        out = autocomplete_address("רוטשילד")

    assert len(out) == 2
    assert out[0]["display_name"] == "רוטשילד 1, תל אביב"
    assert out[0]["type"] == "address"
    assert out[0]["addr_id"] == "64834989"
    assert out[0]["itm_x"] == 3871406.911
    assert out[0]["itm_y"] == 3772053.769
    # Street rows still come back but with addr_id=None — the UI filters them.
    assert out[1]["type"] == "street"
    assert out[1]["addr_id"] is None


def test_autocomplete_short_query_short_circuits():
    """A 1-char query is too noisy — return [] without hitting the network."""
    with patch.object(govmap_client._session, "post") as p:
        out = autocomplete_address("ר")
    assert out == []
    p.assert_not_called()


def test_autocomplete_blank_query_short_circuits():
    with patch.object(govmap_client._session, "post") as p:
        out = autocomplete_address("   ")
    assert out == []
    p.assert_not_called()


def test_autocomplete_500_raises_hebrew_error():
    with patch.object(govmap_client._session, "post", return_value=_mock_response(status=500)):
        with pytest.raises(GovmapFetchError) as exc:
            autocomplete_address("רוטשילד")
    assert exc.value.code == "AUTOCOMPLETE_UNAVAILABLE"
    assert "השלמת" in exc.value.message_he


def test_autocomplete_connection_error_raises_hebrew():
    with patch.object(govmap_client._session, "post", side_effect=ConnectionError("dns")):
        with pytest.raises(GovmapFetchError) as exc:
            autocomplete_address("רוטשילד")
    assert exc.value.code == "AUTOCOMPLETE_UNAVAILABLE"


def test_autocomplete_unparseable_shape_is_skipped():
    body = {
        "results": [
            {"id": "address|ADDRESS|1|x|y", "text": "x", "type": "address", "shape": "WRONG"},
            {"id": "address|ADDRESS|2|x|y", "text": "y", "type": "address", "shape": "POINT(1.0 2.0)"},
        ],
    }
    with patch.object(govmap_client._session, "post", return_value=_mock_response(body=body)):
        out = autocomplete_address("xy")
    assert len(out) == 1
    assert out[0]["addr_id"] == "2"


# ── 2. get_polygon_id_for_address ────────────────────────────────────────────


def test_polygon_lookup_extracts_polygon_id():
    body = {"polygon_id": "53292326", "street_id": "50001103"}
    with patch.object(govmap_client._session, "post", return_value=_mock_response(body=body)):
        pid = get_polygon_id_for_address("64834989")
    assert pid == "53292326"


def test_polygon_lookup_extracts_from_nested_data():
    body = {"data": {"polygonId": "53292326"}}
    with patch.object(govmap_client._session, "post", return_value=_mock_response(body=body)):
        pid = get_polygon_id_for_address("64834989")
    assert pid == "53292326"


def test_polygon_lookup_returns_none_when_absent():
    body = {"some_other_field": 1}
    with patch.object(govmap_client._session, "post", return_value=_mock_response(body=body)):
        pid = get_polygon_id_for_address("64834989")
    assert pid is None


def test_polygon_lookup_500_raises():
    with patch.object(govmap_client._session, "post", return_value=_mock_response(status=503)):
        with pytest.raises(GovmapFetchError) as exc:
            get_polygon_id_for_address("64834989")
    assert exc.value.code == "POLYGON_LOOKUP_FAILED"


def test_polygon_lookup_blank_addr_id_raises():
    with patch.object(govmap_client._session, "post") as p:
        with pytest.raises(GovmapFetchError) as exc:
            get_polygon_id_for_address("")
    assert exc.value.code == "POLYGON_LOOKUP_FAILED"
    p.assert_not_called()


# ── 3. get_street_deals ──────────────────────────────────────────────────────


def _deal(date_, price=3_000_000, area=80, rooms=3, floor=3, street="רוטשילד", house="5"):
    return {
        "streetNameHeb": street,
        "houseNum": house,
        "assetRoomNum": rooms,
        "floorNo": floor,
        "assetArea": area,
        "dealAmount": price,
        "dealDate": date_,
    }


def test_street_deals_maps_fields_correctly():
    body = [_deal("2025-02-15T00:00:00.000Z", price=4_500_000, area=110, rooms=4, floor=5, street="רוטשילד", house="12")]
    with patch.object(govmap_client._session, "get", return_value=_mock_response(body=body)):
        deals = get_street_deals("53292326", limit=5)

    assert len(deals) == 1
    d = deals[0]
    assert isinstance(d, ComparisonProperty)
    assert d.address == "רוטשילד 12"
    assert d.rooms == "4"
    assert d.floor == "5"
    assert d.built_area == 110.0
    assert d.price == 4_500_000.0
    assert d.balcony_area is None
    assert d.is_outlier is False
    # Date should be formatted Israeli style (D.M.YYYY, not zero-padded).
    assert d.notes == "15.2.2025"


def test_street_deals_sorts_descending_and_limits():
    body = [
        _deal("2023-01-01T00:00:00Z", price=1, area=10, house="a"),
        _deal("2025-06-30T00:00:00Z", price=2, area=10, house="b"),
        _deal("2024-09-15T00:00:00Z", price=3, area=10, house="c"),
        _deal("2025-12-01T00:00:00Z", price=4, area=10, house="d"),
    ]
    with patch.object(govmap_client._session, "get", return_value=_mock_response(body=body)):
        deals = get_street_deals("p", limit=2)

    assert len(deals) == 2
    assert deals[0].notes == "1.12.2025"  # newest
    assert deals[1].notes == "30.6.2025"  # second newest


def test_street_deals_empty_response_is_not_error():
    with patch.object(govmap_client._session, "get", return_value=_mock_response(body=[])):
        deals = get_street_deals("53292326")
    assert deals == []


def test_street_deals_drops_rows_missing_price_or_area():
    body = [
        _deal("2025-02-15T00:00:00Z", price=0, area=80),   # bad price
        _deal("2025-03-15T00:00:00Z", price=100, area=0),  # bad area
        _deal("2025-04-15T00:00:00Z", price=100, area=80, house="ok"),
    ]
    with patch.object(govmap_client._session, "get", return_value=_mock_response(body=body)):
        deals = get_street_deals("53292326")
    assert len(deals) == 1
    assert deals[0].address.endswith("ok")


def test_street_deals_500_raises():
    with patch.object(govmap_client._session, "get", return_value=_mock_response(status=502)):
        with pytest.raises(GovmapFetchError) as exc:
            get_street_deals("p")
    assert exc.value.code == "DEALS_FETCH_FAILED"


def test_street_deals_handles_dict_wrapper():
    """Server may wrap the list in {"deals": [...]}."""
    body = {"deals": [_deal("2025-01-01T00:00:00Z", house="z")]}
    with patch.object(govmap_client._session, "get", return_value=_mock_response(body=body)):
        deals = get_street_deals("p")
    assert len(deals) == 1


# ── 4. Hebrew floor parsing ──────────────────────────────────────────────────


def test_format_floor_translates_hebrew_words():
    assert _format_floor("אחת עשרה") == "11"
    assert _format_floor("שתיים עשרה") == "12"
    assert _format_floor("קרקע") == "0"
    assert _format_floor("ראשונה") == "1"
    # Unknown Hebrew word → "" (appraiser fills manually, never invented).
    assert _format_floor("לא מוכר") == ""
    # Numeric pass-through.
    assert _format_floor(7) == "7"
    assert _format_floor("3") == "3"


# ── 5. /shuma/autocomplete endpoint ──────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from real_estate.web import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_autocomplete_endpoint_success(client):
    with patch("real_estate.govmap_client.autocomplete_address") as p:
        p.return_value = [{"display_name": "x", "type": "address", "itm_x": 1.0, "itm_y": 2.0, "addr_id": "9"}]
        r = client.post("/shuma/autocomplete", json={"query": "רוטשילד"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["results"][0]["addr_id"] == "9"


def test_autocomplete_endpoint_failure_returns_hebrew(client):
    with patch("real_estate.govmap_client.autocomplete_address") as p:
        p.side_effect = GovmapFetchError("AUTOCOMPLETE_UNAVAILABLE", "שירות לא זמין")
        r = client.post("/shuma/autocomplete", json={"query": "רוטשילד"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "AUTOCOMPLETE_UNAVAILABLE"
    assert body["message_he"] == "שירות לא זמין"


# ── 6. /shuma/comparables endpoint ───────────────────────────────────────────


def test_comparables_endpoint_full_flow(client):
    deals = [ComparisonProperty(
        address="רוטשילד 12", floor="5", rooms="4",
        built_area=110.0, balcony_area=None, price=4_500_000,
        notes="15.2.2025", is_outlier=False,
    )]
    with patch("real_estate.govmap_client.get_polygon_id_for_address", return_value="53292326"), \
         patch("real_estate.govmap_client.get_street_deals", return_value=deals):
        r = client.post("/shuma/comparables", json={"addr_id": "64834989", "limit": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert len(body["deals"]) == 1
    assert body["deals"][0]["address"] == "רוטשילד 12"
    assert body["fetched_at"]
    assert "govmap" in body["source"]


def test_comparables_endpoint_polygon_lookup_failed(client):
    with patch("real_estate.govmap_client.get_polygon_id_for_address") as p:
        p.side_effect = GovmapFetchError("POLYGON_LOOKUP_FAILED", "לא הצלחנו לזהות")
        r = client.post("/shuma/comparables", json={"addr_id": "64834989"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "POLYGON_LOOKUP_FAILED"


def test_comparables_endpoint_polygon_returns_none(client):
    """No street polygon for this address → graceful POLYGON_LOOKUP_FAILED."""
    with patch("real_estate.govmap_client.get_polygon_id_for_address", return_value=None):
        r = client.post("/shuma/comparables", json={"addr_id": "64834989"})
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "POLYGON_LOOKUP_FAILED"


def test_comparables_endpoint_no_deals_found_is_success(client):
    with patch("real_estate.govmap_client.get_polygon_id_for_address", return_value="p"), \
         patch("real_estate.govmap_client.get_street_deals", return_value=[]):
        r = client.post("/shuma/comparables", json={"addr_id": "64834989"})
    body = r.json()
    assert body["success"] is True
    assert body["error_code"] == "NO_DEALS_FOUND"
    assert body["deals"] == []


def test_comparables_endpoint_blank_addr_id(client):
    r = client.post("/shuma/comparables", json={"addr_id": ""})
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "POLYGON_LOOKUP_FAILED"


def test_comparables_endpoint_deals_fetch_failed(client):
    with patch("real_estate.govmap_client.get_polygon_id_for_address", return_value="p"), \
         patch("real_estate.govmap_client.get_street_deals") as p:
        p.side_effect = GovmapFetchError("DEALS_FETCH_FAILED", "שירות לא זמין")
        r = client.post("/shuma/comparables", json={"addr_id": "64834989"})
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "DEALS_FETCH_FAILED"


# ── 7. End-to-end report: outlier marker + balcony columns hidden ────────────


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
            notes="11.2.2025", is_outlier=True,
        ),
        ComparisonProperty(
            address="רוטשילד 7, תל אביב", floor="2", rooms="3",
            built_area=85.0, balcony_area=None, price=3_200_000,
            notes="4.11.2024", is_outlier=False,
        ),
        ComparisonProperty(
            address="רוטשילד 9, תל אביב", floor="4", rooms="3",
            built_area=82.0, balcony_area=12.0, price=3_350_000,
            notes="3.10.2024", is_outlier=False,
        ),
    ]

    docx_bytes = generate_report_bytes(data)
    doc = Document(io.BytesIO(docx_bytes))
    text = "\n".join(p.text for p in doc.paragraphs) + "\n" + "\n".join(
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    )

    assert "(*) 1" in text
    assert "חריגות ביחס למקובל" in text
    assert "2025-11-12" in text
    table_headers = [
        cell.text for table in doc.tables for cell in table.rows[0].cells
    ]
    assert "מרפסת מ\"ר" not in table_headers


# ── 8. Live smoke (skipped by default) ───────────────────────────────────────


@pytest.mark.skip(reason="Live API test — run manually after deploy")
def test_live_endpoint_smoke():  # pragma: no cover
    results = autocomplete_address("רוטשילד תל אביב")
    assert isinstance(results, list) and results
    addr = next(r for r in results if r["type"] == "address" and r["addr_id"])
    polygon_id = get_polygon_id_for_address(addr["addr_id"])
    assert polygon_id
    deals = get_street_deals(polygon_id, limit=3)
    assert isinstance(deals, list)
