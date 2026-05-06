#!/usr/bin/env python3
"""Entry point — interactive form → Word report."""
import sys
import os

# Allow running as: python real_estate/main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from real_estate.form import collect_form
from real_estate.report_generator import generate_report


def main():
    print("\n" + "=" * 55)
    print("   מערכת אוטומציה לדוחות שמאות מקרקעין")
    print("=" * 55)
    try:
        data = collect_form()
    except KeyboardInterrupt:
        print("\n\n  הופסק.")
        sys.exit(0)

    safe = (
        data.address.replace(" ", "_")
        .replace("/", "-")
        .replace(",", "")
        .replace("\"", "")
    )
    filename = f"שומת_מקרקעין_{safe}_{data.report_date.replace('/', '-')}.docx"
    out_path = os.path.join(os.getcwd(), filename)

    print("\n  מפיק דוח...")
    generate_report(data, out_path)

    print("\n" + "=" * 55)
    print("  הדוח הופק בהצלחה!")
    print(f"  קובץ: {out_path}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
