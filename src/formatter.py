from typing import Dict


def format_mailing_block(addr: Dict[str, str]) -> str:
    """Format a normalised address dict into a mailing block string for envelope printing.

    Lines are assembled in order:
        1. address_line
        2. address_line2 (skipped if empty)
        3. address_line3 (skipped if empty)
        4. postcode + city combined (skipped if both empty)
        5. state (skipped if empty)
    """
    lines: list[str] = []

    address_line = addr.get("address_line", "").strip()
    if address_line:
        lines.append(address_line)

    address_line2 = addr.get("address_line2", "").strip()
    if address_line2:
        lines.append(address_line2)

    address_line3 = addr.get("address_line3", "").strip()
    if address_line3:
        lines.append(address_line3)

    postcode = addr.get("postcode", "").strip()
    city = addr.get("city", "").strip()
    if postcode and city:
        lines.append(f"{postcode} {city}")
    elif postcode:
        lines.append(postcode)
    elif city:
        lines.append(city)

    state = addr.get("state", "").strip()
    if state:
        lines.append(state)

    # Move PETI SURAT (PO Box) to first line — primary mailing identifier
    po_box_idx = None
    for i, line in enumerate(lines):
        if "PETI SURAT" in line.upper():
            po_box_idx = i
            break
    if po_box_idx is not None and po_box_idx > 0:
        lines.insert(0, lines.pop(po_box_idx))

    # Deduplicate: remove line if identical to adjacent, or if it's a
    # substring of the next line (e.g. "NO 4630" followed by "NO 4630 KG PETAI")
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
