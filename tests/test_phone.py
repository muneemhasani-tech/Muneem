import pytest

from lead_verifier.checks.phone import is_valid_mobile, parse_phone

GOOD_GP = [
    "01711-223344", "8801711223344", "+880 1711 223344", "1711223344", "0088 01711223344",
    "(017) 11-22-33-44", "  01711223344  ", "+8801711223344", "01711 223 344",
    "01711223344 / 01811223344",
]


@pytest.mark.parametrize("raw", GOOD_GP)
def test_messy_formats_normalise_to_e164(raw):
    r = parse_phone(raw)
    assert r.e164 == "+8801711223344"
    assert r.valid and r.type == "mobile" and is_valid_mobile(r)
    assert r.carrier == "Grameenphone"


@pytest.mark.parametrize("raw,reason", [("017112233", "invalid_number"), ("abc", "unparseable"),
                                        ("01011223344", "invalid_number"), ("++", "unparseable")])
def test_invalid_numbers(raw, reason):
    r = parse_phone(raw)
    assert r.valid is False and r.e164 == "" and r.reason == reason


def test_blank_is_none_not_false():
    r = parse_phone("   ")
    assert r.valid is None and r.e164 == ""


def test_landline_is_valid_but_not_mobile():
    r = parse_phone("02-9123456")
    assert r.valid and r.type == "fixed_line" and not is_valid_mobile(r)


def test_foreign_mobile_accepted():
    r = parse_phone("+44 7911 123456")
    assert r.valid and r.type == "mobile" and r.e164 == "+447911123456"


def test_second_number_in_cell_used_when_first_bad():
    assert parse_phone("123 / 01811223344").e164 == "+8801811223344"


def test_carrier_comes_from_library_not_hardcoded():
    assert parse_phone("01911223344").carrier == "Banglalink"
