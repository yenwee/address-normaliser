"""Postcode validator for Malaysian addresses.

Validates postcodes against a database of known Malaysian postcodes and
provides suggestions for city/state corrections based on postcode lookups
and prefix-based state inference.
"""

import json
from typing import Optional

from rapidfuzz import fuzz


POSTCODE_STATE_PREFIXES: dict[str, str] = {}

_PREFIX_RANGES: list[tuple[int, int, str]] = [
    (1, 2, "PERLIS"),
    (5, 6, "KEDAH"),
    (8, 9, "KEDAH"),
    (10, 14, "PULAU PINANG"),
    (15, 18, "KELANTAN"),
    (20, 24, "TERENGGANU"),
    (25, 28, "PAHANG"),
    (30, 36, "PERAK"),
    (40, 48, "SELANGOR"),
    (50, 60, "WILAYAH PERSEKUTUAN KUALA LUMPUR"),
    (62, 62, "WILAYAH PERSEKUTUAN PUTRAJAYA"),
    (63, 64, "SELANGOR"),
    (68, 69, "SELANGOR"),
    (70, 73, "NEGERI SEMBILAN"),
    (75, 78, "MELAKA"),
    (79, 86, "JOHOR"),
    (87, 87, "WILAYAH PERSEKUTUAN LABUAN"),
    (88, 91, "SABAH"),
    (93, 98, "SARAWAK"),
]

for _start, _end, _state in _PREFIX_RANGES:
    for _num in range(_start, _end + 1):
        POSTCODE_STATE_PREFIXES[f"{_num:02d}"] = _state

STATE_MATCH_THRESHOLD = 70


class PostcodeValidator:
    """Validates Malaysian postcodes against a known database.

    Builds an internal lookup from postcode to city/state, and uses
    prefix-based inference as a fallback for unknown postcodes.
    """

    def __init__(self, postcodes_path: str) -> None:
        self._lookup: dict[str, dict[str, object]] = {}
        self._load(postcodes_path)

    def _load(self, postcodes_path: str) -> None:
        with open(postcodes_path, encoding="utf-8") as f:
            data = json.load(f)

        for state_entry in data["states"]:
            state_name = state_entry["name"].upper()
            for city_entry in state_entry["cities"]:
                city_name = city_entry["name"].upper()
                for postcode in city_entry["postcodes"]:
                    existing = self._lookup.get(postcode)
                    if existing is None:
                        self._lookup[postcode] = {
                            "city": city_name,  # primary/default (historical behavior)
                            "state": state_name,
                            "cities": [city_name],  # all known cities/localities for postcode
                        }
                    else:
                        existing["city"] = city_name
                        existing["state"] = state_name
                        cities = existing["cities"]
                        if city_name not in cities:
                            cities.append(city_name)

    def _select_city(self, postcode: str, provided_city: str, db_entry: dict) -> str:
        """Choose best city suggestion for postcode."""
        primary_city = str(db_entry.get("city", "") or "")
        state = str(db_entry.get("state", "") or "")
        cities = list(db_entry.get("cities", []) or [])

        provided = (provided_city or "").strip().upper()
        if provided:
            # Keep provided city/locality when it matches any known city for the postcode.
            best = ""
            best_score = -1.0
            for city in cities:
                score = fuzz.token_sort_ratio(provided, city)
                if score > best_score:
                    best_score = score
                    best = city
            if best and best_score >= 80:
                return best

        # Business rule: for KL core postcodes, prefer city label "KUALA LUMPUR"
        # over sub-localities (e.g. SETAPAK/WANGSA MAJU).
        if (
            postcode[:2].isdigit()
            and 50 <= int(postcode[:2]) <= 60
            and "KUALA LUMPUR" in state
        ):
            return "KUALA LUMPUR"

        return primary_city

    def validate(
        self,
        postcode: str,
        city: Optional[str] = None,
        state: Optional[str] = None,
    ) -> dict:
        """Validate a postcode against the database.

        Returns a dict with keys: valid, suggested_postcode, suggested_city,
        suggested_state.
        """
        city = city or ""
        state = state or ""

        result = {
            "valid": False,
            "suggested_postcode": postcode,
            "suggested_city": "",
            "suggested_state": "",
        }

        db_entry = self._lookup.get(postcode)

        if db_entry is not None:
            result["suggested_city"] = self._select_city(postcode, city, db_entry)
            result["suggested_state"] = db_entry["state"]

            state_ok = self._is_state_match(state, db_entry["state"])
            result["valid"] = state_ok
        else:
            prefix = postcode[:2] if len(postcode) >= 2 else ""
            suggested_state = POSTCODE_STATE_PREFIXES.get(prefix, "")
            result["suggested_state"] = suggested_state
            result["valid"] = False

        return result

    def _is_state_match(self, provided: str, expected: str) -> bool:
        """Check if provided state matches expected state.

        Empty/missing state is not considered a mismatch.
        Uses rapidfuzz token_sort_ratio with a configurable threshold.
        """
        if not provided or not provided.strip():
            return True

        score = fuzz.token_sort_ratio(provided.upper(), expected.upper())
        return score > STATE_MATCH_THRESHOLD

    def correct_address(self, addr: dict) -> tuple[dict, dict]:
        """Apply postcode validation and correct the address.

        Returns a tuple of (corrected_address_copy, validation_result).
        The original address dict is not mutated.
        """
        corrected = dict(addr)

        postcode = corrected.get("postcode", "")
        city = corrected.get("city", "")
        state = corrected.get("state", "")

        validation = self.validate(postcode, city, state)

        if validation["suggested_city"]:
            corrected["city"] = validation["suggested_city"]
        if validation["suggested_state"]:
            corrected["state"] = validation["suggested_state"]

        return corrected, validation
