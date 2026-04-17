"""Format a normalised address dict into a mailing block.

Output line order follows the client specification:
  Line 1: Street (Lot/No, Lorong, Jalan, Persiaran, PO Box)
  Line 2: Area (Taman, Kampung, Ladang, FELDA, Bandar)
  Line 3: Postcode + City
  Line 4: State

Text cleanup helpers (dedup, period artefacts, trailing labels, stale BATU)
live in text_utils.py; this file focuses on line ordering and field layout.
"""

import re
from typing import Dict

from src.text_utils import clean_text, dedup_within_line, strip_trailing_label

_STREET_KW = r"(?:JALAN|LORONG|PERSIARAN|LEBUH|LINTANG|LENGKOK)"
_AREA_KW_PATTERN = re.compile(
    r"\b(TAMAN|KAMPUNG|LADANG|FELDA|BANDAR|DESA|FLAT|PANGSAPURI|APARTMENT|RUMAH|PROJEK PERUMAHAN RAKYAT)\b",
    re.IGNORECASE,
)
_STREET_KW_PATTERN = re.compile(rf"\b{_STREET_KW}\b", re.IGNORECASE)


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
    address_line = clean_text(addr.get("address_line", ""))
    address_line2 = clean_text(addr.get("address_line2", ""))
    address_line3 = clean_text(addr.get("address_line3", ""))

    # Reorder: split mixed street+area into proper lines
    line1, line2, line3 = _reorder_lines(address_line, address_line2, address_line3)

    # Reorder Line 1 tokens: LOT/NO before LORONG/JALAN
    line1 = _reorder_street_tokens(line1)

    # Cross-field dedup: re-run dedup on the combined lines (single-field dedup
    # can't see duplicates that only appear after _reorder_lines concatenates).
    line1 = dedup_within_line(line1)
    line2 = dedup_within_line(line2)
    line3 = dedup_within_line(line3)

    # Strip dangling labels at the end of a line (e.g. "JALAN HOSPITAL JALAN" ->
    # "JALAN HOSPITAL"; a line consisting of just "KAMPUNG" is dropped).
    line1 = strip_trailing_label(line1)
    line2 = strip_trailing_label(line2)
    line3 = strip_trailing_label(line3)

    lines: list[str] = []
    if line1:
        lines.append(line1)
    if line2:
        lines.append(line2)
    if line3:
        lines.append(line3)

    # Strip city/state names from end of address lines
    city_raw = clean_text(addr.get("city", ""))
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
