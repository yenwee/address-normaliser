"""Tests for address completeness scorer module."""

import pytest

from src.scorer import score_completeness


class TestScoreCompleteness:
    """Tests for score_completeness function."""

    def _make_addr(
        self,
        address_line="",
        address_line2="",
        address_line3="",
        postcode="",
        city="",
        state="",
    ):
        return {
            "address_line": address_line,
            "address_line2": address_line2,
            "address_line3": address_line3,
            "postcode": postcode,
            "city": city,
            "state": state,
            "raw": "",
            "source_column": "ADDR0",
        }

    def test_complete_address_high_score(self):
        """A complete Malaysian address should score >= 8."""
        addr = self._make_addr(
            address_line="NO 235 JALAN KERETAPI",
            address_line2="TAMAN SPRINGFIELD",
            postcode="93250",
            city="KUCHING",
            state="SARAWAK",
        )
        score = score_completeness(addr)
        assert score >= 8

    def test_minimal_address_low_score(self):
        """Just a place name with no postcode/city/state should score <= 2."""
        addr = self._make_addr(address_line="RUMAH PANJANG")
        score = score_completeness(addr)
        assert score <= 2

    def test_postcode_only_medium_score(self):
        """Address with only a postcode should score between 3 and 5."""
        addr = self._make_addr(postcode="50000")
        score = score_completeness(addr)
        assert 3 <= score <= 5

    def test_all_fields_populated_max_score(self):
        """Address with every scoring field populated should reach max score of 12."""
        addr = self._make_addr(
            address_line="NO 1 JALAN MAJU",
            address_line2="TAMAN SERI INDAH",
            postcode="50000",
            city="KUALA LUMPUR",
            state="W.P. KUALA LUMPUR",
        )
        score = score_completeness(addr)
        assert score == 12

    def test_empty_fields_reduce_score(self):
        """Removing fields from a complete address should reduce the score."""
        full = self._make_addr(
            address_line="NO 1 JALAN MAJU",
            address_line2="TAMAN SERI INDAH",
            postcode="50000",
            city="KUALA LUMPUR",
            state="W.P. KUALA LUMPUR",
        )
        no_postcode = self._make_addr(
            address_line="NO 1 JALAN MAJU",
            address_line2="TAMAN SERI INDAH",
            city="KUALA LUMPUR",
            state="W.P. KUALA LUMPUR",
        )
        no_city = self._make_addr(
            address_line="NO 1 JALAN MAJU",
            address_line2="TAMAN SERI INDAH",
            postcode="50000",
            state="W.P. KUALA LUMPUR",
        )
        assert score_completeness(full) > score_completeness(no_postcode)
        assert score_completeness(full) > score_completeness(no_city)

    def test_postcode_validation_rejects_invalid(self):
        """Non-5-digit postcodes should not earn postcode points."""
        addr_short = self._make_addr(postcode="1234")
        addr_long = self._make_addr(postcode="123456")
        addr_alpha = self._make_addr(postcode="ABCDE")
        for addr in [addr_short, addr_long, addr_alpha]:
            assert score_completeness(addr) == 0

    def test_postcode_validation_accepts_valid(self):
        """Valid 5-digit postcode should earn 3 points."""
        addr = self._make_addr(postcode="93250")
        assert score_completeness(addr) == 3

    def test_street_number_keywords(self):
        """Street number keywords (NO, LOT, UNIT, BLK, BLOK) earn 1 point."""
        for keyword in ["NO", "LOT", "UNIT", "BLK", "BLOK"]:
            addr = self._make_addr(address_line=f"{keyword} 123 SOMEWHERE")
            assert score_completeness(addr) >= 1

    def test_street_name_keywords(self):
        """Street name keywords earn 1 point."""
        for keyword in ["JALAN", "LORONG", "PERSIARAN", "LEBUH", "LINTANG", "LENGKOK"]:
            addr = self._make_addr(address_line=f"NO 1 {keyword} UTAMA")
            # NO contributes street number (+1), keyword contributes street name (+1)
            assert score_completeness(addr) >= 2

    def test_area_keywords(self):
        """Area keywords earn 1 point."""
        for keyword in ["TAMAN", "KAMPUNG", "BANDAR", "DESA", "PANGSAPURI", "FLAT", "APARTMENT"]:
            addr = self._make_addr(address_line=f"{keyword} SERI")
            assert score_completeness(addr) >= 1

    def test_case_insensitive_keyword_match(self):
        """Keywords should match case-insensitively."""
        addr = self._make_addr(address_line="no 1 jalan maju taman indah")
        # Should match: street number (no), street name (jalan), area (taman)
        assert score_completeness(addr) >= 3

    def test_address_line2_contributes_to_keyword_search(self):
        """Keywords in address_line2 should also be detected."""
        addr = self._make_addr(
            address_line="SOMEWHERE",
            address_line2="TAMAN SERI",
        )
        # TAMAN in address_line2 should count for area keyword (+1)
        # address_line2 non-empty (+1)
        assert score_completeness(addr) >= 2

    def test_non_empty_address_line2_bonus(self):
        """Non-empty address_line2 should earn 1 point."""
        without = self._make_addr(address_line="NO 1 JALAN MAJU")
        with_line2 = self._make_addr(
            address_line="NO 1 JALAN MAJU",
            address_line2="SUITE 5",
        )
        assert score_completeness(with_line2) == score_completeness(without) + 1

    def test_word_boundary_matching(self):
        """Keywords should match on word boundaries, not substrings."""
        #ANOL should not match NO; JALANG should not match JALAN
        addr_no_match = self._make_addr(address_line="ANOL JALANG FLATBED")
        assert score_completeness(addr_no_match) == 0

    def test_returns_integer(self):
        """Score should always be an integer."""
        addr = self._make_addr(
            address_line="NO 1 JALAN MAJU",
            postcode="50000",
            city="KL",
            state="WP",
        )
        score = score_completeness(addr)
        assert isinstance(score, int)

    def test_all_empty_fields_zero_score(self):
        """Completely empty address should score 0."""
        addr = self._make_addr()
        assert score_completeness(addr) == 0
