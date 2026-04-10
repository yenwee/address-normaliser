#!/usr/bin/env python3
"""CLI for address normalisation.

Usage:
  python cli.py input.xls                    # outputs input_NORMALISED.xlsx
  python cli.py input.xls output.xlsx        # custom output path
  python cli.py input.xls --nominatim        # enable OSM geocoding fallback
"""
import argparse
import os
import sys
import time

from src.pipeline import process_file


def main():
    parser = argparse.ArgumentParser(description="Malaysian address normaliser")
    parser.add_argument("input", help="Input Excel file (.xls or .xlsx)")
    parser.add_argument("output", nargs="?", help="Output Excel file (default: input_NORMALISED.xlsx)")
    parser.add_argument("--nominatim", action="store_true", help="Enable OSM geocoding for low-confidence addresses")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found")
        sys.exit(1)

    if args.output:
        output = args.output
    else:
        base, ext = os.path.splitext(args.input)
        output = f"{base}_NORMALISED.xlsx"

    if args.nominatim:
        os.environ["NOMINATIM_ENABLED"] = "true"

    print(f"Input:  {args.input}")
    print(f"Output: {output}")
    print()

    start = time.time()
    stats = process_file(args.input, output)
    elapsed = time.time() - start

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Total:          {stats['total']}")
    print(f"  Processed:      {stats['processed']}")
    print(f"  Low confidence: {stats['low_confidence']}")
    print(f"  No address:     {stats['no_address']}")
    print(f"\nOutput: {output}")


if __name__ == "__main__":
    main()
