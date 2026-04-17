#!/usr/bin/env python3
"""Compare pipeline output against the golden benchmark.

Shows exactly which records changed, improved, or regressed.
The benchmark is the client-approved output frozen as ground truth.

Usage:
  python scripts/benchmark.py new_output.xlsx
  python scripts/benchmark.py new_output.xlsx --verbose
  python scripts/benchmark.py new_output.xlsx --only-changes
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from scripts.evaluate import evaluate_record

BENCHMARK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "benchmark", "golden_output.xlsx",
)


def compare(new_path: str, verbose: bool = False, only_changes: bool = False) -> dict:
    golden = pd.read_excel(BENCHMARK_PATH)
    new = pd.read_excel(new_path)

    golden_map = {}
    for _, row in golden.iterrows():
        ic = str(row["ICNO"])
        addr = str(row["MAILING_ADDRESS"]) if pd.notna(row["MAILING_ADDRESS"]) else ""
        conf = row.get("CONFIDENCE", 0) or 0
        golden_map[ic] = {"addr": addr, "conf": conf}

    changed = []
    improved = []
    regressed = []
    same = 0

    for _, row in new.iterrows():
        ic = str(row["ICNO"])
        new_addr = str(row["MAILING_ADDRESS"]) if pd.notna(row["MAILING_ADDRESS"]) else ""
        new_conf = row.get("CONFIDENCE", 0) or 0

        if ic not in golden_map:
            changed.append({"ic": ic, "type": "NEW", "new_addr": new_addr})
            continue

        old = golden_map[ic]
        if old["addr"] == new_addr:
            same += 1
            continue

        # Score both
        old_checks = evaluate_record(old["addr"], old["conf"])
        new_checks = evaluate_record(new_addr, new_conf)

        old_passes = sum(1 for v in old_checks.values() if v)
        new_passes = sum(1 for v in new_checks.values() if v)

        entry = {
            "ic": ic,
            "old_addr": old["addr"].replace("\n", " | ")[:80],
            "new_addr": new_addr.replace("\n", " | ")[:80],
            "old_score": old_passes,
            "new_score": new_passes,
            "old_conf": old["conf"],
            "new_conf": new_conf,
        }

        if new_passes > old_passes:
            entry["type"] = "IMPROVED"
            improved.append(entry)
        elif new_passes < old_passes:
            entry["type"] = "REGRESSED"
            regressed.append(entry)
        else:
            entry["type"] = "CHANGED"
            changed.append(entry)

    # Report
    total = len(new)
    print(f"{'=' * 60}")
    print(f"BENCHMARK COMPARISON")
    print(f"{'=' * 60}")
    print(f"Golden: {BENCHMARK_PATH}")
    print(f"New:    {new_path}")
    print(f"")
    print(f"  Unchanged:  {same:>5} ({same / total * 100:.1f}%)")
    print(f"  Improved:   {len(improved):>5} ({len(improved) / total * 100:.1f}%)")
    print(f"  Changed:    {len(changed):>5} ({len(changed) / total * 100:.1f}%)")
    print(f"  Regressed:  {len(regressed):>5} ({len(regressed) / total * 100:.1f}%)")
    print(f"  Total:      {total:>5}")

    if regressed:
        print(f"\n{'=' * 60}")
        print(f"REGRESSIONS ({len(regressed)})")
        print(f"{'=' * 60}")
        for r in regressed[:20]:
            print(f"\n  IC: {r['ic']} | score {r['old_score']}->{r['new_score']} | conf {r['old_conf']:.0%}->{r['new_conf']:.0%}")
            print(f"    OLD: {r['old_addr']}")
            print(f"    NEW: {r['new_addr']}")

    if improved and (verbose or only_changes):
        print(f"\n{'=' * 60}")
        print(f"IMPROVEMENTS ({len(improved)})")
        print(f"{'=' * 60}")
        for r in improved[:20]:
            print(f"\n  IC: {r['ic']} | score {r['old_score']}->{r['new_score']} | conf {r['old_conf']:.0%}->{r['new_conf']:.0%}")
            print(f"    OLD: {r['old_addr']}")
            print(f"    NEW: {r['new_addr']}")

    if changed and (verbose or only_changes):
        print(f"\n{'=' * 60}")
        print(f"CHANGED (same quality score) ({len(changed)})")
        print(f"{'=' * 60}")
        for r in changed[:20]:
            print(f"\n  IC: {r['ic']} | conf {r.get('old_conf', 0):.0%}->{r.get('new_conf', 0):.0%}")
            print(f"    OLD: {r.get('old_addr', 'N/A')}")
            print(f"    NEW: {r['new_addr']}")

    verdict = "SAFE" if not regressed else "REGRESSIONS FOUND"
    print(f"\n{'=' * 60}")
    print(f"VERDICT: {verdict}")
    if not regressed:
        print(f"  No regressions. Safe to deploy.")
    else:
        print(f"  {len(regressed)} regressions found. Review before deploying.")
    print(f"{'=' * 60}")

    return {
        "same": same,
        "improved": len(improved),
        "changed": len(changed),
        "regressed": len(regressed),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare against golden benchmark")
    parser.add_argument("file", help="New output Excel file to compare")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show all changes")
    parser.add_argument("--only-changes", action="store_true", help="Show only changed records")
    args = parser.parse_args()

    compare(args.file, verbose=args.verbose, only_changes=args.only_changes)
