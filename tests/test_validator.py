"""Tests for postcode validator module."""

import pytest

from src.validator import PostcodeValidator, POSTCODE_STATE_PREFIXES


POSTCODES_PATH = "data/postcodes.json"


@pytest.fixture(scope="module")
def validator():
    return PostcodeValidator(POSTCODES_PATH)


class TestPostcodeStatePrefixes:
    """Tests for the POSTCODE_STATE_PREFIXES mapping."""

    def test_perlis_prefixes(self):
        assert POSTCODE_STATE_PREFIXES["01"] == "PERLIS"
        assert POSTCODE_STATE_PREFIXES["02"] == "PERLIS"

    def test_kedah_prefixes(self):
        assert POSTCODE_STATE_PREFIXES["05"] == "KEDAH"
        assert POSTCODE_STATE_PREFIXES["06"] == "KEDAH"
        assert POSTCODE_STATE_PREFIXES["08"] == "KEDAH"
        assert POSTCODE_STATE_PREFIXES["09"] == "KEDAH"

    def test_pulau_pinang_prefixes(self):
        for p in ["10", "11", "12", "13", "14"]:
            assert POSTCODE_STATE_PREFIXES[p] == "PULAU PINANG"

    def test_kl_prefixes(self):
        for p in ["50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60"]:
            assert POSTCODE_STATE_PREFIXES[p] == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_putrajaya_prefix(self):
        assert POSTCODE_STATE_PREFIXES["62"] == "WILAYAH PERSEKUTUAN PUTRAJAYA"

    def test_selangor_extended_prefixes(self):
        for p in ["63", "64", "68", "69"]:
            assert POSTCODE_STATE_PREFIXES[p] == "SELANGOR"
        for p in ["40", "41", "42", "43", "44", "45", "46", "47", "48"]:
            assert POSTCODE_STATE_PREFIXES[p] == "SELANGOR"

    def test_labuan_prefix(self):
        assert POSTCODE_STATE_PREFIXES["87"] == "WILAYAH PERSEKUTUAN LABUAN"

    def test_sabah_prefixes(self):
        for p in ["88", "89", "90", "91"]:
            assert POSTCODE_STATE_PREFIXES[p] == "SABAH"

    def test_sarawak_prefixes(self):
        for p in ["93", "94", "95", "96", "97", "98"]:
            assert POSTCODE_STATE_PREFIXES[p] == "SARAWAK"


class TestPostcodeValidatorInit:
    """Tests for PostcodeValidator initialisation."""

    def test_loads_postcodes(self, validator):
        """Validator should load postcodes and build lookup."""
        result = validator.validate("50000", "Kuala Lumpur", "Wp Kuala Lumpur")
        assert result["valid"] is True

    def test_lookup_uppercased(self, validator):
        """All names in lookup should be uppercased."""
        result = validator.validate("50000", "", "")
        assert result["suggested_city"] == "KUALA LUMPUR"
        assert result["suggested_state"] == "WP KUALA LUMPUR"


class TestValidate:
    """Tests for PostcodeValidator.validate method."""

    def test_valid_postcode_city_state(self, validator):
        """Valid combination should return valid=True with suggestions matching DB."""
        result = validator.validate("50000", "Kuala Lumpur", "Wp Kuala Lumpur")
        assert result["valid"] is True
        assert result["suggested_postcode"] == "50000"
        assert result["suggested_city"] == "KUALA LUMPUR"
        assert result["suggested_state"] == "WP KUALA LUMPUR"

    def test_wrong_state_for_postcode(self, validator):
        """Wrong state should return valid=False and suggest the correct state."""
        result = validator.validate("50000", "Kuala Lumpur", "Selangor")
        assert result["valid"] is False
        assert result["suggested_state"] == "WP KUALA LUMPUR"

    def test_missing_state_fills_suggestion(self, validator):
        """Missing state should still be valid and fill in the suggested state."""
        result = validator.validate("50000", "Kuala Lumpur", "")
        assert result["valid"] is True
        assert result["suggested_state"] == "WP KUALA LUMPUR"

    def test_missing_city_fills_suggestion(self, validator):
        """Missing city should still fill in the suggested city from DB."""
        result = validator.validate("50000", "", "Wp Kuala Lumpur")
        assert result["valid"] is True
        assert result["suggested_city"] == "KUALA LUMPUR"

    def test_unknown_postcode(self, validator):
        """Postcode not in DB should return valid=False."""
        result = validator.validate("99999", "Somewhere", "Somestate")
        assert result["valid"] is False

    def test_unknown_postcode_with_valid_prefix(self, validator):
        """Unknown postcode with a valid prefix should suggest state from prefix."""
        result = validator.validate("50999", "", "")
        assert result["valid"] is False
        assert result["suggested_state"] == "WILAYAH PERSEKUTUAN KUALA LUMPUR"
        assert result["suggested_postcode"] == "50999"

    def test_state_from_postcode_prefix_fallback(self, validator):
        """When postcode not in DB, use prefix to suggest state."""
        result = validator.validate("02999", "", "")
        assert result["valid"] is False
        assert result["suggested_state"] == "PERLIS"

    def test_missing_state_not_wrong(self, validator):
        """Empty state should not be considered a mismatch."""
        result = validator.validate("50000", "Kuala Lumpur", "")
        assert result["valid"] is True

    def test_none_state_not_wrong(self, validator):
        """None state should not be considered a mismatch."""
        result = validator.validate("50000", "Kuala Lumpur", None)
        assert result["valid"] is True

    def test_fuzzy_state_match(self, validator):
        """State that fuzzy-matches above threshold should be valid."""
        result = validator.validate("50000", "Kuala Lumpur", "WP Kuala Lumpur")
        assert result["valid"] is True

    def test_completely_wrong_prefix(self, validator):
        """Postcode with invalid prefix should return valid=False with empty suggestions."""
        result = validator.validate("00123", "", "")
        assert result["valid"] is False
        assert result["suggested_state"] == ""


class TestCorrectAddress:
    """Tests for PostcodeValidator.correct_address method."""

    def test_corrects_state(self, validator):
        """Should correct the state in the address dict."""
        addr = {"postcode": "50000", "city": "Kuala Lumpur", "state": "Selangor"}
        corrected, result = validator.correct_address(addr)
        assert corrected["state"] == "WP KUALA LUMPUR"
        assert result["valid"] is False

    def test_fills_missing_city(self, validator):
        """Should fill in missing city."""
        addr = {"postcode": "50000", "city": "", "state": "Wp Kuala Lumpur"}
        corrected, result = validator.correct_address(addr)
        assert corrected["city"] == "KUALA LUMPUR"

    def test_does_not_mutate_original(self, validator):
        """Should not mutate the original address dict."""
        addr = {"postcode": "50000", "city": "Kuala Lumpur", "state": "Selangor"}
        corrected, _ = validator.correct_address(addr)
        assert addr["state"] == "Selangor"
        assert corrected["state"] == "WP KUALA LUMPUR"

    def test_preserves_extra_fields(self, validator):
        """Should preserve fields not related to validation."""
        addr = {
            "postcode": "50000",
            "city": "Kuala Lumpur",
            "state": "Wp Kuala Lumpur",
            "line1": "123 Jalan Maju",
        }
        corrected, _ = validator.correct_address(addr)
        assert corrected["line1"] == "123 Jalan Maju"
