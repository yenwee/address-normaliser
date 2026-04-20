#!/usr/bin/env python3
"""Generate a side-by-side validation report for staff to spot-check.

Shows: IC | Name | All Original Addresses | Selected Address | Confidence | Review Flag

Usage:
  python scripts/generate_validation_report.py input.xls output_normalised.xlsx report.xlsx
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import xlrd

from src.io.excel_reader import read_excel, get_addr_columns


def generate_report(input_path, normalised_path, report_path):
    original = read_excel(input_path)
    normalised = pd.read_excel(normalised_path)
    addr_cols = get_addr_columns(original)

    # Filter header rows
    original = original[~original["ICNO"].astype(str).str.strip().str.lower().isin(["ic", "icno"])]

    rows = []
    for _, norm_row in normalised.iterrows():
        ic = str(norm_row["ICNO"])
        name = norm_row["NAME"]
        selected = norm_row["MAILING_ADDRESS"] if pd.notna(norm_row["MAILING_ADDRESS"]) else ""
        confidence = norm_row["CONFIDENCE"]

        # Find original row
        orig_match = original[original["ICNO"].astype(str) == ic]
        originals = []
        if len(orig_match) > 0:
            orig_row = orig_match.iloc[0]
            for i, col in enumerate(addr_cols):
                val = orig_row.get(col)
                if pd.notna(val) and str(val).strip():
                    parts = [p.strip() for p in str(val).split(",")]
                    if any(p and p.upper() != "NULL" for p in parts):
                        originals.append(f"[{col}] {val.strip()}")

        # Flag for review
        if confidence == 0:
            flag = "NO ADDRESS"
        elif confidence < 0.6:
            flag = "LOW - NEEDS REVIEW"
        elif confidence < 0.8:
            flag = "MEDIUM - CHECK"
        else:
            flag = "OK"

        rows.append({
            "IC Number": ic,
            "Name": name,
            "SELECTED ADDRESS": selected.replace("\n", " | ") if selected else "",
            "Confidence": f"{confidence:.0%}",
            "Review Flag": flag,
            "Total Addresses Found": len(originals),
            "All Original Addresses": "\n---\n".join(originals[:10]) if originals else "NONE",
        })

    report_df = pd.DataFrame(rows)

    with pd.ExcelWriter(report_path, engine="xlsxwriter") as writer:
        report_df.to_excel(writer, sheet_name="Validation", index=False)

        # Summary sheet
        summary_data = {
            "Metric": [
                "Total Records",
                "Address Found (OK)",
                "Medium Confidence (Check)",
                "Low Confidence (Needs Review)",
                "No Address Found",
            ],
            "Count": [
                len(rows),
                sum(1 for r in rows if r["Review Flag"] == "OK"),
                sum(1 for r in rows if r["Review Flag"] == "MEDIUM - CHECK"),
                sum(1 for r in rows if r["Review Flag"] == "LOW - NEEDS REVIEW"),
                sum(1 for r in rows if r["Review Flag"] == "NO ADDRESS"),
            ],
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

    print(f"Validation report saved to: {report_path}")
    print(f"\nSummary:")
    for _, s in summary_df.iterrows():
        print(f"  {s['Metric']}: {s['Count']}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python scripts/generate_validation_report.py input.xls normalised.xlsx report.xlsx")
        sys.exit(1)

    generate_report(sys.argv[1], sys.argv[2], sys.argv[3])
