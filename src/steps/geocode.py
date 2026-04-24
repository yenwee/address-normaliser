"""Optional Nominatim geocoding fallback and online validation helpers."""

import re

from rapidfuzz import fuzz

from src.processing.formatter import format_mailing_block
from src.processing.normaliser import normalise_state
from src.io.nominatim import geocode_address


CITY_MATCH_THRESHOLD = 75


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").upper()).strip()


def _norm_postcode(value: str) -> str:
    return str(value or "").strip()


def _postcode_values(value: str) -> set[str]:
    """Extract all 5-digit postcodes from provider strings.

    Some providers return multiple candidates in one field, e.g. "50450, 55000".
    """
    return set(re.findall(r"\b\d{5}\b", str(value or "")))


def _build_geocode_query(addr: dict) -> str:
    """Build a geocoder-friendly single-line query from mailing block fields."""
    query_addr = dict(addr)
    query_addr["state"] = normalise_state(query_addr.get("state", ""))
    mailing = format_mailing_block(query_addr)
    parts = [line.strip() for line in mailing.splitlines() if line.strip()]
    return ", ".join(parts)


def validate_address_online(addr: dict, geocode_fn=None) -> dict:
    """Validate an address online and classify the result.

    Status values:
        - match:     geocode result agrees with key fields
        - mismatch:  geocode result conflicts with key fields
        - no_result: geocoder returned no usable evidence
    """
    query = _build_geocode_query(addr)
    geocode_func = geocode_fn or geocode_address
    result = geocode_func(query)
    provider = str(result.get("provider", "")).strip() if isinstance(result, dict) else ""
    if not provider:
        provider = "nominatim"

    if result is None:
        return {
            "status": "no_result",
            "reason": "no_geocode_result",
            "query": query,
            "geocode": None,
            "city_score": None,
            "provider": provider,
        }

    local_postcode = _norm_postcode(addr.get("postcode", ""))
    local_postcodes = _postcode_values(local_postcode)
    local_city = _norm_text(addr.get("city", ""))
    local_state = normalise_state(_norm_text(addr.get("state", "")))

    geo_postcode = _norm_postcode(result.get("postcode", ""))
    geo_postcodes = _postcode_values(geo_postcode)
    geo_city = _norm_text(result.get("city", ""))
    geo_state = normalise_state(_norm_text(result.get("state", "")))

    if not (geo_postcode or geo_city or geo_state):
        return {
            "status": "no_result",
            "reason": "insufficient_geocode_fields",
            "query": query,
            "geocode": result,
            "city_score": None,
            "provider": provider,
        }

    if local_postcodes and geo_postcodes and local_postcodes.isdisjoint(geo_postcodes):
        return {
            "status": "mismatch",
            "reason": "postcode_mismatch",
            "query": query,
            "geocode": result,
            "city_score": None,
            "provider": provider,
        }

    if local_state and geo_state and local_state != geo_state:
        return {
            "status": "mismatch",
            "reason": "state_mismatch",
            "query": query,
            "geocode": result,
            "city_score": None,
            "provider": provider,
        }

    city_score = None
    if local_city and geo_city:
        city_score = fuzz.token_sort_ratio(local_city, geo_city)

    # City-only validation is noisy; only fail city when postcode/state are missing.
    core_verified = (
        bool(local_postcodes and geo_postcodes and not local_postcodes.isdisjoint(geo_postcodes))
        or bool(local_state and geo_state and local_state == geo_state)
    )
    if city_score is not None and city_score < CITY_MATCH_THRESHOLD and not core_verified:
        return {
            "status": "mismatch",
            "reason": "city_mismatch",
            "query": query,
            "geocode": result,
            "city_score": city_score,
            "provider": provider,
        }

    return {
        "status": "match",
        "reason": "matched",
        "query": query,
        "geocode": result,
        "city_score": city_score,
        "provider": provider,
    }


def apply_geocode_fallback(addr: dict) -> dict:
    """Use Nominatim geocoding to fill missing fields on low-confidence addresses.

    Args:
        addr: The address dict to enrich.

    Returns:
        A copy of addr with any missing fields filled from geocode results.
    """
    query = _build_geocode_query(addr)
    result = geocode_address(query)
    if result is None:
        return addr

    enriched = dict(addr)

    if not enriched.get("postcode") and result.get("postcode"):
        enriched["postcode"] = result["postcode"]
    if not enriched.get("city") and result.get("city"):
        enriched["city"] = result["city"].upper()
    if not enriched.get("state") and result.get("state"):
        enriched["state"] = result["state"].upper()
    if not enriched.get("address_line") and result.get("road"):
        enriched["address_line"] = result["road"].upper()

    return enriched
