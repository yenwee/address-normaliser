#!/usr/bin/env python3
"""Score pipeline output against the expert golden answers benchmark.

Measures how close the pipeline output is to human-expert-level accuracy.

Usage:
  python scripts/score_against_golden.py output.xlsx
  python scripts/score_against_golden.py output.xlsx --verbose
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from rapidfuzz import fuzz

GOLDEN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "benchmark", "golden_answers.json",
)


def _extract_fields(address: str) -> dict:
    """Extract postcode, city, state, and street from a mailing block."""
    lines = [l.strip() for l in address.split("\n") if l.strip()] if address else []

    postcode = ""
    city = ""
    state = ""
    street_lines = []

    for line in lines:
        m = re.match(r"^(\d{5})\s+(.+)", line)
        if m:
            postcode = m.group(1)
            city = m.group(2).strip().upper()
        elif re.match(r"^(JOHOR|KEDAH|KELANTAN|MELAKA|NEGERI SEMBILAN|PAHANG|PERAK|PERLIS|PULAU PINANG|P\.PINANG|SABAH|SARAWAK|SELANGOR|TERENGGANU|WILAYAH|WP|N\.SEMBILAN)", line.upper()):
            state = line.strip().upper()
        else:
            street_lines.append(line.strip().upper())

    street = " ".join(street_lines)
    return {"postcode": postcode, "city": city, "state": state, "street": street}


def score_record(pipeline_addr: str, golden_addr: str) -> dict:
    """Score a single record against golden answer."""
    if not golden_addr or not golden_addr.strip():
        if not pipeline_addr or not pipeline_addr.strip():
            return {"match": True, "postcode": True, "city": True, "state": True, "street": 100, "overall": 100}
        return {"match": False, "postcode": False, "city": False, "state": False, "street": 0, "overall": 0}

    if not pipeline_addr or not pipeline_addr.strip():
        return {"match": False, "postcode": False, "city": False, "state": False, "street": 0, "overall": 0}

    p = _extract_fields(pipeline_addr)
    g = _extract_fields(golden_addr)

    exact_match = pipeline_addr.strip().upper() == golden_addr.strip().upper()
    pc_match = p["postcode"] == g["postcode"] if g["postcode"] else True
    city_match = fuzz.token_sort_ratio(p["city"], g["city"]) > 70 if g["city"] else True
    state_match = fuzz.token_sort_ratio(p["state"], g["state"]) > 60 if g["state"] else True
    street_sim = fuzz.token_sort_ratio(p["street"], g["street"]) if g["street"] else 100

    # Overall score: weighted average
    overall = (
        (30 if pc_match else 0)
        + (20 if city_match else 0)
        + (20 if state_match else 0)
        + (30 * street_sim / 100)
    )

    return {
        "match": exact_match,
        "postcode": pc_match,
        "city": city_match,
        "state": state_match,
        "street": round(street_sim, 1),
        "overall": round(overall, 1),
    }


def score_file(pipeline_path: str, verbose: bool = False):
    """Score all records in pipeline output against golden answers."""
    with open(GOLDEN_PATH) as f:
        golden_data = json.load(f)

    golden_map = {}
    for rec in golden_data["records"]:
        golden_map[rec["ic"]] = rec["golden_address"]

    df = pd.read_excel(pipeline_path)

    scores = []
    mismatches = []

    for _, row in df.iterrows():
        ic = str(row["ICNO"])
        pipeline_addr = str(row["MAILING_ADDRESS"]) if pd.notna(row["MAILING_ADDRESS"]) else ""
        golden_addr = golden_map.get(ic, "")

        result = score_record(pipeline_addr, golden_addr)
        result["ic"] = ic
        scores.append(result)

        if not result["match"] and golden_addr:
            mismatches.append({
                "ic": ic,
                "pipeline": pipeline_addr.replace("\n", " | ")[:70],
                "golden": golden_addr.replace("\n", " | ")[:70],
                "overall": result["overall"],
            })

    # Summary
    total = len(scores)
    exact = sum(1 for s in scores if s["match"])
    pc_ok = sum(1 for s in scores if s["postcode"])
    city_ok = sum(1 for s in scores if s["city"])
    state_ok = sum(1 for s in scores if s["state"])
    avg_street = sum(s["street"] for s in scores) / total if total else 0
    avg_overall = sum(s["overall"] for s in scores) / total if total else 0

    print(f"{'=' * 60}")
    print(f"GOLDEN ANSWER SCORING")
    print(f"{'=' * 60}")
    print(f"Pipeline: {pipeline_path}")
    print(f"Golden:   {GOLDEN_PATH}")
    print(f"Records:  {total} pipeline vs {len(golden_map)} golden")
    print()
    print(f"{'Metric':<25} {'Score':>10}")
    print(f"{'-' * 25} {'-' * 10}")
    print(f"{'Exact match':<25} {exact}/{total} ({exact / total * 100:.1f}%)")
    print(f"{'Postcode correct':<25} {pc_ok}/{total} ({pc_ok / total * 100:.1f}%)")
    print(f"{'City correct':<25} {city_ok}/{total} ({city_ok / total * 100:.1f}%)")
    print(f"{'State correct':<25} {state_ok}/{total} ({state_ok / total * 100:.1f}%)")
    print(f"{'Street similarity':<25} {avg_street:.1f}%")
    print(f"{'OVERALL ACCURACY':<25} {avg_overall:.1f}%")

    # Grade
    if avg_overall >= 95:
        grade = "A+ (Expert level)"
    elif avg_overall >= 90:
        grade = "A (Excellent)"
    elif avg_overall >= 80:
        grade = "B (Good)"
    elif avg_overall >= 70:
        grade = "C (Acceptable)"
    else:
        grade = "D (Needs improvement)"

    print(f"\n{'GRADE':<25} {grade}")

    if verbose:
        # Show worst mismatches
        mismatches.sort(key=lambda m: m["overall"])
        print(f"\n{'=' * 60}")
        print(f"WORST MISMATCHES (bottom 20)")
        print(f"{'=' * 60}")
        for m in mismatches[:20]:
            print(f"\n  IC: {m['ic']} | Score: {m['overall']:.0f}%")
            print(f"    PIPE: {m['pipeline']}")
            print(f"    GOLD: {m['golden']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score against golden answers")
    parser.add_argument("file", help="Pipeline output Excel file")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    score_file(args.file, verbose=args.verbose)
