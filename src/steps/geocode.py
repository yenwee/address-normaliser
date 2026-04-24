"""Optional Nominatim geocoding fallback and online validation helpers."""

import re

from rapidfuzz import fuzz

from src.processing.formatter import format_mailing_block
from src.processing.normaliser import normalise_state
from src.io.nominatim import geocode_address


CITY_MATCH_THRESHOLD = 75
ADDRESS_COMPONENT_MATCH_THRESHOLD = 80

_ADDRESS_COMPONENT_KEYWORDS = (
    "JALAN",
    "LORONG",
    "PERSIARAN",
    "LEBUH",
    "LINTANG",
    "LENGKOK",
    "TAMAN",
    "KAMPUNG",
    "BANDAR",
    "DESA",
)
_ADDRESS_COMPONENT_RE = re.compile(
    r"\b("
    + "|".join(_ADDRESS_COMPONENT_KEYWORDS)
    + r")\b\s+(.+?)(?=\b(?:"
    + "|".join(_ADDRESS_COMPONENT_KEYWORDS)
    + r")\b|$)",
    re.IGNORECASE,
)


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").upper()).strip()


def _norm_component_text(value: str) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())
    return re.sub(r"\s+", " ", text).strip()


def _norm_postcode(value: str) -> str:
    return str(value or "").strip()


def _postcode_values(value: str) -> set[str]:
    """Extract all 5-digit postcodes from provider strings.

    Some providers return multiple candidates in one field, e.g. "50450, 55000".
    """
    return set(re.findall(r"\b\d{5}\b", str(value or "")))


def _state_values(value: str) -> set[str]:
    """Normalise one or more provider state names for comparison.

    Some providers return combined state strings such as
    "Selangor, Federal Territory of Kuala Lumpur"; this should match either
    local state instead of becoming a false hard mismatch.
    """
    parts = re.split(r"[,;/]+", str(value or ""))
    return {normalise_state(_norm_text(part)) for part in parts if str(part).strip()}


def _build_geocode_query(addr: dict) -> str:
    """Build a geocoder-friendly single-line query from mailing block fields."""
    query_addr = dict(addr)
    query_addr["state"] = normalise_state(query_addr.get("state", ""))
    mailing = format_mailing_block(query_addr)
    parts = [line.strip() for line in mailing.splitlines() if line.strip()]
    return ", ".join(parts)


def _address_components(addr: dict) -> list[str]:
    """Extract street/area components worth checking against provider text."""
    combined = " ".join(
        str(addr.get(key, "") or "")
        for key in ("address_line", "address_line2", "address_line3")
    )
    components = []
    for match in _ADDRESS_COMPONENT_RE.finditer(combined):
        phrase = _norm_component_text(f"{match.group(1)} {match.group(2)}")
        if len(phrase.split()) >= 2:
            components.append(phrase)
    return components


def _provider_component_text(result: dict) -> str:
    """Build evidence text from provider fields that can confirm street/area."""
    fields = [
        result.get("formatted", ""),
        result.get("street", ""),
        result.get("area", ""),
    ]
    return _norm_component_text(" ".join(str(v or "") for v in fields))


def _address_component_score(addr: dict, result: dict) -> float | None:
    components = _address_components(addr)
    provider_text = _provider_component_text(result)
    if not components or not provider_text:
        return None

    scores = []
    for component in components:
        scores.append(fuzz.partial_ratio(component, provider_text))
        scores.append(fuzz.token_set_ratio(component, provider_text))
    return max(scores) if scores else None


def _classify_geocode_result(addr: dict, query: str, result: dict | None) -> dict:
    """Classify one provider response against the selected address."""
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
            "component_score": None,
            "provider": provider,
        }

    local_postcode = _norm_postcode(addr.get("postcode", ""))
    local_postcodes = _postcode_values(local_postcode)
    local_city = _norm_text(addr.get("city", ""))
    local_states = _state_values(addr.get("state", ""))

    geo_postcode = _norm_postcode(result.get("postcode", ""))
    geo_postcodes = _postcode_values(geo_postcode)
    geo_city = _norm_text(result.get("city", ""))
    geo_states = _state_values(result.get("state", ""))

    if not (geo_postcode or geo_city or geo_states):
        return {
            "status": "no_result",
            "reason": "insufficient_geocode_fields",
            "query": query,
            "geocode": result,
            "city_score": None,
            "component_score": None,
            "provider": provider,
        }

    if local_postcodes and geo_postcodes and local_postcodes.isdisjoint(geo_postcodes):
        return {
            "status": "mismatch",
            "reason": "postcode_mismatch",
            "query": query,
            "geocode": result,
            "city_score": None,
            "component_score": None,
            "provider": provider,
        }

    if local_states and geo_states and local_states.isdisjoint(geo_states):
        return {
            "status": "mismatch",
            "reason": "state_mismatch",
            "query": query,
            "geocode": result,
            "city_score": None,
            "component_score": None,
            "provider": provider,
        }

    city_score = None
    if local_city and geo_city:
        city_score = fuzz.token_sort_ratio(local_city, geo_city)

    # City-only validation is noisy; only fail city when postcode/state are missing.
    core_verified = (
        bool(local_postcodes and geo_postcodes and not local_postcodes.isdisjoint(geo_postcodes))
        or bool(local_states and geo_states and not local_states.isdisjoint(geo_states))
    )
    if city_score is not None and city_score < CITY_MATCH_THRESHOLD and not core_verified:
        return {
            "status": "mismatch",
            "reason": "city_mismatch",
            "query": query,
            "geocode": result,
            "city_score": city_score,
            "component_score": None,
            "provider": provider,
        }

    components = _address_components(addr)
    provider_component_text = _provider_component_text(result)
    if components and not provider_component_text:
        return {
            "status": "mismatch",
            "reason": "address_component_unverified",
            "query": query,
            "geocode": result,
            "city_score": city_score,
            "component_score": None,
            "provider": provider,
        }

    component_score = _address_component_score(addr, result)
    if (
        component_score is not None
        and component_score < ADDRESS_COMPONENT_MATCH_THRESHOLD
    ):
        return {
            "status": "mismatch",
            "reason": "address_component_mismatch",
            "query": query,
            "geocode": result,
            "city_score": city_score,
            "component_score": component_score,
            "provider": provider,
        }

    return {
        "status": "match",
        "reason": "matched",
        "query": query,
        "geocode": result,
        "city_score": city_score,
        "component_score": component_score,
        "provider": provider,
    }


def validate_address_online(addr: dict, geocode_fn=None) -> dict:
    """Validate an address online and classify the result.

    Status values:
        - match:     geocode result agrees with key fields
        - mismatch:  geocode result conflicts with key fields
        - no_result: geocoder returned no usable evidence
    """
    query = _build_geocode_query(addr)
    geocode_func = geocode_fn or geocode_address

    def accept_result(candidate: dict) -> bool:
        return _classify_geocode_result(addr, query, candidate)["status"] == "match"

    try:
        result = geocode_func(query, accept_result=accept_result)
    except TypeError:
        result = geocode_func(query)

    return _classify_geocode_result(addr, query, result)


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
