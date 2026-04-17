"""Text cleanup helpers shared by formatter and cleaning steps.

Regex-heavy utilities for Malaysian address text cleanup:
  - junk symbol removal (@, #, *, _)
  - period artefact collapse (NO. -> NO, KAMPUNG.MELAYU -> KAMPUNG MELAYU)
  - duplicate-keyword collapse ("TAMAN TAMAN" -> "TAMAN")
  - duplicate-phrase dedup within a single line
  - trailing bare-label stripping ("JALAN HOSPITAL JALAN" -> "JALAN HOSPITAL")
  - leading placeholder removal ("0 BATU ILP KK" -> "ILP KK" when followed by
    a stale BATU, otherwise just strips the leading "0 ")
  - stale BATU removal (reversed form like "<digit> BATU <non-digit>" that
    isn't a milestone marker like "BATU 7" or a place name like "BATU CAVES")
"""

import re

_JUNK_SYMBOLS = re.compile(r"[#@*_]+")
_DUPE_KEYWORDS = [
    "JALAN", "TAMAN", "KAMPUNG", "LORONG", "BANDAR", "SUNGAI",
    "BATU", "FELDA", "DESA", "PERSIARAN", "LEBUH",
]

# Trailing bare generic label that lost its content (e.g. "JALAN HOSPITAL JALAN"
# -> trailing JALAN has no name after it).
_TRAILING_LABEL_RE = re.compile(
    r"\s+(JALAN|LORONG|KAMPUNG|BATU|TAMAN|BANDAR|DESA|FELDA|PERSIARAN|LEBUH|SUNGAI)\s*$",
    re.IGNORECASE,
)

_PERIOD_CLEANUP_RE = re.compile(r"\s*\.\s*")
_NO_PERIOD_RE = re.compile(r"\b(NO|LOT|BLOK|BLK|UNIT|TKT)\.\s*", re.IGNORECASE)

_PLACEHOLDER_LINE_RE = re.compile(r"^(0+|NA|N/A|NULL|NIL|-+)$", re.IGNORECASE)
# Leading placeholder token: "0 BATU ILP KK" -> strip the "0 " prefix
_LEADING_PLACEHOLDER_RE = re.compile(r"^(0+|NA|NULL|NIL)\s+(?=\S)", re.IGNORECASE)
# Stale BATU: appears AFTER a number (reversed form, not the valid "BATU 7" pattern)
# AND not followed by a known place-name suffix. Protects real names like
# "117 BATU CAVES", "BATU PAHAT", "BATU GAJAH" which are legitimate.
_BATU_PLACE_SUFFIX = (
    r"CAVES|PAHAT|GAJAH|ARANG|BERENDAM|KIKIR|FERRINGHI|KAWAN|LINTANG|"
    r"BURUK|BURO[KH]|HITAM|ENAM|TUJUH|LAPAN|SEMBILAN|PUTIH|MERAH|APUNG"
)
_STALE_BATU_RE = re.compile(
    rf"(?<=\d)\s+BATU\b(?!\s+(?:\d|{_BATU_PLACE_SUFFIX}))",
    re.IGNORECASE,
)

_BARE_LABELS = frozenset({
    "JALAN", "KAMPUNG", "LORONG", "BATU", "TAMAN",
    "BANDAR", "DESA", "FELDA", "PERSIARAN", "LEBUH", "SUNGAI",
})


def dedup_within_line(line: str) -> str:
    """Remove repeated multi-word phrases within a single line.

    E.g. "JALAN K2 JALAN K2" -> "JALAN K2"
         "TAMAN PERTIWI JALAN PERTIW 3 TAMAN PERTIWI" -> "TAMAN PERTIWI JALAN PERTIW 3"
    """
    words = line.split()
    for length in range(len(words) // 2, 1, -1):
        for i in range(len(words) - 2 * length + 1):
            phrase = [w.upper() for w in words[i:i + length]]
            next_phrase = [w.upper() for w in words[i + length:i + 2 * length]]
            if phrase == next_phrase:
                return dedup_within_line(" ".join(words[:i + length] + words[i + 2 * length:]))
    return line


def clean_text(text: str) -> str:
    """Remove junk symbols and duplicate keywords from address text."""
    text = _JUNK_SYMBOLS.sub("", text)
    # Collapse period artefacts: "NO.", "NO. 539", "KAMPUNG. BUKIT" -> space
    text = _NO_PERIOD_RE.sub(lambda m: f"{m.group(1).upper()} ", text)
    text = _PERIOD_CLEANUP_RE.sub(" ", text)
    for kw in _DUPE_KEYWORDS:
        text = re.sub(rf"\b({kw})\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = dedup_within_line(text)
    return re.sub(r"\s+", " ", text).strip()


def strip_trailing_label(line: str) -> str:
    """Strip a dangling generic label at the end of a line.

    Only strips when the trailing label already appears earlier in the same
    line — that protects real place names like "TIKAM BATU" or "BAKAR BATU"
    where BATU is a legitimate suffix, while still catching "JALAN HOSPITAL JALAN".
    Also drops lines that are ONLY a bare label.
    """
    stripped = line.strip()
    if _PLACEHOLDER_LINE_RE.match(stripped):
        return ""
    if stripped.upper() in _BARE_LABELS:
        return ""
    # Drop leading placeholder tokens: "0 BATU ILP KK" -> "BATU ILP KK"
    stripped = _LEADING_PLACEHOLDER_RE.sub("", stripped).strip()
    # Remove stale BATU (not "BATU 7" milestone form)
    cleaned = _STALE_BATU_RE.sub(" ", stripped)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned:
        stripped = cleaned
    while True:
        m = _TRAILING_LABEL_RE.search(stripped)
        if not m:
            break
        trailing = m.group(1).upper()
        rest = stripped[:m.start()]
        rest_tokens = {t.upper() for t in rest.split()}
        if trailing not in rest_tokens:
            break
        stripped = rest.strip()
    return stripped
