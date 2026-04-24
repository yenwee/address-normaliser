"""Tests for address normaliser module."""

import pytest

from src.processing.normaliser import expand_abbreviations, normalise_state, normalise_address


class TestExpandAbbreviations:
    """Tests for expand_abbreviations function."""

    def test_expand_jln(self):
        """JLN should expand to JALAN."""
        assert expand_abbreviations("JLN MAJU") == "JALAN MAJU"

    def test_expand_jl(self):
        """JL should expand to JALAN."""
        assert expand_abbreviations("JL MAJU") == "JALAN MAJU"

    def test_expand_tmn(self):
        """TMN should expand to TAMAN."""
        assert expand_abbreviations("TMN SPRINGFIELD") == "TAMAN SPRINGFIELD"

    def test_expand_lrg(self):
        """LRG should expand to LORONG."""
        assert expand_abbreviations("LRG 5") == "LORONG 5"

    def test_expand_kg(self):
        """KG should expand to KAMPUNG."""
        assert expand_abbreviations("KG BATU MUDA") == "KAMPUNG BATU MUDA"

    def test_expand_kpg(self):
        """KPG should expand to KAMPUNG."""
        assert expand_abbreviations("KPG BATU") == "KAMPUNG BATU"

    def test_expand_kmpg(self):
        """KMPG should expand to KAMPUNG."""
        assert expand_abbreviations("KMPG BATU") == "KAMPUNG BATU"

    def test_expand_bdr(self):
        """BDR should expand to BANDAR."""
        assert expand_abbreviations("BDR UTAMA") == "BANDAR UTAMA"

    def test_expand_sg(self):
        """SG is ambiguous and should not be globally expanded."""
        assert expand_abbreviations("SG BESI") == "SG BESI"

    def test_ps_not_globally_expanded(self):
        """PS is ambiguous (not always PETI SURAT), keep literal."""
        assert expand_abbreviations("JALAN PS 5/13") == "JALAN PS 5/13"

    def test_expand_bt(self):
        """BT should expand to BATU."""
        assert expand_abbreviations("BT 5") == "BATU 5"

    def test_expand_psr(self):
        """PSR should expand to PASAR."""
        assert expand_abbreviations("PSR BARU") == "PASAR BARU"

    def test_expand_ppr(self):
        """PPR should expand to PROJEK PERUMAHAN RAKYAT."""
        assert expand_abbreviations("PPR DESA") == "PROJEK PERUMAHAN RAKYAT DESA"

    def test_expand_sbg(self):
        """SBG should expand to SUBANG."""
        assert expand_abbreviations("SBG JAYA") == "SUBANG JAYA"

    def test_expand_pjy(self):
        """PJY should expand to PUTRAJAYA."""
        assert expand_abbreviations("PJY PRESINT 1") == "PUTRAJAYA PRESINT 1"

    def test_expand_sec(self):
        """SEC should expand to SEKSYEN."""
        assert expand_abbreviations("SEC 7") == "SEKSYEN 7"

    def test_expand_sek(self):
        """SEK should expand to SEKSYEN."""
        assert expand_abbreviations("SEK 14") == "SEKSYEN 14"

    def test_expand_kws(self):
        """KWS should expand to KAWASAN."""
        assert expand_abbreviations("KWS PERINDUSTRIAN") == "KAWASAN PERINDUSTRIAN"

    def test_expand_per(self):
        """PER should expand to PERINDUSTRIAN."""
        assert expand_abbreviations("PER BUKIT RAJA") == "PERINDUSTRIAN BUKIT RAJA"

    def test_expand_ind(self):
        """IND should expand to INDUSTRI."""
        assert expand_abbreviations("IND BATU CAVES") == "INDUSTRI BATU CAVES"

    def test_sri_normalised_to_seri(self):
        """SRI and SERI are both valid Malay honorifics but refer to the same
        locality in place names (e.g. "TAMAN SRI PUTRI" == "TAMAN SERI PUTRI").
        We canonicalise to SERI to keep mailing output consistent and because
        the expert golden benchmark uses SERI more frequently.
        """
        assert expand_abbreviations("SRI MUDA") == "SERI MUDA"
        assert expand_abbreviations("TAMAN SRI PUTRI") == "TAMAN SERI PUTRI"

    def test_expand_dr(self):
        """DR should expand to DARUL."""
        assert expand_abbreviations("DR EHSAN") == "DARUL EHSAN"

    def test_multiple_abbreviations_in_one_string(self):
        """Multiple abbreviations in one string should all be expanded."""
        assert expand_abbreviations("NO 235 LRG 5 JLN KERETAPI") == "NO 235 LORONG 5 JALAN KERETAPI"

    def test_multiple_abbreviations_kg_and_tmn(self):
        """KG and TMN in the same string."""
        assert expand_abbreviations("KG BATU TMN MAJU") == "KAMPUNG BATU TAMAN MAJU"

    def test_no_partial_expansion_jlns(self):
        """JLNS should NOT become JALANS - word boundary must be respected."""
        assert expand_abbreviations("JLNS MAJU") == "JLNS MAJU"

    def test_no_partial_expansion_tmns(self):
        """TMNS should NOT be expanded."""
        assert expand_abbreviations("TMNS PARK") == "TMNS PARK"

    def test_no_partial_expansion_lrg_prefix(self):
        """LRGS should NOT be expanded."""
        assert expand_abbreviations("LRGS 5") == "LRGS 5"

    def test_no_partial_expansion_kgs(self):
        """KGS should NOT become KAMPUNGS."""
        assert expand_abbreviations("KGS BARU") == "KGS BARU"

    def test_abbreviation_at_start_of_string(self):
        """Abbreviation at the very start of the string."""
        assert expand_abbreviations("JLN 1") == "JALAN 1"

    def test_abbreviation_at_end_of_string(self):
        """Abbreviation at the very end of the string."""
        assert expand_abbreviations("NO 1 JLN") == "NO 1 JALAN"

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert expand_abbreviations("") == ""

    def test_no_abbreviations(self):
        """String with no abbreviations should be unchanged."""
        assert expand_abbreviations("NO 10 JALAN MAJU") == "NO 10 JALAN MAJU"

    def test_case_insensitive_input(self):
        """Input may already be uppercase; abbreviation matching uses word boundaries."""
        assert expand_abbreviations("JLN MAJU INDAH") == "JALAN MAJU INDAH"


class TestNormaliseState:
    """Tests for normalise_state function."""

    def test_wp_to_wilayah_persekutuan_kl(self):
        """WP should normalise to WILAYAH PERSEKUTUAN KUALA LUMPUR."""
        assert normalise_state("WP") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_wpkl_to_wilayah_persekutuan_kl(self):
        """WPKL should normalise to WILAYAH PERSEKUTUAN KUALA LUMPUR."""
        assert normalise_state("WPKL") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_kl_to_wilayah_persekutuan_kl(self):
        """KL should normalise to WILAYAH PERSEKUTUAN KUALA LUMPUR."""
        assert normalise_state("KL") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_kuala_lumpur_to_wilayah_persekutuan_kl(self):
        """KUALA LUMPUR should normalise to WILAYAH PERSEKUTUAN KUALA LUMPUR."""
        assert normalise_state("KUALA LUMPUR") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_wp_kuala_lumpur_dot_to_wilayah_persekutuan_kl(self):
        """W.P. KUALA LUMPUR should normalise."""
        assert normalise_state("W.P. KUALA LUMPUR") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_wp_kuala_lumpur_to_wilayah_persekutuan_kl(self):
        """WP KUALA LUMPUR should normalise."""
        assert normalise_state("WP KUALA LUMPUR") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_wilayah_persekutuan_to_kl(self):
        """WILAYAH PERSEKUTUAN should normalise to WILAYAH PERSEKUTUAN KUALA LUMPUR."""
        assert normalise_state("WILAYAH PERSEKUTUAN") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_federal_territory_of_kuala_lumpur_to_wilayah_persekutuan_kl(self):
        """Provider state alias should normalise to WILAYAH PERSEKUTUAN KUALA LUMPUR."""
        assert normalise_state("Federal Territory of Kuala Lumpur") == "WILAYAH PERSEKUTUAN KUALA LUMPUR"

    def test_penang_to_pulau_pinang(self):
        """PENANG should normalise to PULAU PINANG."""
        assert normalise_state("PENANG") == "PULAU PINANG"

    def test_pinang_to_pulau_pinang(self):
        """Provider PINANG alias should normalise to PULAU PINANG."""
        assert normalise_state("PINANG") == "PULAU PINANG"

    def test_malacca_to_melaka(self):
        """Provider MALACCA alias should normalise to MELAKA."""
        assert normalise_state("MALACCA") == "MELAKA"

    def test_trengganu_to_terengganu(self):
        """Provider TRENGGANU alias should normalise to TERENGGANU."""
        assert normalise_state("TRENGGANU") == "TERENGGANU"

    def test_negri_sembilan_to_negeri_sembilan(self):
        """Provider NEGRI SEMBILAN alias should normalise to NEGERI SEMBILAN."""
        assert normalise_state("NEGRI SEMBILAN") == "NEGERI SEMBILAN"

    def test_n_dot_sembilan_to_negeri_sembilan(self):
        """N. SEMBILAN should normalise to NEGERI SEMBILAN."""
        assert normalise_state("N. SEMBILAN") == "NEGERI SEMBILAN"

    def test_n_dot_sembilan_no_space_to_negeri_sembilan(self):
        """N.SEMBILAN should normalise to NEGERI SEMBILAN."""
        assert normalise_state("N.SEMBILAN") == "NEGERI SEMBILAN"

    def test_wp_putrajaya_to_wilayah_persekutuan_putrajaya(self):
        """W.P. PUTRAJAYA should normalise."""
        assert normalise_state("W.P. PUTRAJAYA") == "WILAYAH PERSEKUTUAN PUTRAJAYA"

    def test_putrajaya_to_wilayah_persekutuan_putrajaya(self):
        """PUTRAJAYA should normalise."""
        assert normalise_state("PUTRAJAYA") == "WILAYAH PERSEKUTUAN PUTRAJAYA"

    def test_wp_labuan_to_wilayah_persekutuan_labuan(self):
        """W.P. LABUAN should normalise."""
        assert normalise_state("W.P. LABUAN") == "WILAYAH PERSEKUTUAN LABUAN"

    def test_labuan_to_wilayah_persekutuan_labuan(self):
        """LABUAN should normalise."""
        assert normalise_state("LABUAN") == "WILAYAH PERSEKUTUAN LABUAN"

    def test_known_state_passthrough(self):
        """Known states like SELANGOR should pass through unchanged."""
        assert normalise_state("SELANGOR") == "SELANGOR"

    def test_unknown_state_passthrough(self):
        """Unknown state values should pass through unchanged."""
        assert normalise_state("SOMETHING ELSE") == "SOMETHING ELSE"

    def test_empty_state(self):
        """Empty state should return empty string."""
        assert normalise_state("") == ""

    def test_lowercase_input_normalised(self):
        """Lowercase input should still be normalised."""
        assert normalise_state("penang") == "PULAU PINANG"


class TestNormaliseAddress:
    """Tests for normalise_address function."""

    def test_full_address_normalisation(self):
        """Full address dict should have all fields normalised."""
        addr = {
            "address_line": "NO 235 LRG 5 JLN KERETAPI",
            "address_line2": "TMN SPRINGFIELD",
            "address_line3": "",
            "postcode": "93250",
            "city": "kuching",
            "state": "SARAWAK",
            "raw": "NO 235 LRG 5 JLN KERETAPI, TMN SPRINGFIELD, , 93250, KUCHING, SARAWAK, ",
            "source_column": "ADDR0",
        }
        result = normalise_address(addr)

        assert result["address_line"] == "NO 235 LORONG 5 JALAN KERETAPI"
        assert result["address_line2"] == "TAMAN SPRINGFIELD"
        assert result["address_line3"] == ""
        assert result["postcode"] == "93250"
        assert result["city"] == "KUCHING"
        assert result["state"] == "SARAWAK"
        assert result["raw"] == addr["raw"]
        assert result["source_column"] == "ADDR0"

    def test_state_normalisation_in_full_address(self):
        """State field should be normalised via normalise_state."""
        addr = {
            "address_line": "NO 6A JALAN 2/12A",
            "address_line2": "KG BATU MUDA",
            "address_line3": "",
            "postcode": "51100",
            "city": "KUALA LUMPUR",
            "state": "WP",
            "raw": "raw text",
            "source_column": "ADDR0",
        }
        result = normalise_address(addr)
        assert result["state"] == "WILAYAH PERSEKUTUAN KUALA LUMPUR"
        assert result["address_line2"] == "KAMPUNG BATU MUDA"

    def test_extra_whitespace_removal(self):
        """Multiple spaces should be collapsed to a single space."""
        addr = {
            "address_line": "NO  6A   JALAN   2/12A",
            "address_line2": "KG   BATU   MUDA",
            "address_line3": "",
            "postcode": "51100",
            "city": "kuala   lumpur",
            "state": "SELANGOR",
            "raw": "raw text",
            "source_column": "ADDR0",
        }
        result = normalise_address(addr)
        assert result["address_line"] == "NO 6A JALAN 2/12A"
        assert result["address_line2"] == "KAMPUNG BATU MUDA"
        assert result["city"] == "KUALA LUMPUR"

    def test_hyphen_normalisation(self):
        """Hyphens with spaces around them should be normalised."""
        addr = {
            "address_line": "LORONG 5 -LOT 265",
            "address_line2": "",
            "address_line3": "",
            "postcode": "88100",
            "city": "KOTA KINABALU",
            "state": "SABAH",
            "raw": "raw text",
            "source_column": "ADDR0",
        }
        result = normalise_address(addr)
        assert result["address_line"] == "LORONG 5 LOT 265"

    def test_passthrough_fields(self):
        """postcode, raw, and source_column should be passed through unchanged."""
        addr = {
            "address_line": "JLN 1",
            "address_line2": "",
            "address_line3": "",
            "postcode": "50000",
            "city": "KL",
            "state": "WP",
            "raw": "original raw string",
            "source_column": "ADDR5",
        }
        result = normalise_address(addr)
        assert result["postcode"] == "50000"
        assert result["raw"] == "original raw string"
        assert result["source_column"] == "ADDR5"

    def test_original_dict_not_mutated(self):
        """normalise_address should return a new dict, not mutate the input."""
        addr = {
            "address_line": "JLN 1",
            "address_line2": "",
            "address_line3": "",
            "postcode": "50000",
            "city": "KL",
            "state": "WP",
            "raw": "raw",
            "source_column": "ADDR0",
        }
        original_address_line = addr["address_line"]
        normalise_address(addr)
        assert addr["address_line"] == original_address_line

    def test_uppercase_conversion(self):
        """Address lines and city should be uppercased."""
        addr = {
            "address_line": "no 1 jalan maju",
            "address_line2": "taman seri",
            "address_line3": "lot 5",
            "postcode": "50000",
            "city": "shah alam",
            "state": "selangor",
            "raw": "raw",
            "source_column": "ADDR0",
        }
        result = normalise_address(addr)
        assert result["address_line"] == "NO 1 JALAN MAJU"
        assert result["address_line2"] == "TAMAN SERI"
        assert result["address_line3"] == "LOT 5"
        assert result["city"] == "SHAH ALAM"
        assert result["state"] == "SELANGOR"
