"""
PoC: Test new nadlan/govmap endpoints from the deployed environment.

Two ways to run:

* Locally / from Railway shell:
    DEBUG_NADLAN=1 python tests/poc_new_endpoints.py
* From a browser, after deploy:
    GET https://<your-railway-host>/shuma/poc-test

The browser path uses ``run_poc()`` (defined here) wired into a temporary
``/shuma/poc-test`` text/plain endpoint in ``real_estate/web.py``. Both
paths produce the exact same output.

This is a probe, not a test — there is no pytest collection, no asserts,
and no implementation change to the existing nadlan client. The purpose
is to learn whether Railway can reach the new endpoints discovered in
the production site's Network tab, and what their payloads look like.
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import requests


def _run_probes() -> None:
    """Run the three probes and print results to stdout."""
    print("=" * 60)
    print("Test 1: Govmap autocomplete")
    print("=" * 60)

    try:
        r = requests.post(
            "https://www.govmap.gov.il/api/search-service/autocomplete",
            json={
                "searchText": "רוטשילד תל אביב",
                "language": "he",
                "isAccurate": False,
                "maxResults": 10,
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://www.govmap.gov.il",
                "Referer": "https://www.govmap.gov.il/",
                "User-Agent": "Mozilla/5.0 (test)",
            },
            timeout=15,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print("First 500 chars of body:")
        print(r.text[:500])
        print()
        if r.status_code == 200 and "application/json" in (r.headers.get("content-type") or ""):
            data = r.json()
            results = data.get("results", []) if isinstance(data, dict) else []
            print(
                f"Parsed JSON. resultsCount={data.get('resultsCount') if isinstance(data, dict) else 'n/a'}, "
                f"results length={len(results)}"
            )
            if results:
                first = results[0]
                if isinstance(first, dict):
                    print(
                        f"First result: type={first.get('type')}, "
                        f"text={first.get('text')}, shape={first.get('shape')}"
                    )
                else:
                    print(f"First result (raw): {first!r}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 2: data.nadlan.gov.il deals JSON for Tel Aviv (5000)")
    print("=" * 60)

    try:
        r = requests.get(
            "https://data.nadlan.gov.il/api/pages/settlement/buy/5000.json",
            timeout=20,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print(f"Content-Length: {r.headers.get('content-length')}")
        print(f"Response size (after decompression): {len(r.content)} bytes")
        print("First 800 chars of body:")
        print(r.text[:800])
        print()
        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, dict):
                    print(f"Parsed JSON successfully. Top-level keys: {list(data.keys())}")
                    for k, v in data.items():
                        if isinstance(v, list) and len(v) > 0:
                            first = v[0]
                            if isinstance(first, dict):
                                print(
                                    f"  Key '{k}' has {len(v)} items. "
                                    f"First item keys: {list(first.keys())}"
                                )
                                print(
                                    f"  First item sample: "
                                    f"{json.dumps(first, ensure_ascii=False)[:500]}"
                                )
                            else:
                                print(f"  Key '{k}' has {len(v)} items (not dicts).")
                            break
                elif isinstance(data, list):
                    print(f"Parsed JSON successfully. Top-level is a list of {len(data)} items.")
                    if data:
                        print(f"  First item: {json.dumps(data[0], ensure_ascii=False)[:500]}")
                else:
                    print(f"Parsed JSON, but top-level is {type(data).__name__}.")
            except Exception as e:
                print(f"Failed to parse as JSON: {e}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 3: Govmap parcel-search (parcel info by coordinates)")
    print("=" * 60)

    test_x, test_y = 3871406.911, 3772053.769
    url = (
        f"https://www.govmap.gov.il/api/layers-catalog/apps/parcel-search/"
        f"address/({test_x} {test_y})"
    )

    try:
        r = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Origin": "https://www.govmap.gov.il",
                "Referer": "https://www.govmap.gov.il/",
                "User-Agent": "Mozilla/5.0 (test)",
            },
            timeout=15,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print("First 500 chars of body:")
        print(r.text[:500])
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 4: Neighborhood deals JSON (Rothschild area in Tel Aviv)")
    print("=" * 60)

    try:
        r = requests.get(
            "https://data.nadlan.gov.il/api/pages/neighborhood/buy/65209994.json",
            timeout=20,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print(f"Response size: {len(r.content)} bytes")
        print("First 2000 chars of body:")
        print(r.text[:2000])
        print()
        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, dict):
                    print(f"Top-level keys: {list(data.keys())}")
                    for k, v in data.items():
                        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                            print(f"Key '{k}' has {len(v)} items.")
                            print(f"First item keys: {list(v[0].keys())}")
                            print(
                                f"First 2 items full: "
                                f"{json.dumps(v[:2], ensure_ascii=False, indent=2)[:1500]}"
                            )
                            break
                elif isinstance(data, list):
                    print(f"Top-level is a list of {len(data)} items.")
                    if data:
                        print(f"First item: {json.dumps(data[0], ensure_ascii=False)[:1500]}")
            except Exception as e:
                print(f"Failed to parse as JSON: {e}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 5: Try street-level deals JSON")
    print("=" * 60)

    test_urls_5 = [
        "https://data.nadlan.gov.il/api/pages/street/buy/50001103.json",
        "https://data.nadlan.gov.il/api/pages/streets/buy/50001103.json",
        "https://data.nadlan.gov.il/api/pages/street/50001103.json",
        "https://data.nadlan.gov.il/api/pages/buy/street/50001103.json",
    ]

    for url in test_urls_5:
        try:
            r = requests.get(url, timeout=10)
            print(f"\n{url}")
            print(f"  Status: {r.status_code}, size: {len(r.content)} bytes")
            if r.status_code == 200:
                print(f"  First 300 chars: {r.text[:300]}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 6: Try polygon-level / address-level deals JSON")
    print("=" * 60)

    test_urls_6 = [
        "https://data.nadlan.gov.il/api/pages/polygon/buy/53292326.json",
        "https://data.nadlan.gov.il/api/pages/address/buy/64834989.json",
        "https://data.nadlan.gov.il/api/pages/addr/buy/64834989.json",
        "https://data.nadlan.gov.il/api/pages/buy/64834989.json",
        "https://data.nadlan.gov.il/api/pages/deals/64834989.json",
        "https://data.nadlan.gov.il/api/pages/deals/65209994.json",
        "https://data.nadlan.gov.il/api/pages/transactions/buy/65209994.json",
    ]

    for url in test_urls_6:
        try:
            r = requests.get(url, timeout=10)
            print(f"\n{url}")
            print(f"  Status: {r.status_code}, size: {len(r.content)} bytes")
            if r.status_code == 200:
                print(f"  First 300 chars: {r.text[:300]}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 7: Govmap deals by radius (50m around Rothschild 1 TLV)")
    print("=" * 60)

    point_x = 3871406.911338617
    point_y = 3772053.768985697
    radius = 50

    url = (
        f"https://www.govmap.gov.il/api/real-estate/deals/"
        f"({point_x} {point_y})/{radius}"
    )

    try:
        r = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Origin": "https://www.govmap.gov.il",
                "Referer": "https://www.govmap.gov.il/",
                "User-Agent": "Mozilla/5.0 (test)",
            },
            timeout=15,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print(f"Response size: {len(r.content)} bytes")
        print("First 1500 chars:")
        print(r.text[:1500])
        if r.status_code == 200 and "application/json" in (r.headers.get("content-type") or ""):
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"\nParsed as list of {len(data)} deals.")
                    if data:
                        first = data[0]
                        if isinstance(first, dict):
                            print(f"First deal keys: {list(first.keys())}")
                            print(
                                f"First deal: "
                                f"{json.dumps(first, ensure_ascii=False, indent=2)[:800]}"
                            )
                        else:
                            print(f"First item (raw): {first!r}")
                elif isinstance(data, dict):
                    print(f"\nParsed as dict. Keys: {list(data.keys())}")
            except Exception as e:
                print(f"JSON parse failed: {e}")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 8: Govmap street-deals for Rothschild polygon")
    print("=" * 60)

    test_ids_8 = ["53292326", "50001103"]

    for pid in test_ids_8:
        url = f"https://www.govmap.gov.il/api/real-estate/street-deals/{pid}"
        try:
            r = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "Origin": "https://www.govmap.gov.il",
                    "Referer": "https://www.govmap.gov.il/",
                    "User-Agent": "Mozilla/5.0 (test)",
                },
                timeout=15,
            )
            print(f"\nID={pid}: Status={r.status_code}, size={len(r.content)}")
            if r.status_code == 200:
                print(f"  Content-Type: {r.headers.get('content-type')}")
                print(f"  First 500 chars: {r.text[:500]}")
        except Exception as e:
            print(f"  FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("Test 9: Govmap entitiesByPoint (find polygons at a coordinate)")
    print("=" * 60)

    url = "https://www.govmap.gov.il/api/layers-catalog/entitiesByPoint"

    try:
        r = requests.post(
            url,
            json={
                "x": 3871406.911338617,
                "y": 3772053.768985697,
                "layers": ["neighborhoods", "streets", "parcels"],
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Origin": "https://www.govmap.gov.il",
                "Referer": "https://www.govmap.gov.il/",
                "User-Agent": "Mozilla/5.0 (test)",
            },
            timeout=15,
        )
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print("First 1000 chars:")
        print(r.text[:1000])
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 60)
    print("PoC complete.")
    print("=" * 60)


def run_poc() -> str:
    """Run the probes and return all stdout as a single string.

    Used by the temporary ``/shuma/poc-test`` endpoint so the result is
    available from a browser without needing shell access to the Railway
    instance.
    """
    buf = io.StringIO()
    with redirect_stdout(buf):
        _run_probes()
    return buf.getvalue()


if __name__ == "__main__":
    _run_probes()
