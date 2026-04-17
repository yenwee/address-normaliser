"""MyKad IC number utilities for Malaysian address normalisation.

Extracts birth state from IC number positions 7-8 (0-indexed from digits).
IC format: YYMMDDSSXXXX where SS = birth state code.
"""

import re

_IC_RE = re.compile(r"^\d{12}$")

# MyKad state codes -> canonical state names
# Codes 01-16: primary codes
# Codes 21-59: extended codes (multiple codes per state)
# Codes 60-99: foreign born (not mapped)
IC_STATE_CODES: dict[str, str] = {
    "01": "JOHOR",
    "02": "KEDAH",
    "03": "KELANTAN",
    "04": "MELAKA",
    "05": "NEGERI SEMBILAN",
    "06": "PAHANG",
    "07": "PULAU PINANG",
    "08": "PERAK",
    "09": "PERLIS",
    "10": "SELANGOR",
    "11": "TERENGGANU",
    "12": "SABAH",
    "13": "SARAWAK",
    "14": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "15": "WILAYAH PERSEKUTUAN LABUAN",
    "16": "WILAYAH PERSEKUTUAN PUTRAJAYA",
    # Extended codes
    "21": "JOHOR",
    "22": "JOHOR",
    "23": "JOHOR",
    "24": "JOHOR",
    "25": "KEDAH",
    "26": "KEDAH",
    "27": "KEDAH",
    "28": "KELANTAN",
    "29": "KELANTAN",
    "30": "MELAKA",
    "31": "NEGERI SEMBILAN",
    "32": "NEGERI SEMBILAN",
    "33": "PAHANG",
    "34": "PAHANG",
    "35": "PULAU PINANG",
    "36": "PULAU PINANG",
    "37": "PERAK",
    "38": "PERAK",
    "39": "PERAK",
    "40": "PERLIS",
    "41": "SELANGOR",
    "42": "SELANGOR",
    "43": "SELANGOR",
    "44": "SELANGOR",
    "45": "TERENGGANU",
    "46": "TERENGGANU",
    "47": "SABAH",
    "48": "SABAH",
    "49": "SABAH",
    "50": "SARAWAK",
    "51": "SARAWAK",
    "52": "SARAWAK",
    "53": "SARAWAK",
    "54": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "55": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "56": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "57": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "58": "WILAYAH PERSEKUTUAN LABUAN",
    "59": "SABAH",
}


def extract_birth_state(ic: str) -> str:
    """Extract birth state from a MyKad IC number.

    Args:
        ic: A 12-digit Malaysian IC number string.

    Returns:
        The canonical state name, or empty string if IC is invalid
        or the person was born outside Malaysia.
    """
    cleaned = re.sub(r"[-\s]", "", str(ic).strip())
    if not _IC_RE.match(cleaned):
        return ""
    state_code = cleaned[6:8]
    return IC_STATE_CODES.get(state_code, "")
