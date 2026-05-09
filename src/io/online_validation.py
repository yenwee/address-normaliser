"""Online geocoding adapters for address validation provider fallback.

Thread-safe with per-provider token-bucket rate limiting, 429 retry,
and daily quota tracking.
"""

from __future__ import annotations

import logging
import threading
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

MAX_RETRIES = 3
RETRY_BASE_SECONDS = 1.0

_PROVIDER_LIMITS = {
    "tomtom": {"rps": 5, "daily": 2500},
    "geoapify": {"rps": 5, "daily": 3000},
    "locationiq": {"rps": 2, "daily": 5000},
}


class _TokenBucket:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float, burst: int):
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
                self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            time.sleep(wait)


class _DailyQuota:
    """Thread-safe daily request counter."""

    def __init__(self, limit: int):
        self._limit = limit
        self._count = 0
        self._day = 0
        self._lock = threading.Lock()

    def try_consume(self) -> bool:
        with self._lock:
            today = int(time.time() // 86400)
            if today != self._day:
                self._day = today
                self._count = 0
            if self._count >= self._limit:
                return False
            self._count += 1
            return True

    @property
    def remaining(self) -> int:
        with self._lock:
            today = int(time.time() // 86400)
            if today != self._day:
                return self._limit
            return max(0, self._limit - self._count)


_buckets: dict[str, _TokenBucket] = {
    name: _TokenBucket(rate=cfg["rps"], burst=cfg["rps"])
    for name, cfg in _PROVIDER_LIMITS.items()
}

_quotas: dict[str, _DailyQuota] = {
    name: _DailyQuota(limit=cfg["daily"])
    for name, cfg in _PROVIDER_LIMITS.items()
}

_cache: dict[tuple[str, tuple[str, ...]], dict | None] = {}
_cache_lock = threading.Lock()


def _request_json_with_retry(
    url: str, params: dict | None, provider: str
) -> dict | list | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=ONLINE_VALIDATION_TIMEOUT_SECONDS,
                headers={"User-Agent": "address-normaliser/1.0 (falcon-field-partners)"},
            )
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", RETRY_BASE_SECONDS * (2 ** (attempt - 1))))
                logger.debug("429 from %s, retry %d after %.1fs", provider, attempt, retry_after)
                if attempt < MAX_RETRIES:
                    time.sleep(retry_after)
                    continue
                return None
            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            logger.debug("Request failed for %s (attempt %d): %s", provider, attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
                continue
            return None
    return None


def _provider_available(provider: str) -> bool:
    return _quotas[provider].remaining > 0


def geocode_tomtom(query: str) -> dict | None:
    if not TOMTOM_API_KEY or not _provider_available("tomtom"):
        return None

    _buckets["tomtom"].acquire()
    if not _quotas["tomtom"].try_consume():
        return None

    url = f"https://api.tomtom.com/search/2/geocode/{quote(query)}.json"
    payload = _request_json_with_retry(
        url,
        params={
            "key": TOMTOM_API_KEY,
            "countrySet": "MY",
            "limit": 1,
            "language": "en-GB",
        },
        provider="tomtom",
    )
    if not isinstance(payload, dict):
        return None

    results = payload.get("results", [])
    if not results:
        return None

    first = results[0]
    addr = first.get("address", {})
    city = addr.get("municipality") or addr.get("municipalitySubdivision") or ""
    formatted = addr.get("freeformAddress") or first.get("freeformAddress") or ""
    street = addr.get("streetName") or ""

    return {
        "provider": "tomtom",
        "postcode": str(addr.get("postalCode", "") or ""),
        "city": str(city),
        "state": str(addr.get("countrySubdivision", "") or ""),
        "formatted": str(formatted),
        "street": str(street),
    }


def geocode_geoapify(query: str) -> dict | None:
    if not GEOAPIFY_API_KEY or not _provider_available("geoapify"):
        return None

    _buckets["geoapify"].acquire()
    if not _quotas["geoapify"].try_consume():
        return None

    payload = _request_json_with_retry(
        "https://api.geoapify.com/v1/geocode/search",
        params={
            "text": query,
            "filter": "countrycode:my",
            "limit": 1,
            "apiKey": GEOAPIFY_API_KEY,
        },
        provider="geoapify",
    )
    if not isinstance(payload, dict):
        return None

    if payload.get("results"):
        first = payload["results"][0]
    elif payload.get("features"):
        first = payload["features"][0].get("properties", {})
    else:
        return None

    city = first.get("city") or first.get("town") or first.get("village") or ""

    return {
        "provider": "geoapify",
        "postcode": str(first.get("postcode", "") or ""),
        "city": str(city),
        "state": str(first.get("state", "") or ""),
        "formatted": str(first.get("formatted", "") or ""),
        "street": str(first.get("street", "") or ""),
        "area": str(first.get("suburb") or first.get("city_district") or first.get("district") or ""),
    }


def geocode_locationiq(query: str) -> dict | None:
    if not LOCATIONIQ_API_KEY or not _provider_available("locationiq"):
        return None

    _buckets["locationiq"].acquire()
    if not _quotas["locationiq"].try_consume():
        return None

    payload = _request_json_with_retry(
        "https://us1.locationiq.com/v1/search.php",
        params={
            "key": LOCATIONIQ_API_KEY,
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "countrycodes": "my",
            "limit": 1,
        },
        provider="locationiq",
    )
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
        "formatted": str(first.get("display_name", "") or ""),
        "street": str(addr.get("road") or addr.get("pedestrian") or ""),
        "area": str(addr.get("suburb") or addr.get("neighbourhood") or ""),
    }


def geocode_multi_provider(
    query: str,
    providers: tuple[str, ...] | None = None,
    accept_result=None,
) -> dict | None:
    provider_order = providers if providers is not None else ONLINE_VALIDATION_PROVIDERS

    cache_key = (query, tuple(provider_order))
    if accept_result is None:
        with _cache_lock:
            if cache_key in _cache:
                return _cache[cache_key]

    provider_map = {
        "tomtom": geocode_tomtom,
        "geoapify": geocode_geoapify,
        "locationiq": geocode_locationiq,
    }

    rejected_result = None
    for provider in provider_order:
        fn = provider_map.get(provider)
        if fn is None:
            continue

        result = fn(query)
        if result is not None:
            if accept_result is None or accept_result(result):
                if accept_result is None:
                    with _cache_lock:
                        _cache[cache_key] = result
                return result
            if rejected_result is None:
                rejected_result = result

    if accept_result is None:
        with _cache_lock:
            _cache[cache_key] = None
    return rejected_result
