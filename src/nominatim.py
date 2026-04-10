"""Nominatim geocoding fallback for low-confidence Malaysian addresses.

Uses OpenStreetMap's Nominatim API to validate and enrich address data.
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "address-normaliser/1.0 (falcon-field-partners)"
REQUEST_TIMEOUT = 10
RATE_LIMIT_SECONDS = 1.0

_last_request_time = 0.0


def geocode_address(query: str) -> dict | None:
    """Geocode a Malaysian address using Nominatim.

    Args:
        query: Address string to geocode.

    Returns:
        Structured result dict with address components, or None on error.
    """
    global _last_request_time

    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)

    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "countrycodes": "my",
                "limit": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        _last_request_time = time.time()

        results = response.json()
        if not results:
            return None

        first = results[0]
        address = first.get("address", {})

        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or ""
        )

        return {
            "display_name": first.get("display_name", ""),
            "road": address.get("road", ""),
            "suburb": address.get("suburb", ""),
            "city": city,
            "state": address.get("state", ""),
            "postcode": address.get("postcode", ""),
            "importance": float(first.get("importance", 0.0)),
        }

    except (requests.exceptions.RequestException, ValueError) as exc:
        logger.debug("Nominatim geocode failed for %r: %s", query, exc)
        return None
