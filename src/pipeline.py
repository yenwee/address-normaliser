"""Main processing pipeline for Malaysian address normalisation.

Reads Excel files containing ICNO, NAME, and ADDR columns, normalises
addresses through parsing, clustering, scoring, validation, and optional
geocoding, then writes a clean output Excel with mailing blocks.
"""

import logging
import re
from collections import Counter

import pandas as pd

from src.processing.clusterer import cluster_addresses
from src.config import (
    CONFIDENCE_THRESHOLD,
    IC_COLUMN,
    NAME_COLUMN,
    NOMINATIM_ENABLED,
    ONLINE_VALIDATION_ENABLED,
    ONLINE_VALIDATION_MAILABLE_ONLY,
    ONLINE_VALIDATION_REVIEW_NO_RESULT,
)
from src.io.excel_reader import get_addr_columns, is_header_row, read_excel
from src.io.excel_writer import highlight_rows, write_results
from src.io.online_validation import geocode_multi_provider
from src.processing.formatter import format_mailing_block
from src.processing.mailability import is_mailable_block
from src.processing.normaliser import normalise_address, normalise_state
from src.processing.parser import parse_all_addresses
from src.processing.scorer import score_completeness
from src.steps.clean import merge_standalone_words, strip_leaked_fields
from src.steps.enrich import ensemble_enhance, enrich_from_cluster
from src.steps.geocode import apply_geocode_fallback, validate_address_online
from src.steps.select import find_best_cluster, select_best_address
from src.processing.validator import POSTCODE_STATE_PREFIXES, PostcodeValidator

# Aliases for test backward compatibility (tests import with underscore prefix)
_select_best_address = select_best_address

logger = logging.getLogger(__name__)

MAX_COMPLETENESS_SCORE = 12
POSTCODES_PATH = "data/postcodes.json"


def process_file(input_path: str, output_path: str) -> dict:
    """Process an Excel file of Malaysian addresses through the full pipeline.

    Flow per row:
        1. Parse all ADDR columns into structured address dicts
        2. Normalise each parsed address
        3. Cluster normalised addresses by similarity
        4. Select the best address from the best cluster
        5. Validate and correct postcode/city/state
        6. Optionally geocode low-confidence addresses
        7. Format as a mailing block

    Args:
        input_path: Path to the input Excel file.
        output_path: Path for the output Excel file.

    Returns:
        Stats dict with keys: total, processed, low_confidence, no_address.
    """
    df = read_excel(input_path)
    addr_columns = get_addr_columns(df)

    validator = PostcodeValidator(POSTCODES_PATH)

    stats = {
        "total": 0,
        "processed": 0,
        "low_confidence": 0,
        "no_address": 0,
        "online_checked": 0,
        "online_match": 0,
        "online_mismatch": 0,
        "online_no_result": 0,
        "online_skipped": 0,
    }

    results = []

    for _, row in df.iterrows():
        if is_header_row(row):
            continue

        stats["total"] += 1

        ic = str(row.get(IC_COLUMN, "")).strip()
        name = str(row.get(NAME_COLUMN, "")).strip()

        parsed_addresses = parse_all_addresses(row, addr_columns)

        if not parsed_addresses:
            stats["no_address"] += 1
            stats["processed"] += 1
            results.append({
                "ICNO": ic,
                "NAME": name,
                "MAILING_ADDRESS": "",
                "CONFIDENCE": 0.0,
            })
            continue

        normalised = [normalise_address(addr) for addr in parsed_addresses]

        clusters = cluster_addresses(normalised)

        # Count raw postcode frequency across all ADDR columns for popularity scoring
        raw_pc_counts = Counter()
        for col in addr_columns:
            if col not in row.index:
                continue
            val = str(row[col]) if pd.notna(row[col]) else ""
            pc_match = re.search(r"\b(\d{5})\b", val)
            if pc_match:
                raw_pc_counts[pc_match.group(1)] += 1

        best_addr, confidence = select_best_address(clusters, raw_pc_counts)

        if best_addr is None:
            stats["no_address"] += 1
            stats["processed"] += 1
            results.append({
                "ICNO": ic,
                "NAME": name,
                "MAILING_ADDRESS": "",
                "CONFIDENCE": 0.0,
            })
            continue

        # Capture selected cluster before enrichment (enrichment returns a copied dict).
        selected_cluster = next(
            (c for c in clusters if any(a is best_addr for a in c)),
            find_best_cluster(clusters),
        )

        # Light merge: enrich best address with info from cluster siblings
        best_addr = enrich_from_cluster(best_addr, clusters)

        # Ensemble: fill missing fields from the same selected cluster only.
        best_cluster = selected_cluster
        best_addr = ensemble_enhance(best_addr, best_cluster)

        corrected, _ = validator.correct_address(best_addr)

        # Re-normalise state after validator (DB may return "WP KUALA LUMPUR")
        corrected["state"] = normalise_state(corrected.get("state", ""))

        # Fill missing state from postcode prefix as fallback
        if not corrected.get("state", "").strip() and corrected.get("postcode", "").strip():
            prefix = corrected["postcode"][:2]
            inferred = POSTCODE_STATE_PREFIXES.get(prefix, "")
            if inferred:
                corrected["state"] = normalise_state(inferred)

        # Clean up address lines
        corrected = strip_leaked_fields(corrected)
        corrected = merge_standalone_words(corrected)

        confidence = min(
            score_completeness(corrected) / MAX_COMPLETENESS_SCORE, 1.0
        )

        if NOMINATIM_ENABLED and confidence < CONFIDENCE_THRESHOLD:
            corrected = apply_geocode_fallback(corrected)
            confidence = min(
                score_completeness(corrected) / MAX_COMPLETENESS_SCORE, 1.0
            )

        if confidence < CONFIDENCE_THRESHOLD:
            stats["low_confidence"] += 1

        mailing = format_mailing_block(corrected)

        if ONLINE_VALIDATION_ENABLED:
            should_check_online = (
                is_mailable_block(mailing)
                if ONLINE_VALIDATION_MAILABLE_ONLY
                else bool(mailing.strip())
            )

            if should_check_online:
                online = validate_address_online(
                    corrected,
                    geocode_fn=geocode_multi_provider,
                )
                stats["online_checked"] += 1
                stats[f"online_{online['status']}"] += 1

                online_needs_review = (
                    online["status"] == "mismatch"
                    or (
                        online["status"] == "no_result"
                        and ONLINE_VALIDATION_REVIEW_NO_RESULT
                    )
                )
                if online_needs_review:
                    confidence = min(confidence, max(CONFIDENCE_THRESHOLD - 0.01, 0.0))

                if online["status"] != "match":
                    logger.info(
                        "Online validation %s (%s) for IC %s via %s",
                        online["status"],
                        online["reason"],
                        ic,
                        online.get("provider", ""),
                    )
            else:
                stats["online_skipped"] += 1

        stats["processed"] += 1
        results.append({
            "ICNO": ic,
            "NAME": name,
            "MAILING_ADDRESS": mailing,
            "CONFIDENCE": round(confidence, 2),
        })

    write_results(results, output_path)
    highlight_rows(output_path)

    logger.info(
        "Pipeline complete: %d total, %d processed, %d low confidence, %d no address",
        stats["total"],
        stats["processed"],
        stats["low_confidence"],
        stats["no_address"],
    )
    if ONLINE_VALIDATION_ENABLED:
        logger.info(
            "Online validation: %d checked, %d match, %d mismatch, %d no_result, %d skipped",
            stats["online_checked"],
            stats["online_match"],
            stats["online_mismatch"],
            stats["online_no_result"],
            stats["online_skipped"],
        )

    return stats
