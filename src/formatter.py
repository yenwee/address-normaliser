import re
from typing import Dict

_STREET_KW = r"(?:JALAN|LORONG|PERSIARAN|LEBUH|LINTANG|LENGKOK)"
_AREA_KW_PATTERN = re.compile(
    r"\b(TAMAN|KAMPUNG|LADANG|FELDA|BANDAR|DESA|FLAT|PANGSAPURI|APARTMENT|RUMAH|PROJEK PERUMAHAN RAKYAT)\b",
    re.IGNORECASE,
)
_STREET_KW_PATTERN = re.compile(rf"\b{_STREET_KW}\b", re.IGNORECASE)

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


def _dedup_within_line(line: str) -> str:
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
                return _dedup_within_line(" ".join(words[:i + length] + words[i + 2 * length:]))
    return line


def _clean_text(text: str) -> str:
    """Remove junk symbols and duplicate keywords from address text."""
    text = _JUNK_SYMBOLS.sub("", text)
    # Collapse period artefacts: "NO.", "NO. 539", "KAMPUNG. BUKIT" -> space
    text = _NO_PERIOD_RE.sub(lambda m: f"{m.group(1).upper()} ", text)
    text = _PERIOD_CLEANUP_RE.sub(" ", text)
    for kw in _DUPE_KEYWORDS:
        text = re.sub(rf"\b({kw})\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    text = _dedup_within_line(text)
    return re.sub(r"\s+", " ", text).strip()


_BARE_LABELS = frozenset({
    "JALAN", "KAMPUNG", "LORONG", "BATU", "TAMAN",
    "BANDAR", "DESA", "FELDA", "PERSIARAN", "LEBUH", "SUNGAI",
})


def _strip_trailing_label(line: str) -> str:
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


def _reorder_lines(addr_line: str, addr_line2: str, addr_line3: str) -> tuple[str, str, str]:
    """Split mixed street+area into proper lines.

    Line 1: Lot/No, PO Box, Batu, Mukim, Lorong, Jalan, Persiaran
    Line 2: Taman, Kampung, Ladang, FELDA, Bandar
    """
    combined = " ".join(filter(None, [addr_line, addr_line2, addr_line3])).strip()
    if not combined:
        return "", "", ""

    # Find first area keyword NOT preceded by a street keyword
    best_split = None
    for m in _AREA_KW_PATTERN.finditer(combined):
        pos = m.start()
        before = combined[:pos].strip()
        prev_words = before.split()
        if prev_words and _STREET_KW_PATTERN.match(prev_words[-1]):
            continue
        if before:
            best_split = pos
            break

    if best_split is not None:
        street = combined[:best_split].strip()
        area = combined[best_split:].strip()
        if street and area:
            return street, area, ""

    return combined, "", ""


_HOUSE_ID_RE = re.compile(
    r"^((?:(?:NO\.?|LOT|UNIT|BLK|BLOK)\s+)?\S+(?:\s+\S+)?)",
    re.IGNORECASE,
)
_STREET_BEFORE_HOUSE_RE = re.compile(
    r"^((?:LORONG|JALAN|PERSIARAN|LEBUH|LINTANG|LENGKOK)\s+\S+(?:\s+\S+)?)\s+"
    r"((?:NO\.?|LOT|UNIT)\s+\S+)",
    re.IGNORECASE,
)


def _reorder_street_tokens(line: str) -> str:
    """Move LOT/NO before LORONG/JALAN on Line 1.

    'LORONG 5 LOT 265' -> 'LOT 265 LORONG 5'
    'JALAN 3 NO 42'    -> 'NO 42 JALAN 3'
    'LOT 265 LORONG 5' -> unchanged (already correct)
    """
    m = _STREET_BEFORE_HOUSE_RE.match(line)
    if m:
        street_part = m.group(1)
        house_part = m.group(2)
        rest = line[m.end():].strip()
        parts = [house_part, street_part]
        if rest:
            parts.append(rest)
        return " ".join(parts)
    return line


def format_mailing_block(addr: Dict[str, str]) -> str:
    """Format a normalised address dict into a mailing block for envelope printing.

    Output line order:
        Line 1: Street (Lot/No, Lorong, Jalan, Persiaran, PO Box)
        Line 2: Area (Taman, Kampung, Ladang, FELDA, Bandar)
        Line 3: Postcode + City
        Line 4: State
    """
    address_line = _clean_text(addr.get("address_line", ""))
    address_line2 = _clean_text(addr.get("address_line2", ""))
    address_line3 = _clean_text(addr.get("address_line3", ""))

    # Reorder: split mixed street+area into proper lines
    line1, line2, line3 = _reorder_lines(address_line, address_line2, address_line3)

    # Reorder Line 1 tokens: LOT/NO before LORONG/JALAN
    line1 = _reorder_street_tokens(line1)

    # Cross-field dedup: re-run dedup on the combined lines (single-field dedup
    # can't see duplicates that only appear after _reorder_lines concatenates).
    line1 = _dedup_within_line(line1)
    line2 = _dedup_within_line(line2)
    line3 = _dedup_within_line(line3)

    # Strip dangling labels at the end of a line (e.g. "JALAN HOSPITAL JALAN" ->
    # "JALAN HOSPITAL"; a line consisting of just "KAMPUNG" is dropped).
    line1 = _strip_trailing_label(line1)
    line2 = _strip_trailing_label(line2)
    line3 = _strip_trailing_label(line3)

    lines: list[str] = []
    if line1:
        lines.append(line1)
    if line2:
        lines.append(line2)
    if line3:
        lines.append(line3)

    # Strip city/state names from end of address lines
    city_raw = _clean_text(addr.get("city", ""))
    state_raw = addr.get("state", "").strip()
    for i in range(len(lines)):
        line_upper = lines[i].upper()
        # Strip city from end
        if city_raw and len(city_raw) > 3 and line_upper.endswith(city_raw.upper()):
            stripped = lines[i][: -len(city_raw)].strip()
            if stripped:
                lines[i] = stripped
                line_upper = stripped.upper()
        # Strip state from end
        if state_raw and len(state_raw) > 2 and line_upper.endswith(state_raw.upper()):
            stripped = lines[i][: -len(state_raw)].strip()
            if stripped:
                lines[i] = stripped

    # Remove lines that became empty after stripping
    lines = [l for l in lines if l.strip()]

    postcode = addr.get("postcode", "").strip()
    city = city_raw
    if postcode and city:
        lines.append(f"{postcode} {city}")
    elif postcode:
        lines.append(postcode)
    elif city:
        lines.append(city)

    state = addr.get("state", "").strip()
    if state:
        lines.append(state)

    # Extract and move PETI SURAT (PO Box) to first line
    _PS_RE = re.compile(r"(PETI SURAT\s+\S+(?:\s+\S+)?)", re.IGNORECASE)
    for i, line in enumerate(lines):
        if "PETI SURAT" in line.upper():
            m = _PS_RE.search(line)
            if m:
                ps_text = m.group(1).strip()
                remainder = line[:m.start()].strip() + " " + line[m.end():].strip()
                remainder = remainder.strip()
                if remainder and remainder.upper() != ps_text.upper():
                    lines[i] = remainder
                    lines.insert(0, ps_text)
                elif i > 0:
                    lines.insert(0, lines.pop(i))
            break

    # Deduplicate: identical or substring of next line
    deduped: list[str] = []
    for i, line in enumerate(lines):
        upper = line.upper()
        next_upper = lines[i + 1].upper() if i + 1 < len(lines) else ""
        prev_upper = deduped[-1].upper() if deduped else ""

        if upper == prev_upper:
            continue
        if next_upper and upper in next_upper:
            continue

        deduped.append(line)

    return "\n".join(deduped)
