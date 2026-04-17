"""Main processing pipeline for Malaysian address normalisation.

Reads Excel files containing ICNO, NAME, and ADDR columns, normalises
addresses through parsing, clustering, scoring, validation, and optional
geocoding, then writes a clean output Excel with mailing blocks.
"""

import logging
import re
from collections import Counter
from typing import Optional

import pandas as pd

from src.clusterer import cluster_addresses
from src.config import (
    CONFIDENCE_THRESHOLD,
    IC_COLUMN,
    NAME_COLUMN,
    NOMINATIM_ENABLED,
)
from src.excel.reader import get_addr_columns, is_header_row, read_excel
from src.excel.writer import highlight_rows, write_results
from src.formatter import format_mailing_block
from src.nominatim import geocode_address
from src.normaliser import normalise_address, normalise_state
from src.parser import parse_all_addresses
from src.scorer import score_completeness
from src.validator import POSTCODE_STATE_PREFIXES, PostcodeValidator

logger = logging.getLogger(__name__)

MAX_COMPLETENESS_SCORE = 12
POSTCODES_PATH = "data/postcodes.json"


# Re-export for test backward compatibility
from src.steps.enrich import enrich_from_cluster as _enrich_from_cluster
from src.steps.enrich import ensemble_enhance as _ensemble_enhance
from src.steps.select import (
    find_best_cluster as _find_best_cluster,
    select_best_address as _select_best_address,
    select_from_cluster as _select_from_cluster,
)


def _strip_leaked_fields(addr: dict) -> dict:
    """Remove state names and postcode+city patterns that leaked into address lines."""
    import re
    from src.parser import KNOWN_STATES

    cleaned = dict(addr)
    state = cleaned.get("state", "").upper()
    postcode = cleaned.get("postcode", "")
    city = cleaned.get("city", "").upper()

    for key in ("address_line", "address_line2", "address_line3"):
        val = cleaned.get(key, "").strip()
        upper_val = val.upper()

        # Strip if entire field is just a state name
        if upper_val in KNOWN_STATES or upper_val == state:
            cleaned[key] = ""
            continue

        # Strip "postcode city" pattern from address lines (e.g. "70300 SEREMBAN")
        if postcode and city:
            pattern = f"{postcode}\\s*{re.escape(city)}"
            stripped = re.sub(pattern, "", upper_val, flags=re.IGNORECASE).strip()
            if stripped != upper_val:
                cleaned[key] = stripped
                continue

        # Strip standalone postcode from address lines (e.g. "... 06150 ALOR SETAR")
        if postcode:
            stripped = re.sub(rf"\b{postcode}\b", "", upper_val).strip()
            stripped = re.sub(r"\s+", " ", stripped)
            if stripped != upper_val:
                cleaned[key] = stripped
                val = cleaned[key]
                upper_val = val.upper()

        # Strip city name from END of address lines (e.g. "JLN ADABI KOTA BHARU" when city=KOTA BHARU)
        if city and len(city) > 3 and upper_val.endswith(city):
            stripped = upper_val[: -len(city)].strip()
            if stripped:
                cleaned[key] = stripped

        # Strip state name from END of address lines
        if state and len(state) > 2 and upper_val.endswith(state):
            stripped = upper_val[: -len(state)].strip()
            if stripped:
                cleaned[key] = stripped

    return cleaned


_MERGE_WORDS = frozenset({"JALAN", "KAMPUNG", "LORONG", "TAMAN", "BANDAR", "SUNGAI", "BATU", "DESA"})
_MERGE_WORDS_NEED_NUMBER = frozenset({"BATU"})


def _merge_standalone_words(addr: dict) -> dict:
    """Merge standalone generic words (JALAN, KAMPUNG etc.) with adjacent lines.

    Source data sometimes splits 'Kampung' or 'Jalan' into a separate comma field,
    producing standalone address lines like just 'JALAN' or 'KAMPUNG'.
    These should be merged with the next non-empty line.
    """
    cleaned = dict(addr)
    lines = [cleaned.get("address_line", ""), cleaned.get("address_line2", ""), cleaned.get("address_line3", "")]

    merged = []
    carry = ""
    for i, line in enumerate(lines):
        if carry:
            if line:
                # BATU should only merge when the following token starts with a digit
                # (e.g. "BATU 7"). Otherwise drop the stale label.
                if carry.upper() in _MERGE_WORDS_NEED_NUMBER:
                    first_tok = line.strip().split()[0] if line.strip() else ""
                    if not re.match(r"^\d", first_tok):
                        carry = ""
                        merged.append(line)
                        continue
                line = f"{carry} {line}".strip()
                carry = ""
            else:
                # No next line -- check remaining lines for something to merge with
                remaining = [l for l in lines[i + 1:] if l.strip()]
                if remaining:
                    # Will merge with next non-empty line in a future iteration
                    merged.append("")  # placeholder for this empty slot
                    continue
                # Nothing ahead -- append to previous if available, else drop number-needing words
                if carry.upper() in _MERGE_WORDS_NEED_NUMBER and not merged:
                    carry = ""
                    merged.append(line)
                    continue
                if merged:
                    merged[-1] = f"{merged[-1]} {carry}".strip() if merged[-1] else carry
                else:
                    merged.append(carry)
                carry = ""
                merged.append(line)
                continue
        if line.strip().upper() in _MERGE_WORDS:
            carry = line.strip()
        else:
            merged.append(line)

    if carry:
        if carry.upper() in _MERGE_WORDS_NEED_NUMBER and not merged:
            pass
        elif merged:
            merged[-1] = f"{merged[-1]} {carry}".strip() if merged[-1] else carry
        else:
            merged.append(carry)

    while len(merged) < 3:
        merged.append("")

    cleaned["address_line"] = merged[0]
    cleaned["address_line2"] = merged[1]
    cleaned["address_line3"] = merged[2]

    return cleaned


def _apply_geocode_fallback(addr: dict) -> dict:
    """Use Nominatim geocoding to fill missing fields on low-confidence addresses.

    Args:
        addr: The address dict to enrich.

    Returns:
        A copy of addr with any missing fields filled from geocode results.
    """
    query = format_mailing_block(addr)
    result = geocode_address(query)
    if result is None:
        return addr

    enriched = dict(addr)

    if not enriched.get("postcode") and result.get("postcode"):
        enriched["postcode"] = result["postcode"]
    if not enriched.get("city") and result.get("city"):
        enriched["city"] = result["city"].upper()
    if not enriched.get("state") and result.get("state"):
        enriched["state"] = result["state"].upper()
    if not enriched.get("address_line") and result.get("road"):
        enriched["address_line"] = result["road"].upper()

    return enriched


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

        best_addr, confidence = _select_best_address(clusters, raw_pc_counts)

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

        # Light merge: enrich best address with info from cluster siblings
        best_addr = _enrich_from_cluster(best_addr, clusters)

        # Ensemble: fill missing fields from cluster majority vote
        best_cluster = _find_best_cluster(clusters)
        best_addr = _ensemble_enhance(best_addr, best_cluster)

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
        corrected = _strip_leaked_fields(corrected)
        corrected = _merge_standalone_words(corrected)

        confidence = min(
            score_completeness(corrected) / MAX_COMPLETENESS_SCORE, 1.0
        )

        if NOMINATIM_ENABLED and confidence < CONFIDENCE_THRESHOLD:
            corrected = _apply_geocode_fallback(corrected)
            confidence = min(
                score_completeness(corrected) / MAX_COMPLETENESS_SCORE, 1.0
            )

        if confidence < CONFIDENCE_THRESHOLD:
            stats["low_confidence"] += 1

        mailing = format_mailing_block(corrected)

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

    return stats
