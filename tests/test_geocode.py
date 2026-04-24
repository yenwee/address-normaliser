"""Tests for online validation helpers in geocode step."""

from unittest.mock import patch

from src.steps.geocode import CITY_MATCH_THRESHOLD, apply_geocode_fallback, validate_address_online


def _base_addr():
    return {
        "address_line": "NO 12 JALAN AMPANG",
        "address_line2": "TAMAN DAMAI",
        "address_line3": "",
        "postcode": "50450",
        "city": "KUALA LUMPUR",
        "state": "WP KUALA LUMPUR",
    }


class TestValidateAddressOnline:
    """Tests for validate_address_online classifier."""

    @patch("src.steps.geocode.geocode_address", return_value=None)
    def test_no_result_when_geocoder_returns_none(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "no_result"
        assert result["reason"] == "no_geocode_result"

    @patch("src.steps.geocode.geocode_address", return_value={"display_name": "Malaysia"})
    def test_no_result_when_geocoder_has_no_usable_fields(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "no_result"
        assert result["reason"] == "insufficient_geocode_fields"

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "50000",
            "city": "Kuala Lumpur",
            "state": "Wilayah Persekutuan Kuala Lumpur",
        },
    )
    def test_mismatch_on_postcode(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "mismatch"
        assert result["reason"] == "postcode_mismatch"

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "50450",
            "city": "Kuala Lumpur",
            "state": "Selangor",
        },
    )
    def test_mismatch_on_state(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "mismatch"
        assert result["reason"] == "state_mismatch"

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "",
            "city": "Batu Pahat",
            "state": "",
        },
    )
    def test_city_mismatch_when_no_core_signal(self, _mock_geocode):
        addr = _base_addr()
        addr["postcode"] = ""
        addr["state"] = ""
        result = validate_address_online(addr)
        assert result["status"] == "mismatch"
        assert result["reason"] == "city_mismatch"
        assert result["city_score"] < CITY_MATCH_THRESHOLD

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "50450",
            "city": "Batu Pahat",
            "state": "Wilayah Persekutuan Kuala Lumpur",
            "formatted": "NO 12 JALAN AMPANG, KUALA LUMPUR",
        },
    )
    def test_city_mismatch_ignored_when_postcode_or_state_matches(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "match"
        assert result["reason"] == "matched"
        assert result["city_score"] < CITY_MATCH_THRESHOLD

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "50450",
            "city": "Kuala Lumpur",
            "state": "Wilayah Persekutuan Kuala Lumpur",
            "formatted": "NO 12 JALAN AMPANG, KUALA LUMPUR",
        },
    )
    def test_match_when_core_fields_align(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "match"
        assert result["reason"] == "matched"

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "50450, 55000",
            "city": "Kuala Lumpur",
            "state": "Federal Territory of Kuala Lumpur",
            "formatted": "NO 12 JALAN AMPANG, KUALA LUMPUR",
        },
    )
    def test_match_when_provider_returns_multiple_postcodes_and_state_alias(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "match"
        assert result["reason"] == "matched"

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "50450",
            "city": "Kuala Lumpur",
            "state": "Wilayah Persekutuan Kuala Lumpur",
        },
    )
    def test_mismatch_when_provider_has_no_component_evidence(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "mismatch"
        assert result["reason"] == "address_component_unverified"

    @patch(
        "src.steps.geocode.geocode_address",
        return_value={
            "postcode": "50450",
            "city": "Kuala Lumpur",
            "state": "Wilayah Persekutuan Kuala Lumpur",
            "formatted": "JALAN RAJA CHULAN, KUALA LUMPUR",
        },
    )
    def test_mismatch_when_provider_component_conflicts(self, _mock_geocode):
        result = validate_address_online(_base_addr())
        assert result["status"] == "mismatch"
        assert result["reason"] == "address_component_mismatch"

    def test_multi_provider_continues_until_component_match(self):
        calls = []

        def fake_multi_provider(query, accept_result=None):
            candidates = [
                {
                    "provider": "tomtom",
                    "postcode": "50450",
                    "city": "Kuala Lumpur",
                    "state": "Wilayah Persekutuan Kuala Lumpur",
                },
                {
                    "provider": "geoapify",
                    "postcode": "50450",
                    "city": "Kuala Lumpur",
                    "state": "Wilayah Persekutuan Kuala Lumpur",
                    "formatted": "NO 12 JALAN AMPANG, KUALA LUMPUR",
                },
            ]
            for candidate in candidates:
                calls.append(candidate["provider"])
                if accept_result is None or accept_result(candidate):
                    return candidate
            return candidates[0]

        result = validate_address_online(_base_addr(), geocode_fn=fake_multi_provider)
        assert result["status"] == "match"
        assert result["provider"] == "geoapify"
        assert calls == ["tomtom", "geoapify"]

    @patch("src.steps.geocode.geocode_address", return_value=None)
    def test_query_is_single_line_for_geocoder(self, mock_geocode):
        validate_address_online(_base_addr())
        query = mock_geocode.call_args[0][0]
        assert "\n" not in query
        assert ", " in query
        assert "WP KUALA LUMPUR" not in query
        assert "WILAYAH PERSEKUTUAN KUALA LUMPUR" in query


class TestApplyGeocodeFallback:
    """Tests for apply_geocode_fallback query behavior."""

    @patch("src.steps.geocode.geocode_address", return_value=None)
    def test_fallback_uses_single_line_query(self, mock_geocode):
        apply_geocode_fallback(_base_addr())
        query = mock_geocode.call_args[0][0]
        assert "\n" not in query
