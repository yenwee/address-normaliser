"""Tests for address clusterer module."""

import pytest

from src.processing.clusterer import cluster_addresses, _address_text, _similarity


def _make_addr(address_line="", address_line2="", address_line3="",
               postcode="", city="", state="", raw="", source_column=""):
    """Helper to build address dicts for testing."""
    return {
        "address_line": address_line,
        "address_line2": address_line2,
        "address_line3": address_line3,
        "postcode": postcode,
        "city": city,
        "state": state,
        "raw": raw,
        "source_column": source_column,
    }


class TestAddressText:
    """Tests for _address_text helper."""

    def test_combines_address_fields_and_postcode(self):
        addr = _make_addr(
            address_line="NO 235 LRG 5 JALAN KERETAPI",
            address_line2="TAMAN SPRINGFIELD",
            postcode="93250",
        )
        result = _address_text(addr)
        assert result == "NO 235 LRG 5 JALAN KERETAPI TAMAN SPRINGFIELD 93250"

    def test_skips_empty_parts(self):
        addr = _make_addr(address_line="NO 1 JALAN 1", postcode="50000")
        result = _address_text(addr)
        assert result == "NO 1 JALAN 1 50000"

    def test_uppercases_output(self):
        addr = _make_addr(address_line="no 1 jalan 1", postcode="50000")
        result = _address_text(addr)
        assert result == "NO 1 JALAN 1 50000"

    def test_all_empty_returns_empty_string(self):
        addr = _make_addr()
        result = _address_text(addr)
        assert result == ""


class TestSimilarity:
    """Tests for _similarity helper."""

    def test_identical_addresses_score_100(self):
        a = _make_addr(address_line="NO 235 LORONG 5 JALAN KERETAPI",
                       address_line2="TAMAN SPRINGFIELD", postcode="93250")
        score = _similarity(a, a)
        assert score == 100.0

    def test_reordered_words_high_similarity(self):
        a = _make_addr(address_line="NO 235 LORONG 5 JALAN KERETAPI",
                       address_line2="TAMAN SPRINGFIELD", postcode="93250")
        b = _make_addr(address_line="NO 235 LORONG 5 TAMAN SPRINGFIELD",
                       address_line2="JALAN KERETAPI", postcode="93250")
        score = _similarity(a, b)
        assert score >= 80

    def test_completely_different_addresses_low_similarity(self):
        a = _make_addr(address_line="NO 235 LORONG 5 JALAN KERETAPI",
                       address_line2="KUCHING", postcode="93250")
        b = _make_addr(address_line="NO 6A JALAN 2/12A",
                       address_line2="KAMPUNG BATU MUDA KUALA LUMPUR",
                       postcode="51100")
        score = _similarity(a, b)
        assert score < 65


class TestClusterAddresses:
    """Tests for cluster_addresses function."""

    def test_empty_input_returns_empty_list(self):
        result = cluster_addresses([])
        assert result == []

    def test_single_address_returns_one_cluster(self):
        addr = _make_addr(address_line="NO 1 JALAN 1", postcode="50000")
        result = cluster_addresses([addr])
        assert len(result) == 1
        assert len(result[0]) == 1
        assert result[0][0] is addr

    def test_similar_variants_cluster_together(self):
        """Same address with slight word reordering should cluster."""
        a = _make_addr(
            address_line="NO 235 LORONG 5 JALAN KERETAPI",
            address_line2="TAMAN SPRINGFIELD",
            postcode="93250",
            raw="NO 235 LORONG 5 JALAN KERETAPI, TAMAN SPRINGFIELD, , 93250, KUCHING, SARAWAK, ",
            source_column="ADDR0",
        )
        b = _make_addr(
            address_line="NO 235 LORONG 5 TAMAN SPRINGFIELD",
            address_line2="JALAN KERETAPI",
            postcode="93250",
            raw="NO 235 LORONG 5 TAMAN SPRINGFIELD, JALAN KERETAPI, , 93250, KUCHING, SARAWAK, ",
            source_column="ADDR1",
        )
        result = cluster_addresses([a, b])
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_different_addresses_separate_clusters(self):
        """Completely different addresses should be in separate clusters."""
        a = _make_addr(
            address_line="NO 235 LORONG 5 JALAN KERETAPI",
            address_line2="KUCHING",
            postcode="93250",
            source_column="ADDR0",
        )
        b = _make_addr(
            address_line="NO 6A JALAN 2/12A",
            address_line2="KAMPUNG BATU MUDA KUALA LUMPUR",
            postcode="51100",
            source_column="ADDR1",
        )
        result = cluster_addresses([a, b])
        assert len(result) == 2
        assert len(result[0]) == 1
        assert len(result[1]) == 1

    def test_three_addresses_two_similar_one_different(self):
        """Two similar + one different should produce two clusters."""
        a = _make_addr(
            address_line="NO 235 LORONG 5 JALAN KERETAPI",
            address_line2="TAMAN SPRINGFIELD",
            postcode="93250",
        )
        b = _make_addr(
            address_line="NO 235 LORONG 5 TAMAN SPRINGFIELD",
            address_line2="JALAN KERETAPI",
            postcode="93250",
        )
        c = _make_addr(
            address_line="NO 6A JALAN 2/12A",
            address_line2="KAMPUNG BATU MUDA KUALA LUMPUR",
            postcode="51100",
        )
        result = cluster_addresses([a, b, c])
        assert len(result) == 2
        cluster_sizes = sorted([len(cl) for cl in result], reverse=True)
        assert cluster_sizes == [2, 1]

    def test_custom_threshold(self):
        """Higher threshold should produce more clusters (stricter matching)."""
        a = _make_addr(address_line="NO 235 LRG 5 JALAN KERETAPI",
                       address_line2="TAMAN SPRINGFIELD", postcode="93250")
        b = _make_addr(address_line="NO 235 LORONG 5 TAMAN SPRINGFIELD",
                       address_line2="JALAN KERETAPI", postcode="93250")
        # With very high threshold, abbreviation difference may split them
        result_strict = cluster_addresses([a, b], threshold=99)
        result_loose = cluster_addresses([a, b], threshold=50)
        assert len(result_strict) >= len(result_loose)

    def test_all_identical_addresses_one_cluster(self):
        """Multiple identical addresses should all land in one cluster."""
        addr = _make_addr(address_line="NO 1 JALAN 1", postcode="50000")
        addrs = [dict(addr) for _ in range(5)]
        result = cluster_addresses(addrs)
        assert len(result) == 1
        assert len(result[0]) == 5
