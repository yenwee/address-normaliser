"""Tests for address parser module."""

import pandas as pd
import pytest

from src.parser import parse_address, parse_all_addresses


class TestParseAddress:
    """Tests for parse_address function."""

    def test_standard_7_field_address(self):
        """Standard 7-field format with postcode at position 3."""
        raw = "NO 235 LRG 5 JALAN KERETAPI, TAMAN SPRINGFIELD, , 93250, KUCHING, SARAWAK, "
        result = parse_address(raw)

        assert result is not None
        assert result["address_line"] == "NO 235 LRG 5 JALAN KERETAPI"
        assert result["address_line2"] == "TAMAN SPRINGFIELD"
        assert result["address_line3"] == ""
        assert result["postcode"] == "93250"
        assert result["city"] == "KUCHING"
        assert result["state"] == "SARAWAK"
        assert result["raw"] == raw

    def test_standard_7_field_wp_kuala_lumpur(self):
        """Standard 7-field with W.P. KUALA LUMPUR as state."""
        raw = "NO 6A   JALAN 2/12A, KG BATU MUDA, , 51100, , W.P. KUALA LUMPUR, "
        result = parse_address(raw)

        assert result is not None
        assert result["address_line"] == "NO 6A JALAN 2/12A"
        assert result["address_line2"] == "KG BATU MUDA"
        assert result["postcode"] == "51100"
        assert result["city"] == ""
        assert result["state"] == "W.P. KUALA LUMPUR"

    def test_8_field_record(self):
        """8-field record with extra field before postcode."""
        raw = "LOT 265,   Batu, TAMAN PASAR PUTIH PHASE 1, , 88100, KOTA KINABALU, SABAH, "
        result = parse_address(raw)

        assert result is not None
        assert result["postcode"] == "88100"
        assert result["city"] == "KOTA KINABALU"
        assert result["state"] == "SABAH"
        assert "LOT 265" in result["address_line"]

    def test_city_state_swap_detection(self):
        """When city and state fields are swapped, parser should correct them."""
        raw = "NO 10 JALAN MAJU, TAMAN SERI, , 40000, SELANGOR, SHAH ALAM, "
        result = parse_address(raw)

        assert result is not None
        assert result["postcode"] == "40000"
        assert result["state"] == "SELANGOR"
        assert result["city"] == "SHAH ALAM"

    def test_null_field_handling(self):
        """NULL strings should be treated as empty."""
        raw = "NO 55 BATU 8 JALAN TRONG CHANGKAT JERING, NULL, , 34850, CHANGKAT JERING, PERAK, "
        result = parse_address(raw)

        assert result is not None
        assert result["address_line"] == "NO 55 BATU 8 JALAN TRONG CHANGKAT JERING"
        assert result["address_line2"] == ""
        assert result["postcode"] == "34850"
        assert result["city"] == "CHANGKAT JERING"
        assert result["state"] == "PERAK"

    def test_empty_address_returns_none(self):
        """Fully empty address should return None."""
        raw = ", , , , , , "
        result = parse_address(raw)
        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        assert parse_address("") is None

    def test_none_input_returns_none(self):
        """None input should return None."""
        assert parse_address(None) is None

    def test_junk_phone_number_returns_none(self):
        """Address containing only phone/IC number should return None."""
        raw = ", , 60168240208, , , , "
        result = parse_address(raw)
        assert result is None

    def test_junk_ic_number_returns_none(self):
        """Address with IC number as the only content should return None."""
        raw = ", , 890512105234, , , , "
        result = parse_address(raw)
        assert result is None

    def test_postcode_embedded_in_address_line(self):
        """When postcode is in the address text, not its own field."""
        raw = "LORONG 5 -LOT 265 TAMAN PARK  PUTIH PUTA   88100 KOTA KINABALU, , , , , , "
        result = parse_address(raw)

        assert result is not None
        assert result["postcode"] == "88100"

    def test_whitespace_normalization(self):
        """Multiple spaces should be collapsed to single space."""
        raw = "NO 6A   JALAN 2/12A, KG BATU MUDA, , 51100, , W.P. KUALA LUMPUR, "
        result = parse_address(raw)
        assert "  " not in result["address_line"]

    def test_all_output_keys_present(self):
        """Result dict should have all required keys."""
        raw = "NO 1 JALAN 1, TAMAN A, , 50000, KL, SELANGOR, "
        result = parse_address(raw)

        expected_keys = {"address_line", "address_line2", "address_line3", "postcode", "city", "state", "raw"}
        assert result is not None
        assert set(result.keys()) == expected_keys

    def test_state_in_city_position_detected(self):
        """State name appearing in city position should be moved to state."""
        raw = "NO 1 JALAN A, TAMAN B, , 31000, PERAK, IPOH, "
        result = parse_address(raw)

        assert result is not None
        assert result["state"] == "PERAK"
        assert result["city"] == "IPOH"

    def test_nan_input_returns_none(self):
        """NaN (float) input should return None."""
        import math
        assert parse_address(float("nan")) is None

    def test_address_with_only_postcode_fields(self):
        """Address with just a postcode and nothing else meaningful."""
        raw = ", , , 50000, , , "
        result = parse_address(raw)

        assert result is not None
        assert result["postcode"] == "50000"


class TestParseAllAddresses:
    """Tests for parse_all_addresses function."""

    def test_parse_row_with_multiple_addr_columns(self):
        """Parse a pandas Series row with multiple ADDR columns."""
        row = pd.Series({
            "ICNO": "900101010001",
            "NAME": "ALI BIN ABU",
            "ADDR0": "NO 1 JALAN 1, TAMAN A, , 50000, KUALA LUMPUR, W.P. KUALA LUMPUR, ",
            "ADDR1": ", , , , , , ",
            "ADDR2": "NO 2 JALAN 2, TAMAN B, , 40000, SHAH ALAM, SELANGOR, ",
        })
        addr_columns = ["ADDR0", "ADDR1", "ADDR2"]
        results = parse_all_addresses(row, addr_columns)

        assert len(results) == 2
        assert results[0]["source_column"] == "ADDR0"
        assert results[0]["postcode"] == "50000"
        assert results[1]["source_column"] == "ADDR2"
        assert results[1]["postcode"] == "40000"

    def test_parse_row_with_all_empty(self):
        """Row where all ADDR columns are empty."""
        row = pd.Series({
            "ICNO": "900101010001",
            "ADDR0": ", , , , , , ",
            "ADDR1": ", , , , , , ",
        })
        addr_columns = ["ADDR0", "ADDR1"]
        results = parse_all_addresses(row, addr_columns)

        assert len(results) == 0

    def test_parse_row_with_nan_values(self):
        """Row where some ADDR columns contain NaN."""
        row = pd.Series({
            "ICNO": "900101010001",
            "ADDR0": "NO 1 JALAN 1, TAMAN A, , 50000, KUALA LUMPUR, W.P. KUALA LUMPUR, ",
            "ADDR1": float("nan"),
        })
        addr_columns = ["ADDR0", "ADDR1"]
        results = parse_all_addresses(row, addr_columns)

        assert len(results) == 1
        assert results[0]["source_column"] == "ADDR0"

    def test_source_column_key_present(self):
        """Each result should include source_column key."""
        row = pd.Series({
            "ADDR5": "NO 1 JALAN 1, TAMAN A, , 50000, KUALA LUMPUR, W.P. KUALA LUMPUR, ",
        })
        addr_columns = ["ADDR5"]
        results = parse_all_addresses(row, addr_columns)

        assert len(results) == 1
        assert results[0]["source_column"] == "ADDR5"
        assert "source_column" not in parse_address(row["ADDR5"])

    def test_missing_column_skipped(self):
        """If a column is listed but not in the row, skip it."""
        row = pd.Series({
            "ADDR0": "NO 1 JALAN 1, TAMAN A, , 50000, KUALA LUMPUR, W.P. KUALA LUMPUR, ",
        })
        addr_columns = ["ADDR0", "ADDR1"]
        results = parse_all_addresses(row, addr_columns)

        assert len(results) == 1
