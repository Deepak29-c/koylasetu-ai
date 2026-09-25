import pytest

from app.services.normalise import (
    find_unit,
    month_in_fy,
    parse_number,
    state_name,
    subsidiary_code,
)


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("12.70", 12.70),
        ("4,00,715.45", 400715.45),
        ("400,715.45", 400715.45),
        ("७८१.०६", 781.06),
        ("(12.5)", -12.5),
        (" 0.03 ", 0.03),
    ],
)
def test_numbers(raw, value):
    assert parse_number(raw) == pytest.approx(value)


@pytest.mark.parametrize("raw", ["", "-", "NA", "n.a.", "▲ 9.43", "93.17%", "FY 25", "Dec"])
def test_not_numbers(raw):
    assert parse_number(raw) is None


@pytest.mark.parametrize(
    ("text", "std", "factor"),
    [
        ("Fig. in MT", "MT", 1.0),
        ("(Qty. in MT)", "MT", 1.0),
        ("(Resource in million tonne)", "MT", 1.0),
        ("Production in Lakh Tonnes", "MT", 0.1),
        ("('000 tonnes)", "MT", 0.001),
        ("OBR (M.Cum)", "Mcum", 1.0),
        ("(in billion tonne)", "MT", 1000.0),
    ],
)
def test_units(text, std, factor):
    _, got_std, got_factor = find_unit(text)
    assert (got_std, got_factor) == (std, factor)


def test_unit_missing():
    assert find_unit("Coal Production during December") is None
    assert find_unit("MTPA is not a unit here? MT is") is not None  # MT itself still counts


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("MCL", "MCL"),
        ("M.C.L.", "MCL"),
        ("Mahanadi Coalfields Ltd", "MCL"),
        ("10 Captives/Others", "CAPTIVE"),
        ("Grand Total", "ALL_INDIA"),
        ("CIL", "CIL"),
        ("Sl No", None),
        ("NLCIL", None),
    ],
)
def test_subsidiaries(text, code):
    assert subsidiary_code(text) == code


def test_states():
    assert state_name("ODISHA") == "ODISHA"
    assert state_name("Orissa") == "ODISHA"
    assert state_name("West Bengal") == "WEST BENGAL"
    assert state_name("Total") is None


def test_months_follow_the_indian_financial_year():
    assert month_in_fy(12, "FY 2024-25") == "2024-12"
    assert month_in_fy(1, "FY 2024-25") == "2025-01"
    assert month_in_fy(4, "FY 2024-25") == "2024-04"
