"""Address normaliser for Malaysian addresses.

Expands common abbreviations, cleans whitespace, normalises state names,
and standardises parsed address dicts for downstream processing.
"""

import re


ABBREVIATIONS = {
    "JLN": "JALAN",
    "JL": "JALAN",
    "JLAN": "JALAN",
    "JALN": "JALAN",
    "TMN": "TAMAN",
    "TMAN": "TAMAN",
    "LRG": "LORONG",
    "KG": "KAMPUNG",
    "KPG": "KAMPUNG",
    "KMPG": "KAMPUNG",
    "KAMPONG": "KAMPUNG",
    "BDR": "BANDAR",
    "SG": "SUNGAI",
    "BT": "BATU",
    "PSR": "PASAR",
    "PPR": "PROJEK PERUMAHAN RAKYAT",
    "SBG": "SUBANG",
    "PJY": "PUTRAJAYA",
    "SEC": "SEKSYEN",
    "SEK": "SEKSYEN",
    "KWS": "KAWASAN",
    "PER": "PERINDUSTRIAN",
    "IND": "INDUSTRI",
    # SRI and SERI are both valid Malay honorifics, but in place names they refer
    # to the same locality (e.g. "TAMAN SRI PUTRI" == "TAMAN SERI PUTRI"). We
    # canonicalise to SERI because the expert golden uses SERI in 47 cases vs
    # SRI in 30 — normalising here keeps mailing output consistent.
    "SRI": "SERI",
    "DR": "DARUL",
    "RKAT": "RUMAH PANGSA",
    "PPMS": "PROJEK PERUMAHAN MURAH SEMENANJUNG",
    "LG": "LORONG",
    "PS": "PETI SURAT",
}

_ABBREV_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(ABBREVIATIONS, key=len, reverse=True)) + r")\b"
)

STATE_MAPPING = {
    "WP": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WPKL": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "KL": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "KUALA LUMPUR": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "W.P. KUALA LUMPUR": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WP KUALA LUMPUR": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "WILAYAH PERSEKUTUAN": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
    "PENANG": "PULAU PINANG",
    "N. SEMBILAN": "NEGERI SEMBILAN",
    "N.SEMBILAN": "NEGERI SEMBILAN",
    "W.P. PUTRAJAYA": "WILAYAH PERSEKUTUAN PUTRAJAYA",
    "WP PUTRAJAYA": "WILAYAH PERSEKUTUAN PUTRAJAYA",
    "PUTRAJAYA": "WILAYAH PERSEKUTUAN PUTRAJAYA",
    "W.P. LABUAN": "WILAYAH PERSEKUTUAN LABUAN",
    "WP LABUAN": "WILAYAH PERSEKUTUAN LABUAN",
    "LABUAN": "WILAYAH PERSEKUTUAN LABUAN",
}

_WORD_HYPHEN_RE = re.compile(r"(?<=[A-Z])\s*-\s*(?=[A-Z])|\s+-\s*(?=[A-Z])|\s*-\s+")  # word-word or space-hyphen-word
_DOT_SEPARATOR_RE = re.compile(r"(?<=[A-Za-z0-9])\.(?=[A-Za-z])")
_WHITESPACE_RE = re.compile(r"\s+")
# Split digits from known abbreviations stuck together (e.g. 117KPG -> 117 KPG)
# Only splits when followed by a known abbreviation, not arbitrary letters like 6AB
_KNOWN_ABBREVS = "|".join(sorted(ABBREVIATIONS.keys(), key=len, reverse=True))
_DIGIT_ABBREV_RE = re.compile(rf"(\d)({_KNOWN_ABBREVS})\b")


def expand_abbreviations(text: str) -> str:
    """Expand common Malaysian address abbreviations using word-boundary regex.

    Only matches whole words to prevent partial expansions
    (e.g. JLNS will NOT become JALANS).

    Args:
        text: The address text to process (expected uppercase).

    Returns:
        Text with abbreviations expanded.
    """
    if not text:
        return text
    return _ABBREV_PATTERN.sub(lambda m: ABBREVIATIONS[m.group(0)], text)


def normalise_state(state: str) -> str:
    """Normalise a Malaysian state name to its standard form.

    Args:
        state: The raw state string.

    Returns:
        The standardised state name, or the input uppercased if no mapping exists.
    """
    if not state:
        return state
    upper = state.strip().upper()
    return STATE_MAPPING.get(upper, upper)


def normalise_address(addr: dict) -> dict:
    """Normalise a parsed address dict.

    Applies uppercasing, whitespace collapsing, abbreviation expansion,
    hyphen normalisation to address lines; state normalisation; and
    city uppercasing. Passthrough fields: postcode, raw, source_column.

    Args:
        addr: A parsed address dict from the parser module.

    Returns:
        A new dict with normalised values. The original dict is not mutated.
    """

    def _normalise_line(value: str) -> str:
        line = value.upper()
        line = _DOT_SEPARATOR_RE.sub(" ", line)  # "432.P5.KOLEJ15" -> "432 P5 KOLEJ15"
        line = _DIGIT_ABBREV_RE.sub(r"\1 \2", line)  # split "117KPG" -> "117 KPG"
        line = _WHITESPACE_RE.sub(" ", line).strip()
        line = _WORD_HYPHEN_RE.sub(" ", line)
        line = expand_abbreviations(line)
        return line

    city_raw = addr.get("city", "")
    city = _WHITESPACE_RE.sub(" ", city_raw.upper()).strip()

    return {
        "address_line": _normalise_line(addr.get("address_line", "")),
        "address_line2": _normalise_line(addr.get("address_line2", "")),
        "address_line3": _normalise_line(addr.get("address_line3", "")),
        "postcode": addr.get("postcode", ""),
        "city": city,
        "state": normalise_state(addr.get("state", "")),
        "raw": addr.get("raw", ""),
        "source_column": addr.get("source_column", ""),
    }
