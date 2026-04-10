"""Address parser for Malaysian comma-separated address strings.

Parses raw address strings from Excel ADDR columns into structured dicts
with address_line, address_line2, address_line3, postcode, city, state fields.
"""

import re
from typing import Optional

import pandas as pd

KNOWN_STATES = frozenset({
    "JOHOR",
    "KEDAH",
    "KELANTAN",
    "MELAKA",
    "NEGERI SEMBILAN",
    "PAHANG",
    "PERAK",
    "PERLIS",
    "PULAU PINANG",
    "SABAH",
    "SARAWAK",
    "SELANGOR",
    "TERENGGANU",
    "WILAYAH PERSEKUTUAN",
    "W.P. KUALA LUMPUR",
    "WP KUALA LUMPUR",
    "WP",
    "WPKL",
    "KL",
    "KUALA LUMPUR",
    "PENANG",
    "N. SEMBILAN",
    "N.SEMBILAN",
    "LABUAN",
    "PUTRAJAYA",
    "W.P. PUTRAJAYA",
    "W.P. LABUAN",
})

_POSTCODE_RE = re.compile(r"\b(\d{5})\b")
_JUNK_DIGIT_RE = re.compile(r"^\d{10,12}$")
_NULL_VALUES = frozenset({"NULL", "null", "Null", "NONE", "none", "None", "-"})


def _clean_field(value: str) -> str:
    """Normalize a single field: strip, collapse whitespace, handle NULL."""
    value = value.strip()
    if value in _NULL_VALUES:
        return ""
    return re.sub(r"\s+", " ", value)


def _is_junk(value: str) -> bool:
    """Check if a value is a junk IC/phone number (10-12 digit sequence)."""
    return bool(_JUNK_DIGIT_RE.match(value.strip()))


def _is_state(value: str) -> bool:
    """Check if a value is a known Malaysian state."""
    return value.upper() in KNOWN_STATES


def _find_postcode_index(fields: list[str]) -> Optional[int]:
    """Find the index of the first field that is a 4-5 digit postcode.

    Malaysian postcodes are 5 digits, but some data sources drop the leading
    zero (e.g. 7000 instead of 07000 for Langkawi).
    """
    for i, f in enumerate(fields):
        if re.fullmatch(r"\d{5}", f):
            return i
    # Second pass: 4-digit postcodes (leading zero dropped)
    for i, f in enumerate(fields):
        if re.fullmatch(r"\d{4}", f):
            fields[i] = f.zfill(5)
            return i
    return None


def _extract_postcode_from_text(text: str) -> Optional[str]:
    """Extract a 4-5 digit postcode embedded in free text."""
    match = _POSTCODE_RE.search(text)
    if match:
        return match.group(1)
    # Try 4-digit (leading zero dropped)
    match4 = re.search(r"\b(\d{4})\b", text)
    if match4:
        return match4.group(1).zfill(5)
    return None


def parse_address(raw) -> Optional[dict]:
    """Parse a single comma-separated address string into a structured dict.

    Args:
        raw: A comma-separated address string, or None/NaN.

    Returns:
        A dict with keys: address_line, address_line2, address_line3,
        postcode, city, state, raw. Returns None for empty/junk addresses.
    """
    if raw is None:
        return None
    if isinstance(raw, float):
        if pd.isna(raw):
            return None
    if not isinstance(raw, str):
        return None

    raw_str = raw
    fields = [_clean_field(f) for f in raw_str.split(",")]

    non_empty = [f for f in fields if f]
    if not non_empty:
        return None

    meaningful = [f for f in non_empty if not _is_junk(f)]
    if not meaningful:
        return None

    postcode_idx = _find_postcode_index(fields)

    address_line = ""
    address_line2 = ""
    address_line3 = ""
    postcode = ""
    city = ""
    state = ""

    if postcode_idx is not None:
        postcode = fields[postcode_idx]

        pre_fields = [f for f in fields[:postcode_idx] if f]
        if len(pre_fields) >= 1:
            address_line = pre_fields[0]
        if len(pre_fields) >= 2:
            address_line2 = pre_fields[1]
        if len(pre_fields) >= 3:
            address_line3 = " ".join(pre_fields[2:])

        post_fields = [f for f in fields[postcode_idx + 1:] if f]

        city_candidate = ""
        state_candidate = ""

        if len(post_fields) >= 2:
            city_candidate = post_fields[0]
            state_candidate = post_fields[1]
        elif len(post_fields) == 1:
            val = post_fields[0]
            if _is_state(val):
                state_candidate = val
            else:
                city_candidate = val

        if city_candidate and state_candidate:
            if _is_state(city_candidate) and not _is_state(state_candidate):
                city = state_candidate
                state = city_candidate
            else:
                city = city_candidate
                state = state_candidate
        else:
            city = city_candidate
            state = state_candidate

    else:
        all_text = " ".join(f for f in fields if f)
        extracted = _extract_postcode_from_text(all_text)
        if extracted:
            postcode = extracted
            first_non_empty = fields[0] if fields else ""
            address_line = first_non_empty
        else:
            if not meaningful:
                return None
            if len(meaningful) >= 1:
                address_line = meaningful[0]
            if len(meaningful) >= 2:
                address_line2 = meaningful[1]

    if not postcode and not address_line and not city and not state:
        return None

    return {
        "address_line": address_line,
        "address_line2": address_line2,
        "address_line3": address_line3,
        "postcode": postcode,
        "city": city,
        "state": state,
        "raw": raw_str,
    }


def parse_all_addresses(row: pd.Series, addr_columns: list[str]) -> list[dict]:
    """Parse all ADDR columns from a pandas DataFrame row.

    Args:
        row: A pandas Series representing a single row.
        addr_columns: List of column names to parse (e.g. ["ADDR0", "ADDR1", ...]).

    Returns:
        List of valid parsed address dicts, each with an added "source_column" key.
    """
    results = []
    for col in addr_columns:
        if col not in row.index:
            continue
        val = row[col]
        parsed = parse_address(val)
        if parsed is not None:
            parsed["source_column"] = col
            results.append(parsed)
    return results
