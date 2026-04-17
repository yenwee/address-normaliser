"""Excel output: write results and colour-code rows by confidence.

Uses openpyxl for both writing the results sheet and post-processing
styling (cell colours, wrap text, auto-width). Keeping these together
because they all operate on the same output file.
"""

import re

import pandas as pd


def write_results(results: list[dict], output_path: str) -> None:
    """Write processed results to an Excel file.

    Args:
        results: List of result dicts with ICNO, NAME, MAILING_ADDRESS, CONFIDENCE.
        output_path: Path for the output Excel file.
    """
    out_df = pd.DataFrame(results, columns=["ICNO", "NAME", "MAILING_ADDRESS", "CONFIDENCE"])
    out_df["MAILING_ADDRESS"] = out_df["MAILING_ADDRESS"].fillna("")
    out_df.to_excel(output_path, index=False, engine="openpyxl")


def highlight_rows(path: str) -> None:
    """Colour-code Excel rows by confidence level.

    Red:    no address or no postcode (unmailable)
    Yellow: low/medium confidence (needs review)
    Green:  high confidence header row
    """
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, PatternFill

    from src.processing.parser import KNOWN_STATES
    from src.processing.normaliser import STATE_MAPPING
    known_states_upper = KNOWN_STATES | {v.upper() for v in STATE_MAPPING.values()}

    red = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    yellow = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    green_header = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

    wb = load_workbook(path)
    ws = wb.active

    # Header row
    for cell in ws[1]:
        cell.fill = green_header

    for row_idx in range(2, ws.max_row + 1):
        confidence = ws.cell(row=row_idx, column=4).value or 0
        address = str(ws.cell(row=row_idx, column=3).value or "")
        has_postcode = bool(re.search(r"\b\d{5}\b", address))

        # Check if address has a street/house component (not just postcode+city+state)
        lines = [l.strip() for l in address.split("\n") if l.strip()]
        has_street = any(
            not re.match(r"^\d{5}\s", l) and l.upper() not in known_states_upper
            for l in lines
        )

        # Check for house/lot number keyword (NO, LOT, UNIT, BLK, or standalone leading digit on first line)
        addr_lines = [l.strip() for l in address.split("\n") if l.strip()]
        street_lines = [l for l in addr_lines
                        if not re.match(r"^\d{5}\s", l) and l.upper() not in known_states_upper]
        street_text = " ".join(street_lines)
        # Simple check: does the street text contain any number?
        # Addresses with no number at all (just area/village names) are incomplete.
        has_house_number = bool(re.search(r"\d", street_text))

        if confidence == 0 or not address.strip():
            fill = red
        elif not has_postcode:
            fill = red
        elif not has_street:
            fill = red
        elif not has_house_number:
            fill = yellow
        elif confidence < 0.6:
            fill = yellow
        else:
            continue

        for col in range(1, 5):
            ws.cell(row=row_idx, column=col).fill = fill

    # Enable wrap text on address column so multi-line addresses display properly
    wrap = Alignment(wrap_text=True, vertical="top")
    for row_idx in range(2, ws.max_row + 1):
        ws.cell(row=row_idx, column=3).alignment = wrap

    # Auto-width columns
    for col_idx in range(1, 5):
        max_len = max(len(str(ws.cell(row=r, column=col_idx).value or "")) for r in range(1, min(ws.max_row + 1, 50)))
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = min(max_len + 2, 60)

    wb.save(path)
