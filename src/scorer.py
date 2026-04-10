"""Address completeness scorer for Malaysian addresses."""

import re

_POSTCODE_RE = re.compile(r"^\d{5}$")

_STREET_NUMBER_KEYWORDS = ("NO", "LOT", "UNIT", "BLK", "BLOK")
_STREET_NAME_KEYWORDS = ("JALAN", "LORONG", "PERSIARAN", "LEBUH", "LINTANG", "LENGKOK")
_AREA_KEYWORDS = ("TAMAN", "KAMPUNG", "BANDAR", "DESA", "PANGSAPURI", "FLAT", "APARTMENT")

_STREET_NUMBER_RE = re.compile(
    r"\b(?:" + "|".join(_STREET_NUMBER_KEYWORDS) + r")\b",
    re.IGNORECASE,
)
_STREET_NAME_RE = re.compile(
    r"\b(?:" + "|".join(_STREET_NAME_KEYWORDS) + r")\b",
    re.IGNORECASE,
)
_AREA_RE = re.compile(
    r"\b(?:" + "|".join(_AREA_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def score_completeness(addr: dict) -> int:
    """Score an address dict by completeness.

    Returns an integer score (0-11) where higher means more complete.

    Scoring rules:
        +3  valid 5-digit postcode
        +2  non-empty city
        +2  non-empty state
        +1  street number keyword in address text
        +1  street name keyword in address text
        +1  area keyword in address text
        +1  non-empty address_line2
    """
    score = 0

    postcode = addr.get("postcode", "")
    if _POSTCODE_RE.match(str(postcode)):
        score += 3

    if str(addr.get("city", "")).strip():
        score += 2

    if str(addr.get("state", "")).strip():
        score += 2

    address_line = str(addr.get("address_line", ""))
    address_line2 = str(addr.get("address_line2", ""))
    combined_text = (address_line + " " + address_line2).strip()

    if _STREET_NUMBER_RE.search(combined_text):
        score += 1

    if _STREET_NAME_RE.search(combined_text):
        score += 1

    if _AREA_RE.search(combined_text):
        score += 1

    if address_line2.strip():
        score += 1

    return score
