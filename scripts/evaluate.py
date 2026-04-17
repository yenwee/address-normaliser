#!/usr/bin/env python3
"""Evaluate address normalisation output quality.

Scores every record against automated quality checks.
Run after processing to measure improvement across pipeline changes.

Usage:
  python scripts/evaluate.py output.xlsx
  python scripts/evaluate.py output.xlsx --verbose
"""
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from src.processing.parser import KNOWN_STATES
from src.processing.normaliser import STATE_MAPPING


STATES_FULL = KNOWN_STATES | {v.upper() for v in STATE_MAPPING.values()}


def evaluate_record(addr: str, confidence: float) -> dict:
    """Score a single address against quality checks. Returns dict of pass/fail per check."""
    checks = {}

    if not addr or addr.strip() == "" or str(addr) == "nan":
        return {"has_address": False}

    checks["has_address"] = True
    lines = [l.strip() for l in addr.split("\n") if l.strip()]

    # 1. Has postcode (5-digit)
    checks["has_postcode"] = bool(re.search(r"\b\d{5}\b", addr))

    # 2. Has state (last line should be a state)
    checks["has_state"] = lines[-1].upper() in STATES_FULL if lines else False

    # 3. Has street component (not just postcode+city+state)
    non_meta = [l for l in lines if not re.match(r"^\d{5}\s", l) and l.upper() not in STATES_FULL]
    checks["has_street"] = len(non_meta) > 0

    # 4. Proper line ordering: street before postcode before state
    pc_idx = next((i for i, l in enumerate(lines) if re.match(r"^\d{5}\s", l)), -1)
    state_idx = next((i for i, l in enumerate(lines) if l.upper() in STATES_FULL), -1)
    checks["line_order"] = (pc_idx == -1 or state_idx == -1 or pc_idx < state_idx)

    # 5. No duplicate lines
    checks["no_dupe_lines"] = len(lines) == len(set(l.upper() for l in lines))

    # 6. No duplicate keywords (JALAN JALAN, TAMAN TAMAN)
    dupe_kw = any(re.search(rf"\b{kw}\s+{kw}\b", addr, re.I)
                   for kw in ["JALAN", "TAMAN", "KAMPUNG", "LORONG", "BANDAR"])
    checks["no_dupe_keywords"] = not dupe_kw

    # 7. No junk symbols (@#*_)
    checks["no_junk_symbols"] = not bool(re.search(r"[@#*_]", addr))

    # 8. No state leaked into address lines (state only on last line)
    state_leak = False
    for line in lines[:-1]:
        if line.upper() in STATES_FULL and not re.match(r"^\d{5}", line):
            state_leak = True
            break
    checks["no_state_leak"] = not state_leak

    # 9. No raw abbreviations remaining (JLN, TMN, LRG, KG — should be expanded)
    abbrev_remaining = bool(re.search(r"\b(JLN|TMN|LRG|KPG|KMPG|BDR)\b", addr))
    checks["abbreviations_expanded"] = not abbrev_remaining

    # 10. No embedded postcode in address lines (postcode should only be in postcode+city line)
    postcode_lines = [l for l in lines if re.match(r"^\d{5}\s", l) or re.match(r"^\d{5}$", l)]
    pc_value = ""
    for pl in postcode_lines:
        m = re.match(r"(\d{5})", pl)
        if m:
            pc_value = m.group(1)
            break
    if pc_value:
        addr_only = [l for l in lines if l not in postcode_lines and l.upper() not in STATES_FULL]
        checks["no_embedded_postcode"] = not any(pc_value in l for l in addr_only)
    else:
        checks["no_embedded_postcode"] = True

    # 11. No duplicate city at END of address lines (city as part of a place name is OK)
    city = ""
    for pl in postcode_lines:
        m = re.match(r"\d{5}\s+(.+)", pl)
        if m:
            city = m.group(1).strip().upper()
    if city and len(city) > 3:
        addr_only = [l for l in lines if l not in postcode_lines and l.upper() not in STATES_FULL]
        checks["no_city_in_addr"] = not any(l.upper().endswith(city) for l in addr_only)
    else:
        checks["no_city_in_addr"] = True

    # 12. Confidence >= 0.6 (usable for mailing)
    checks["confidence_ok"] = confidence >= 0.6

    # 13. Address line not too short (at least has a meaningful address)
    checks["not_too_short"] = len(" ".join(non_meta)) >= 10 if non_meta else False

    return checks


def evaluate_file(path: str, verbose: bool = False) -> dict:
    """Evaluate all records in an output file."""
    df = pd.read_excel(path)

    all_checks = []
    failures = {}

    for _, row in df.iterrows():
        addr = str(row["MAILING_ADDRESS"]) if pd.notna(row["MAILING_ADDRESS"]) else ""
        conf = row.get("CONFIDENCE", 0) or 0
        checks = evaluate_record(addr, conf)
        all_checks.append((row["ICNO"], checks))

        for check_name, passed in checks.items():
            if not passed:
                if check_name not in failures:
                    failures[check_name] = []
                failures[check_name].append(str(row["ICNO"]))

    # Summary
    total = len(all_checks)
    check_names = set()
    for _, checks in all_checks:
        check_names.update(checks.keys())

    print(f"{'=' * 60}")
    print(f"EVALUATION REPORT: {path}")
    print(f"{'=' * 60}")
    print(f"Total records: {total}\n")

    print(f"{'Check':<25} {'Pass':>6} {'Fail':>6} {'Rate':>7}")
    print(f"{'-' * 25} {'-' * 6} {'-' * 6} {'-' * 7}")

    overall_score = 0
    overall_total = 0

    for check in sorted(check_names):
        passed = sum(1 for _, c in all_checks if c.get(check, True))
        failed = total - passed
        rate = passed / total * 100
        overall_score += passed
        overall_total += total
        marker = "" if rate >= 95 else " <--" if rate < 90 else " !"
        print(f"{check:<25} {passed:>6} {failed:>6} {rate:>6.1f}%{marker}")

    overall_rate = overall_score / overall_total * 100 if overall_total else 0
    print(f"\n{'OVERALL SCORE':<25} {'':>6} {'':>6} {overall_rate:>6.1f}%")

    # Mailable rate
    mailable = sum(1 for _, c in all_checks
                   if c.get("has_address") and c.get("has_postcode") and c.get("has_street"))
    print(f"{'MAILABLE RATE':<25} {mailable:>6} {total - mailable:>6} {mailable / total * 100:>6.1f}%")

    if verbose and failures:
        print(f"\n{'=' * 60}")
        print("FAILURES BY CHECK")
        print(f"{'=' * 60}")
        for check in sorted(failures):
            ics = failures[check]
            if len(ics) <= 20:
                print(f"\n{check} ({len(ics)} failures):")
                for ic in ics[:10]:
                    r = df[df["ICNO"].astype(str) == ic]
                    if len(r):
                        addr = str(r.iloc[0]["MAILING_ADDRESS"]).replace("\n", " | ")[:70] if pd.notna(r.iloc[0]["MAILING_ADDRESS"]) else "(empty)"
                        print(f"  {ic}: {addr}")
            else:
                print(f"\n{check} ({len(ics)} failures): [too many to list]")

    return {"total": total, "mailable": mailable, "overall_rate": overall_rate}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate address normalisation quality")
    parser.add_argument("file", help="Output Excel file to evaluate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show failure details")
    args = parser.parse_args()

    evaluate_file(args.file, verbose=args.verbose)
