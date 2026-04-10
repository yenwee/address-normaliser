"""Tests for Nominatim geocoding fallback module."""

import time
from unittest.mock import patch, MagicMock

import pytest
import requests

from src.nominatim import geocode_address


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


class TestGeocodeAddress:
    """Tests for geocode_address function."""

    def _make_nominatim_response(self):
        """Build a mock Nominatim JSON response."""
        return [
            {
                "display_name": "Jalan Ampang, Kuala Lumpur, 50450, Malaysia",
                "importance": 0.65,
                "address": {
                    "road": "Jalan Ampang",
                    "suburb": "Kampung Baru",
                    "city": "Kuala Lumpur",
                    "state": "Wilayah Persekutuan Kuala Lumpur",
                    "postcode": "50450",
                    "country": "Malaysia",
                    "country_code": "my",
                },
            }
        ]

    @patch("src.nominatim.requests.get")
    def test_successful_geocode_returns_structured_result(self, mock_get):
        """Successful geocode returns dict with expected keys and values."""
        mock_response = MagicMock()
        mock_response.json.return_value = self._make_nominatim_response()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Jalan Ampang, Kuala Lumpur")

        assert result is not None
        assert result["display_name"] == "Jalan Ampang, Kuala Lumpur, 50450, Malaysia"
        assert result["road"] == "Jalan Ampang"
        assert result["suburb"] == "Kampung Baru"
        assert result["city"] == "Kuala Lumpur"
        assert result["state"] == "Wilayah Persekutuan Kuala Lumpur"
        assert result["postcode"] == "50450"
        assert result["importance"] == 0.65

        mock_get.assert_called_once_with(
            NOMINATIM_URL,
            params={
                "q": "Jalan Ampang, Kuala Lumpur",
                "format": "jsonv2",
                "addressdetails": 1,
                "countrycodes": "my",
                "limit": 1,
            },
            headers={"User-Agent": "address-normaliser/1.0 (falcon-field-partners)"},
            timeout=10,
        )

    @patch("src.nominatim.requests.get")
    def test_city_falls_back_to_town(self, mock_get):
        """When address has town but not city, city field uses town."""
        data = self._make_nominatim_response()
        del data[0]["address"]["city"]
        data[0]["address"]["town"] = "Batu Pahat"

        mock_response = MagicMock()
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Batu Pahat")
        assert result["city"] == "Batu Pahat"

    @patch("src.nominatim.requests.get")
    def test_city_falls_back_to_village(self, mock_get):
        """When address has village but not city/town, city field uses village."""
        data = self._make_nominatim_response()
        del data[0]["address"]["city"]
        data[0]["address"]["village"] = "Kampung Melayu"

        mock_response = MagicMock()
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Kampung Melayu")
        assert result["city"] == "Kampung Melayu"

    @patch("src.nominatim.requests.get")
    def test_empty_results_returns_none(self, mock_get):
        """Empty result list from Nominatim returns None."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("nonexistent address xyz")
        assert result is None

    @patch("src.nominatim.requests.get")
    def test_network_error_returns_none(self, mock_get):
        """RequestException during geocode returns None."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        result = geocode_address("Jalan Ampang")
        assert result is None

    @patch("src.nominatim.requests.get")
    def test_timeout_error_returns_none(self, mock_get):
        """Timeout during geocode returns None."""
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        result = geocode_address("Jalan Ampang")
        assert result is None

    @patch("src.nominatim.requests.get")
    def test_malformed_json_returns_none(self, mock_get):
        """ValueError from malformed JSON returns None."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Jalan Ampang")
        assert result is None

    @patch("src.nominatim.requests.get")
    def test_missing_address_fields_default_to_empty_string(self, mock_get):
        """Missing optional address fields default to empty string."""
        data = [
            {
                "display_name": "Some Place, Malaysia",
                "importance": 0.3,
                "address": {
                    "country": "Malaysia",
                    "country_code": "my",
                },
            }
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = data
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = geocode_address("Some Place")
        assert result is not None
        assert result["road"] == ""
        assert result["suburb"] == ""
        assert result["city"] == ""
        assert result["state"] == ""
        assert result["postcode"] == ""

    @patch("src.nominatim.time.time")
    @patch("src.nominatim.time.sleep")
    @patch("src.nominatim.requests.get")
    def test_rate_limiting_enforced(self, mock_get, mock_sleep, mock_time):
        """Second call within 1 second triggers sleep for rate limiting."""
        import src.nominatim as nominatim_mod

        nominatim_mod._last_request_time = 100.0
        mock_time.return_value = 100.5

        mock_response = MagicMock()
        mock_response.json.return_value = self._make_nominatim_response()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        geocode_address("Jalan Ampang")

        mock_sleep.assert_called_once()
        sleep_duration = mock_sleep.call_args[0][0]
        assert 0.4 < sleep_duration < 0.6
