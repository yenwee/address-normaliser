from src.processing.formatter import format_mailing_block


class TestFormatMailingBlock:
    def test_full_address_all_fields(self):
        addr = {
            "address_line": "NO 235 LORONG 5 JALAN KERETAPI",
            "address_line2": "TAMAN SPRINGFIELD",
            "address_line3": "",
            "postcode": "93250",
            "city": "KUCHING",
            "state": "SARAWAK",
        }
        expected = "NO 235 LORONG 5 JALAN KERETAPI\nTAMAN SPRINGFIELD\n93250 KUCHING\nSARAWAK"
        assert format_mailing_block(addr) == expected

    def test_no_address_line2(self):
        addr = {
            "address_line": "NO 1 JALAN AMPANG",
            "address_line2": "",
            "address_line3": "",
            "postcode": "50450",
            "city": "KUALA LUMPUR",
            "state": "WILAYAH PERSEKUTUAN KUALA LUMPUR",
        }
        expected = "NO 1 JALAN AMPANG\n50450 KUALA LUMPUR\nWILAYAH PERSEKUTUAN KUALA LUMPUR"
        assert format_mailing_block(addr) == expected

    def test_missing_postcode(self):
        addr = {
            "address_line": "KAMPUNG PARIS 3",
            "address_line2": "",
            "address_line3": "",
            "postcode": "",
            "city": "KOTA KINABALU",
            "state": "SABAH",
        }
        expected = "KAMPUNG PARIS 3\nKOTA KINABALU\nSABAH"
        assert format_mailing_block(addr) == expected

    def test_with_address_line3(self):
        addr = {
            "address_line": "LOT 123",
            "address_line2": "LORONG BAKAWALI",
            "address_line3": "TAMAN PERMAI",
            "postcode": "81100",
            "city": "JOHOR BAHRU",
            "state": "JOHOR",
        }
        expected = "LOT 123 LORONG BAKAWALI\nTAMAN PERMAI\n81100 JOHOR BAHRU\nJOHOR"
        assert format_mailing_block(addr) == expected

    def test_postcode_only_no_city(self):
        addr = {
            "address_line": "NO 5 JALAN MERDEKA",
            "address_line2": "",
            "address_line3": "",
            "postcode": "40000",
            "city": "",
            "state": "SELANGOR",
        }
        expected = "NO 5 JALAN MERDEKA\n40000\nSELANGOR"
        assert format_mailing_block(addr) == expected

    def test_no_state(self):
        addr = {
            "address_line": "NO 10 JALAN SULTAN",
            "address_line2": "KAMPUNG BARU",
            "address_line3": "",
            "postcode": "50300",
            "city": "KUALA LUMPUR",
            "state": "",
        }
        expected = "NO 10 JALAN SULTAN\nKAMPUNG BARU\n50300 KUALA LUMPUR"
        assert format_mailing_block(addr) == expected

    def test_empty_postcode_and_city_skips_line(self):
        addr = {
            "address_line": "KAMPUNG SUNGAI",
            "address_line2": "",
            "address_line3": "",
            "postcode": "",
            "city": "",
            "state": "SABAH",
        }
        expected = "KAMPUNG SUNGAI\nSABAH"
        assert format_mailing_block(addr) == expected

    def test_does_not_strip_state_when_part_of_city_phrase(self):
        addr = {
            "address_line": "NO 39",
            "address_line2": "JALAN KUALA KEDAH KAMPUNG MASJID",
            "address_line3": "KAMPUNG MASJID",
            "postcode": "06600",
            "city": "KUALA KEDAH",
            "state": "KEDAH",
        }
        expected = "NO 39 JALAN KUALA KEDAH\nKAMPUNG MASJID\n06600 KUALA KEDAH\nKEDAH"
        assert format_mailing_block(addr) == expected

    def test_still_strips_true_state_suffix(self):
        addr = {
            "address_line": "NO 1 JALAN AMPANG SELANGOR",
            "address_line2": "",
            "address_line3": "",
            "postcode": "50450",
            "city": "KUALA LUMPUR",
            "state": "SELANGOR",
        }
        expected = "NO 1 JALAN AMPANG\n50450 KUALA LUMPUR\nSELANGOR"
        assert format_mailing_block(addr) == expected
