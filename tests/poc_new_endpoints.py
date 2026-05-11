"""PoC #10–11: discover whether Govmap deals-by-radius returns polygons.

Iteration motivation: the current `street-deals/{polygon_id}` flow
returns deals for a single building because `polygon_id` from
`deal-info` is parcel-level, not street-level. `nitzpo/nadlan-mcp`
documents an alternative two-step flow:

1. `GET /api/real-estate/deals/{x y}/{radius}` → polygon metadata in
   radius (not deals themselves).
2. For each polygon → `GET /api/real-estate/street-deals/{polygon_id}`
   → the deals on that polygon.
3. Merge + sort by date.

This probe answers:

* Does step 1 return polygons at radii > 50m? (We've already seen 50m
  return `[]`.)
* What field name carries the polygon id we'd feed step 2?
* Does step 2 then yield recent (2024-2025) deals from a wider area?

Run via the temporary ``GET /shuma/poc-test`` endpoint or directly as
``DEBUG_NADLAN=1 python tests/poc_new_endpoints.py``. Both paths use
``run_poc()`` which captures stdout into a string.

This file lives only long enough to get the answer; it will be
removed in the follow-up that fixes ``govmap_client.py``.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import requests


_GOVMAP_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.govmap.gov.il",
    "Referer": "https://www.govmap.gov.il/",
    "User-Agent": "Mozilla/5.0 (test)",
}


def _run_probes() -> None:
    print("=" * 60)
    print("Test 10: Govmap deals/{point}/{radius} — discover polygons in radius")
    print("=" * 60)

    # Coordinates from earlier autocomplete for "רוטשילד תל אביב"
    point_x = 3871406.911338617
    point_y = 3772053.768985697

    for radius in [100, 300, 500, 1000]:
        url = (
            f"https://www.govmap.gov.il/api/real-estate/deals/"
            f"({point_x} {point_y})/{radius}"
        )
        try:
            r = requests.get(url, headers=_GOVMAP_HEADERS, timeout=15)
            print(f"\nRadius {radius}m: status={r.status_code}, size={len(r.content)}")
            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, list):
                        print(f"  Returned list of {len(data)} items")
                        if data:
                            first = data[0]
                            if isinstance(first, dict):
                                print(f"  First item keys: {list(first.keys())}")
                            else:
                                print(f"  First item type: {type(first).__name__}")
                            print(
                                f"  First item: "
                                f"{json.dumps(first, ensure_ascii=False, indent=2)[:600]}"
                            )
                    elif isinstance(data, dict):
                        print(f"  Returned dict with keys: {list(data.keys())}")
                        print(f"  First 600 chars: {r.text[:600]}")
                except Exception as e:
                    print(f"  JSON parse failed: {e}")
                    print(f"  First 300 chars: {r.text[:300]}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 11: Pick first polygon_id from Test 10 result and fetch street-deals")
    print("=" * 60)

    url_poly = (
        f"https://www.govmap.gov.il/api/real-estate/deals/"
        f"({point_x} {point_y})/500"
    )
    try:
        r = requests.get(url_poly, headers=_GOVMAP_HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"Polygon list fetch failed: status={r.status_code}")
        else:
            polys = r.json()
            if isinstance(polys, list) and polys:
                for poly in polys[:2]:
                    poly_id = None
                    if isinstance(poly, dict):
                        for k in ["polygonId", "polygon_id", "id", "objectid", "ObjectID"]:
                            if k in poly:
                                poly_id = poly[k]
                                break
                    if poly_id is None:
                        print(
                            f"\nNo polygon_id field found in: "
                            f"{json.dumps(poly, ensure_ascii=False)[:300]}"
                        )
                        continue

                    deals_url = (
                        f"https://www.govmap.gov.il/api/real-estate/street-deals/{poly_id}"
                    )
                    try:
                        dr = requests.get(deals_url, headers=_GOVMAP_HEADERS, timeout=15)
                        print(
                            f"\nPolygon {poly_id}: street-deals "
                            f"status={dr.status_code}, size={len(dr.content)}"
                        )
                        if dr.status_code == 200:
                            try:
                                ddata = dr.json()
                                if isinstance(ddata, dict):
                                    total = ddata.get("totalCount", "?")
                                    data_list = ddata.get("data", [])
                                    print(
                                        f"  totalCount: {total}, "
                                        f"returned {len(data_list)} deals"
                                    )
                                    for d in data_list[:2]:
                                        if isinstance(d, dict):
                                            addr = (
                                                f"{d.get('streetNameHeb', '?')} "
                                                f"{d.get('houseNum', '?')}"
                                            )
                                            date = d.get("dealDate", "?")
                                            price = d.get("dealAmount", "?")
                                            print(f"    {addr} — {date} — ₪{price}")
                                        else:
                                            print(f"    (non-dict) {d!r}")
                                elif isinstance(ddata, list):
                                    print(f"  Returned list of {len(ddata)} deals")
                                    for d in ddata[:2]:
                                        if isinstance(d, dict):
                                            addr = (
                                                f"{d.get('streetNameHeb', '?')} "
                                                f"{d.get('houseNum', '?')}"
                                            )
                                            date = d.get("dealDate", "?")
                                            price = d.get("dealAmount", "?")
                                            print(f"    {addr} — {date} — ₪{price}")
                            except Exception as e:
                                print(f"  JSON parse failed: {e}")
                    except Exception as e:
                        print(f"  street-deals FAILED: {type(e).__name__}: {e}")
            else:
                print("Test 10 returned no polygons at radius 500. Cannot continue Test 11.")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("PoC complete.")
    print("=" * 60)


def _run_test_12() -> None:
    """Replicates the URL/header shape used by ``nitzpo/nadlan-mcp``.

    Two findings from reading ``nadlan_mcp/govmap/client.py`` line 274:

      * URL: ``/real-estate/deals/{x},{y}/{radius}`` — **comma**, no
        parentheses. Our existing PoC used ``({x} {y})`` (space inside
        parens), which is what we now suspect returns ``[]`` from
        Railway too.
      * Headers: only ``Content-Type: application/json`` and
        ``User-Agent``. No ``Origin``, no ``Referer``. ``Accept`` is
        not set.

    Sequence: autocomplete → take the first ``type=="address"`` result
    → use its ``POINT(x y)`` coords as the search point → query
    deals-by-radius at 50/100/300 m → pick the first polygon and feed
    its ``polygon_id`` into street-deals.
    """
    import re

    base = "https://www.govmap.gov.il/api"
    nitzpo_headers = {
        "Content-Type": "application/json",
        "User-Agent": "NadlanMCP/1.0.0",
    }
    session = requests.Session()
    session.headers.update(nitzpo_headers)

    print()
    print("=" * 60)
    print("Test 12: Replicate nitzpo/nadlan-mcp call shape")
    print("=" * 60)

    # Step 1: autocomplete
    ac_url = f"{base}/search-service/autocomplete"
    ac_payload = {
        "searchText": "רוטשילד 1 תל אביב",
        "language": "he",
        "isAccurate": False,
        "maxResults": 10,
    }
    try:
        ac_resp = session.post(ac_url, json=ac_payload, timeout=15)
        print(f"  autocomplete status={ac_resp.status_code}")
        if not ac_resp.ok:
            print(f"  autocomplete body: {ac_resp.text[:300]}")
            return
        ac_data = ac_resp.json()
    except Exception as e:
        print(f"  autocomplete FAILED: {type(e).__name__}: {e}")
        return

    addr_row = None
    for r in (ac_data.get("results") or []):
        if isinstance(r, dict) and (r.get("type") or "").lower() == "address":
            addr_row = r
            break
    if addr_row is None:
        print("  No type=address row in autocomplete; bailing.")
        return

    shape = addr_row.get("shape") or ""
    m = re.search(r"POINT\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", shape)
    if not m:
        print(f"  Could not parse shape: {shape!r}; bailing.")
        return
    x, y = float(m.group(1)), float(m.group(2))
    print(f"  picked address: {addr_row.get('text')!r}")
    print(f"  parsed POINT: x={x}, y={y}")

    # Step 2: deals-by-radius — nitzpo URL shape with comma
    for radius in [50, 100, 300]:
        url = f"{base}/real-estate/deals/{x},{y}/{radius}"
        try:
            r = session.get(url, timeout=15)
            size = len(r.content)
            print(f"\n  deals/{x},{y}/{radius} → status={r.status_code} size={size}")
            if r.status_code != 200:
                print(f"    body: {r.text[:300]}")
                continue
            try:
                data = r.json()
            except Exception as e:
                print(f"    JSON parse failed: {e}; first 200: {r.text[:200]}")
                continue
            if isinstance(data, list):
                print(f"    Returned list of {len(data)} polygons")
                if data:
                    first = data[0]
                    if isinstance(first, dict):
                        print(f"    First polygon keys: {list(first.keys())}")
                        print(f"    First polygon: {json.dumps(first, ensure_ascii=False)[:500]}")
                    # Step 3: feed the first polygon_id into street-deals
                    poly_id = None
                    if isinstance(first, dict):
                        for k in ("polygon_id", "polygonId", "objectid", "id"):
                            if k in first and first[k] is not None:
                                poly_id = first[k]
                                break
                    if poly_id is not None:
                        sd_url = f"{base}/real-estate/street-deals/{poly_id}"
                        try:
                            sd = session.get(sd_url, timeout=15)
                            print(f"    street-deals/{poly_id} → status={sd.status_code} size={len(sd.content)}")
                            if sd.ok:
                                try:
                                    sdd = sd.json()
                                except Exception as e:
                                    print(f"      JSON parse failed: {e}")
                                    sdd = None
                                if isinstance(sdd, list):
                                    print(f"      Returned list of {len(sdd)} deals")
                                    for d in sdd[:3]:
                                        if isinstance(d, dict):
                                            print(
                                                f"        {d.get('streetNameHeb','?')} "
                                                f"{d.get('houseNum','?')} — "
                                                f"{d.get('dealDate','?')} — "
                                                f"₪{d.get('dealAmount','?')}"
                                            )
                                elif isinstance(sdd, dict):
                                    print(f"      dict keys: {list(sdd.keys())}")
                                    deals = sdd.get("data") or sdd.get("deals") or []
                                    print(f"      totalCount={sdd.get('totalCount','?')} data-len={len(deals) if isinstance(deals, list) else '?'}")
                                    if isinstance(deals, list):
                                        for d in deals[:3]:
                                            if isinstance(d, dict):
                                                print(
                                                    f"        {d.get('streetNameHeb','?')} "
                                                    f"{d.get('houseNum','?')} — "
                                                    f"{d.get('dealDate','?')} — "
                                                    f"₪{d.get('dealAmount','?')}"
                                                )
                        except Exception as e:
                            print(f"    street-deals FAILED: {type(e).__name__}: {e}")
                    break  # one successful radius is enough for the PoC
            elif isinstance(data, dict):
                print(f"    Returned dict with keys: {list(data.keys())}")
                print(f"    First 400 chars: {r.text[:400]}")
        except Exception as e:
            print(f"    FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 12 complete.")
    print("=" * 60)


def _run_all() -> None:
    _run_probes()
    _run_test_12()


def run_poc() -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        _run_all()
    return buf.getvalue()


if __name__ == "__main__":
    _run_all()
