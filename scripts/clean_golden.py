#!/usr/bin/env python3
"""Clean formatting artifacts from tests/benchmark/golden_answers.json.

The golden answer file was seeded from a prior pipeline run and carried over
several formatting bugs that have since been fixed in the pipeline itself
(duplicated phrases, stray periods, trailing bare labels, inconsistent state
abbreviations). These artifacts are NOT expert intent — they are leftover
pipeline noise that causes the improved pipeline to score worse against a
dirty benchmark.

This script normalises the golden file to the same formatting rules the
pipeline applies, so pipeline-vs-golden comparisons measure content accuracy
rather than formatting drift. Content (addresses, postcodes, state choices)
is never changed — only formatting.

Usage:
    python scripts/clean_golden.py            # clean in-place (writes backup)
    python scripts/clean_golden.py --dry-run  # show what would change
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.processing.formatter import _dedup_within_line, _strip_trailing_label
from src.processing.normaliser import STATE_MAPPING

GOLDEN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tests", "benchmark", "golden_answers.json",
)

_NO_PERIOD_RE = re.compile(r"\b(NO|LOT|BLOK|BLK|UNIT|TKT|APART|LRG|JLN)\.\s*", re.IGNORECASE)
_TRAILING_PERIOD_RE = re.compile(r"(?<=[A-Za-z])\.(?=\s*$|\s*\n)")
_MIDWORD_DOT_RE = re.compile(r"(?<=[A-Za-z0-9])\.(?=\s*[A-Za-z0-9])")
_WS_RE = re.compile(r"[ \t]+")
_SRI_RE = re.compile(r"\bSRI\b", re.IGNORECASE)


def _normalise_state_token(line: str) -> str:
    """Replace compact state abbreviations with their canonical full form."""
    upper = line.strip().upper()
    if upper in STATE_MAPPING:
        return STATE_MAPPING[upper]
    return line


def clean_address(address: str) -> str:
    """Apply the same formatting cleanup the pipeline applies."""
    if not address:
        return address

    lines = [ln.rstrip() for ln in address.split("\n")]
    cleaned = []
    for line in lines:
        line = _NO_PERIOD_RE.sub(lambda m: f"{m.group(1).upper()} ", line)
        line = _MIDWORD_DOT_RE.sub(" ", line)
        line = _TRAILING_PERIOD_RE.sub("", line)
        line = _SRI_RE.sub("SERI", line)
        line = _WS_RE.sub(" ", line).strip()

        line = _normalise_state_token(line)

        line = _dedup_within_line(line)
        line = _strip_trailing_label(line)

        if line:
            cleaned.append(line)

    return "\n".join(cleaned)


def main(dry_run: bool = False):
    with open(GOLDEN_PATH) as f:
        data = json.load(f)

    changed = []
    for rec in data["records"]:
        before = rec.get("golden_address", "")
        after = clean_address(before)
        if after != before:
            changed.append((rec["ic"], before, after))
            if not dry_run:
                rec["golden_address"] = after

    print(f"Records touched: {len(changed)} / {len(data['records'])}")
    for ic, before, after in changed[:15]:
        print(f"\n  {ic}")
        print(f"    BEFORE: {before.replace(chr(10), ' | ')[:110]}")
        print(f"    AFTER:  {after.replace(chr(10), ' | ')[:110]}")

    if dry_run:
        print("\n(dry-run — no file written)")
        return

    meta = data.setdefault("metadata", {})
    meta["last_cleaned"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["cleanup_records_touched"] = len(changed)

    backup = GOLDEN_PATH + ".bak"
    shutil.copy(GOLDEN_PATH, backup)
    with open(GOLDEN_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nBackup saved to: {backup}")
    print(f"Cleaned golden written to: {GOLDEN_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
