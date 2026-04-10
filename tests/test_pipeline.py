"""Integration tests for the main pipeline module."""

import pandas as pd
import pytest

from src.pipeline import process_file, _get_addr_columns, _select_best_address


class TestGetAddrColumns:
    """Tests for _get_addr_columns helper."""

    def test_finds_and_sorts_addr_columns(self):
        df = pd.DataFrame(columns=["ICNO", "NAME", "ADDR2", "ADDR0", "ADDR10", "ADDR1"])
        result = _get_addr_columns(df)
        assert result == ["ADDR0", "ADDR1", "ADDR2", "ADDR10"]

    def test_returns_empty_when_no_addr_columns(self):
        df = pd.DataFrame(columns=["ICNO", "NAME", "OTHER"])
        result = _get_addr_columns(df)
        assert result == []


class TestSelectBestAddress:
    """Tests for _select_best_address helper."""

    def test_returns_none_for_empty_clusters(self):
        addr, confidence = _select_best_address([])
        assert addr is None
        assert confidence == 0.0

    def test_selects_highest_scoring_cluster_and_address(self):
        clusters = [
            [
                {"address_line": "NO 1 JALAN 1", "address_line2": "", "postcode": "", "city": "", "state": ""},
            ],
            [
                {"address_line": "NO 5 JALAN MAJU", "address_line2": "TAMAN SENTOSA", "postcode": "88100", "city": "KOTA KINABALU", "state": "SABAH"},
                {"address_line": "NO 5 JLN MAJU", "address_line2": "TMN SENTOSA", "postcode": "88100", "city": "KOTA KINABALU", "state": "SABAH"},
            ],
        ]
        addr, confidence = _select_best_address(clusters)
        assert addr is not None
        assert addr["postcode"] == "88100"
        assert confidence > 0.0


class TestProcessFile:
    """Integration test for the full pipeline."""

    def test_process_file_end_to_end(self, tmp_path):
        """Create synthetic Excel, run pipeline, verify output."""
        input_path = tmp_path / "input.xlsx"
        output_path = tmp_path / "output.xlsx"

        rows = [
            {
                "ICNO": "900208125173",
                "NAME": "ALI BIN ABU",
                "ADDR0": "NO 5, JALAN MAJU, TAMAN SENTOSA, 88100, KOTA KINABALU, SABAH",
                "ADDR1": "NO 5 JLN MAJU, TMN SENTOSA, 88100, KOTA KINABALU, SABAH",
                "ADDR2": "KOTA KINABALU, SABAH",
            },
            {
                "ICNO": "830509135841",
                "NAME": "SITI BINTI AHMAD",
                "ADDR0": "LOT 123, JALAN PENDING, 93450, KUCHING, SARAWAK",
                "ADDR1": "LOT 123, JLN PENDING, 93450, KUCHING, SARAWAK",
                "ADDR2": "",
            },
        ]
        df = pd.DataFrame(rows)
        df.to_excel(input_path, index=False, engine="openpyxl")

        stats = process_file(str(input_path), str(output_path))

        assert output_path.exists()

        out_df = pd.read_excel(str(output_path), engine="openpyxl")

        assert list(out_df.columns) == ["ICNO", "NAME", "MAILING_ADDRESS", "CONFIDENCE"]
        assert len(out_df) == 2

        for _, row in out_df.iterrows():
            assert row["MAILING_ADDRESS"] is not None
            assert str(row["MAILING_ADDRESS"]).strip() != ""
            assert 0.0 <= row["CONFIDENCE"] <= 1.0

        assert stats["total"] == 2
        assert stats["processed"] == 2
        assert stats["no_address"] == 0

    def test_process_file_filters_header_rows(self, tmp_path):
        """Header rows where ICNO looks like a column header should be skipped."""
        input_path = tmp_path / "input.xlsx"
        output_path = tmp_path / "output.xlsx"

        rows = [
            {
                "ICNO": "ICNO",
                "NAME": "NAME",
                "ADDR0": "ADDR0",
            },
            {
                "ICNO": "900208125173",
                "NAME": "ALI BIN ABU",
                "ADDR0": "NO 5, JALAN MAJU, TAMAN SENTOSA, 88100, KOTA KINABALU, SABAH",
            },
        ]
        df = pd.DataFrame(rows)
        df.to_excel(input_path, index=False, engine="openpyxl")

        stats = process_file(str(input_path), str(output_path))

        out_df = pd.read_excel(str(output_path), engine="openpyxl")
        assert len(out_df) == 1
        assert stats["total"] == 1

    def test_process_file_handles_no_address(self, tmp_path):
        """Rows with all empty ADDR columns get no_address count incremented."""
        input_path = tmp_path / "input.xlsx"
        output_path = tmp_path / "output.xlsx"

        rows = [
            {
                "ICNO": "900208125173",
                "NAME": "ALI BIN ABU",
                "ADDR0": "",
                "ADDR1": "",
            },
        ]
        df = pd.DataFrame(rows)
        df.to_excel(input_path, index=False, engine="openpyxl")

        stats = process_file(str(input_path), str(output_path))

        assert stats["no_address"] == 1
        assert stats["processed"] == 1

        out_df = pd.read_excel(str(output_path), engine="openpyxl")
        assert len(out_df) == 1
