"""Helpers for classifying whether a formatted mailing block is mailable."""

from __future__ import annotations

import re

from src.processing.normaliser import STATE_MAPPING
from src.processing.parser import KNOWN_STATES

_POSTCODE_RE = re.compile(r"\b\d{5}\b")
_POSTCODE_LINE_RE = re.compile(r"^\d{5}\s")
_HAS_DIGIT_RE = re.compile(r"\d")

_KNOWN_STATES_UPPER = KNOWN_STATES | {v.upper() for v in STATE_MAPPING.values()}


def inspect_mailing_block(address: str) -> dict[str, bool]:
    """Inspect a formatted mailing block and return mailability signals."""
    text = str(address or "")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    has_postcode = bool(_POSTCODE_RE.search(text))
    has_street = any(
        not _POSTCODE_LINE_RE.match(line) and line.upper() not in _KNOWN_STATES_UPPER
        for line in lines
    )

    street_lines = [
        line for line in lines
        if not _POSTCODE_LINE_RE.match(line) and line.upper() not in _KNOWN_STATES_UPPER
    ]
    has_house_number = bool(_HAS_DIGIT_RE.search(" ".join(street_lines)))
    mailable = bool(text.strip()) and has_postcode and has_street

    return {
        "has_postcode": has_postcode,
        "has_street": has_street,
        "has_house_number": has_house_number,
        "mailable": mailable,
    }


def is_mailable_block(address: str) -> bool:
    """True when address has enough structure to be considered mailable."""
    return inspect_mailing_block(address)["mailable"]
