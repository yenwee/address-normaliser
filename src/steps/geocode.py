"""Optional Nominatim geocoding fallback for low-confidence addresses."""

from src.processing.formatter import format_mailing_block
from src.io.nominatim import geocode_address


def apply_geocode_fallback(addr: dict) -> dict:
    """Use Nominatim geocoding to fill missing fields on low-confidence addresses.

    Args:
        addr: The address dict to enrich.

    Returns:
        A copy of addr with any missing fields filled from geocode results.
    """
    query = format_mailing_block(addr)
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
