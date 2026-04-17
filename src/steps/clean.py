"""Post-selection cleanup of the chosen address.

Two cleanup operations applied after validator + state normalisation:

1. strip_leaked_fields: remove state names and postcode+city patterns that
   leaked into address_line fields (source data is messy — e.g. field 1 says
   "JLN ADABI KOTA BHARU" when city is already "KOTA BHARU" in field 5).

2. merge_standalone_words: source data sometimes splits "Kampung" or "Jalan"
   into a separate comma field, producing standalone address lines like just
   "JALAN" or "KAMPUNG". These get merged with the next non-empty line, or
   dropped if they need a number (BATU) and none follows.
"""

import re

from src.processing.parser import KNOWN_STATES


def strip_leaked_fields(addr: dict) -> dict:
    """Remove state names and postcode+city patterns that leaked into address lines."""
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


def merge_standalone_words(addr: dict) -> dict:
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
