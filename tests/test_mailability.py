"""Tests for mailability helpers."""

from src.processing.mailability import inspect_mailing_block, is_mailable_block


def test_is_mailable_block_true_for_street_plus_postcode():
    addr = "NO 5 JALAN MAJU\nTAMAN SENTOSA\n88100 KOTA KINABALU\nSABAH"
    assert is_mailable_block(addr) is True


def test_is_mailable_block_false_without_postcode():
    addr = "NO 5 JALAN MAJU\nTAMAN SENTOSA\nSABAH"
    assert is_mailable_block(addr) is False


def test_inspect_mailing_block_flags_missing_house_number():
    addr = "JALAN MAJU\nTAMAN SENTOSA\n88100 KOTA KINABALU\nSABAH"
    signals = inspect_mailing_block(addr)
    assert signals["mailable"] is True
    assert signals["has_house_number"] is False
