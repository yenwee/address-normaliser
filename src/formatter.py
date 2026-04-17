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


def _clean_text(text: str) -> str:
    """Remove junk symbols and duplicate keywords from address text."""
    text = _JUNK_SYMBOLS.sub("", text)
    for kw in _DUPE_KEYWORDS:
        text = re.sub(rf"\b({kw})\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


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

    lines: list[str] = []
    if line1:
        lines.append(line1)
    if line2:
        lines.append(line2)
    if line3:
        lines.append(line3)

    postcode = addr.get("postcode", "").strip()
    city = _clean_text(addr.get("city", ""))
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
