#!/usr/bin/env python3
"""Generate a sample report without filling the form — for testing."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from real_estate.demo_data import sample_standard19, sample_market, sample_evacuation
from real_estate.report_generator import generate_report

DEMOS = {
    "תקן19": (sample_standard19, "demo_teken19.docx"),
    "שוק": (sample_market, "demo_shuk.docx"),
    "פינוי_בינוי": (sample_evacuation, "demo_pinui_binui.docx"),
}

choice = sys.argv[1] if len(sys.argv) > 1 else "תקן19"
if choice not in DEMOS:
    print(f"Usage: python run_demo.py [{' | '.join(DEMOS.keys())}]")
    sys.exit(1)

fn, filename = DEMOS[choice]
data = fn()
out = os.path.join(os.path.dirname(__file__), filename)
print(f"מפיק דוח לדוגמה ({choice})...")
generate_report(data, out)
print(f"נשמר: {out}")
