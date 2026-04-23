"""Online geocoding adapters for address validation provider fallback."""

from __future__ import annotations

import logging
import time
from urllib.parse import quote

import requests

from src.config import (
    GEOAPIFY_API_KEY,
    LOCATIONIQ_API_KEY,
    ONLINE_VALIDATION_PROVIDERS,
    ONLINE_VALIDATION_TIMEOUT_SECONDS,
    TOMTOM_API_KEY,
)

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, tuple[str, ...]], dict | None] = {}
_last_request_time: dict[str, float] = {
    "tomtom": 0.0,
    "geoapify": 0.0,
    "locationiq": 0.0,
}

_MIN_INTERVAL_SECONDS = {
    "tomtom": 0.05,
    "geoapify": 0.05,
    "locationiq": 0.5,  # Free tier limit is 2 req/sec.
}


def _rate_limit(provider: str) -> None:
    min_interval = _MIN_INTERVAL_SECONDS.get(provider, 0.1)
    elapsed = time.time() - _last_request_time.get(provider, 0.0)
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)


def _request_json(url: str, params: dict | None = None) -> dict | list | None:
    try:
        response = requests.get(
            url,
            params=params,
            timeout=ONLINE_VALIDATION_TIMEOUT_SECONDS,
            headers={"User-Agent": "address-normaliser/1.0 (falcon-field-partners)"},
        )
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.RequestException, ValueError) as exc:
        logger.debug("Online validation request failed for %s: %s", url, exc)
        return None


def geocode_tomtom(query: str) -> dict | None:
    """Geocode via TomTom Search API."""
    if not TOMTOM_API_KEY:
        return None

    _rate_limit("tomtom")
    url = f"https://api.tomtom.com/search/2/geocode/{quote(query)}.json"
    payload = _request_json(
        url,
        params={
            "key": TOMTOM_API_KEY,
            "countrySet": "MY",
            "limit": 1,
            "language": "en-GB",
        },
    )
    _last_request_time["tomtom"] = time.time()
    if not isinstance(payload, dict):
        return None

    results = payload.get("results", [])
    if not results:
        return None

    first = results[0]
    addr = first.get("address", {})
    city = addr.get("municipality") or addr.get("municipalitySubdivision") or ""

    return {
        "provider": "tomtom",
        "postcode": str(addr.get("postalCode", "") or ""),
        "city": str(city),
        "state": str(addr.get("countrySubdivision", "") or ""),
    }


def geocode_geoapify(query: str) -> dict | None:
    """Geocode via Geoapify Forward Geocoding API."""
    if not GEOAPIFY_API_KEY:
        return None

    _rate_limit("geoapify")
    payload = _request_json(
        "https://api.geoapify.com/v1/geocode/search",
        params={
            "text": query,
            "filter": "countrycode:my",
            "limit": 1,
            "apiKey": GEOAPIFY_API_KEY,
        },
    )
    _last_request_time["geoapify"] = time.time()
    if not isinstance(payload, dict):
        return None

    results = payload.get("results", [])
    if not results:
        return None

    first = results[0]
    city = first.get("city") or first.get("town") or first.get("village") or ""

    return {
        "provider": "geoapify",
        "postcode": str(first.get("postcode", "") or ""),
        "city": str(city),
        "state": str(first.get("state", "") or ""),
    }


def geocode_locationiq(query: str) -> dict | None:
    """Geocode via LocationIQ Search API."""
    if not LOCATIONIQ_API_KEY:
        return None

    _rate_limit("locationiq")
    payload = _request_json(
        "https://us1.locationiq.com/v1/search.php",
        params={
            "key": LOCATIONIQ_API_KEY,
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "countrycodes": "my",
            "limit": 1,
        },
    )
    _last_request_time["locationiq"] = time.time()
    if not isinstance(payload, list) or not payload:
        return None

    first = payload[0]
    addr = first.get("address", {})
    city = addr.get("city") or addr.get("town") or addr.get("village") or ""

    return {
        "provider": "locationiq",
        "postcode": str(addr.get("postcode", "") or ""),
        "city": str(city),
        "state": str(addr.get("state", "") or ""),
    }


def geocode_multi_provider(query: str, providers: tuple[str, ...] | None = None) -> dict | None:
    """Try online geocoding providers in order until first successful result."""
    provider_order = providers if providers is not None else ONLINE_VALIDATION_PROVIDERS
    cache_key = (query, tuple(provider_order))
    if cache_key in _cache:
        return _cache[cache_key]

    provider_map = {
        "tomtom": geocode_tomtom,
        "geoapify": geocode_geoapify,
        "locationiq": geocode_locationiq,
    }

    for provider in provider_order:
        fn = provider_map.get(provider)
        if fn is None:
            continue

        result = fn(query)
        if result is not None:
            _cache[cache_key] = result
            return result

    _cache[cache_key] = None
    return None
