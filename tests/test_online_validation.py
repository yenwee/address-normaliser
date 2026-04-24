"""Tests for online geocoding provider adapters."""

from unittest.mock import MagicMock, patch

import src.io.online_validation as ov


class TestProviderParsers:
    """Provider response mapping tests."""

    @patch("src.io.online_validation.requests.get")
    def test_tomtom_mapping(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "results": [
                {
                    "address": {
                        "postalCode": "50450",
                        "municipality": "Kuala Lumpur",
                        "countrySubdivision": "Wilayah Persekutuan Kuala Lumpur",
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        with patch.object(ov, "TOMTOM_API_KEY", "tomtom-key"):
            result = ov.geocode_tomtom("Jalan Ampang, Kuala Lumpur")

        assert result is not None
        assert result["provider"] == "tomtom"
        assert result["postcode"] == "50450"
        assert result["city"] == "Kuala Lumpur"
        assert result["state"] == "Wilayah Persekutuan Kuala Lumpur"

    @patch("src.io.online_validation.requests.get")
    def test_geoapify_results_mapping(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "results": [
                {
                    "postcode": "81100",
                    "city": "Johor Bahru",
                    "state": "Johor",
                }
            ]
        }
        mock_get.return_value = mock_response

        with patch.object(ov, "GEOAPIFY_API_KEY", "geo-key"):
            result = ov.geocode_geoapify("Johor Bahru")

        assert result is not None
        assert result["provider"] == "geoapify"
        assert result["postcode"] == "81100"
        assert result["city"] == "Johor Bahru"
        assert result["state"] == "Johor"

    @patch("src.io.online_validation.requests.get")
    def test_geoapify_feature_collection_mapping(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {
                        "postcode": "50450",
                        "city": "Kuala Lumpur",
                        "state": "Federal Territory of Kuala Lumpur",
                    }
                }
            ],
        }
        mock_get.return_value = mock_response

        with patch.object(ov, "GEOAPIFY_API_KEY", "geo-key"):
            result = ov.geocode_geoapify("Kuala Lumpur")

        assert result is not None
        assert result["provider"] == "geoapify"
        assert result["postcode"] == "50450"
        assert result["city"] == "Kuala Lumpur"
        assert result["state"] == "Federal Territory of Kuala Lumpur"

    @patch("src.io.online_validation.requests.get")
    def test_locationiq_mapping(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {
                "address": {
                    "postcode": "43000",
                    "town": "Kajang",
                    "state": "Selangor",
                }
            }
        ]
        mock_get.return_value = mock_response

        with patch.object(ov, "LOCATIONIQ_API_KEY", "loc-key"):
            result = ov.geocode_locationiq("Kajang")

        assert result is not None
        assert result["provider"] == "locationiq"
        assert result["postcode"] == "43000"
        assert result["city"] == "Kajang"
        assert result["state"] == "Selangor"


class TestMultiProviderFallback:
    """Fallback sequencing tests."""

    def test_tries_next_provider_on_none(self):
        with patch.object(ov, "geocode_tomtom", return_value=None), patch.object(
            ov, "geocode_geoapify", return_value={"provider": "geoapify", "postcode": "50000", "city": "Kuala Lumpur", "state": "Wilayah Persekutuan Kuala Lumpur"}
        ), patch.object(ov, "geocode_locationiq", return_value=None):
            result = ov.geocode_multi_provider("Kuala Lumpur", providers=("tomtom", "geoapify", "locationiq"))

        assert result is not None
        assert result["provider"] == "geoapify"
