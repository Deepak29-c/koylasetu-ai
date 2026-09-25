import pytest

from app.services.normalise import normalise_fy


@pytest.mark.parametrize(
    "raw",
    [
        "2023-24",
        "2023–24",
        "2023/24",
        "2023-2024",
        "FY 2023-24",
        "fy2023-24",
        "F.Y. 2023-24",
        "FY24",
        "FY 24",
        "FY2024",
        " 2023 - 24 ",
        "२०२३-२४",
    ],
)
def test_all_forms_give_the_same_fy(raw):
    assert normalise_fy(raw) == "FY 2023-24"


def test_century_rollover():
    assert normalise_fy("1999-00") == "FY 1999-00"
    assert normalise_fy("2099-00") == "FY 2099-00"


def test_blank_is_none():
    assert normalise_fy(None) is None
    assert normalise_fy("  ") is None


@pytest.mark.parametrize("raw", ["2023-25", "2024-23", "2023", "last year", "FY 2023-24-25"])
def test_rejects_unclear_values(raw):
    with pytest.raises(ValueError):
        normalise_fy(raw)


# --- Numbers, units, subsidiaries, states, periods (guide 7.3) --------------------------------

from app.models.enums import PeriodType  # noqa: E402
from app.services.normalise import (  # noqa: E402
    find_period,
    find_unit,
    fy_of_month,
    match_state,
    match_subsidiaries,
    parse_number,
    resolve_period,
)


@pytest.mark.parametrize(
    "raw, value",
    [
        ("1,23,456.70", 123456.7),  # Indian grouping
        ("123,456.70", 123456.7),  # western grouping
        ("225.20", 225.2),
        ("(12.5)", -12.5),
        ("-2965.53", -2965.53),
        ("204.62*", 204.62),
        ("1234 (P)", 1234.0),
        ("१२३.४५", 123.45),  # Devanagari digits
    ],
)
def test_parse_number(raw, value):
    assert parse_number(raw) == value


@pytest.mark.parametrize(
    "raw", ["", "-", "–", "NA", "N.A.", "nil", "9%", "▲ 9.43", "0-300", "10 20"]
)
def test_parse_number_empty_or_not_a_number(raw):
    assert parse_number(raw) is None


@pytest.mark.parametrize(
    "text, label, factor",
    [
        ("Production (MT)", "MT", 1),
        ("Figures in Million Tonnes", "MT", 1),
        ("mill. te", "MT", 1),
        ("Lakh Tonnes", "Lakh tonnes", 0.1),
        ("lakh MT", "Lakh tonnes", 0.1),  # not read as MT
        ("'000 tonnes", "Thousand tonnes", 0.001),
        ("Thousand Tonnes", "Thousand tonnes", 0.001),
        ("OBR (M.Cum)", "Mcum", 1),
        ("Million cubic metres", "Mcum", 1),
        ("Lakh cum", "Lakh cum", 0.1),
        ("लाख टन", "Lakh tonnes", 0.1),
    ],
)
def test_find_unit(text, label, factor):
    unit = find_unit(text)
    assert (unit.label, unit.to_std) == (label, factor)


@pytest.mark.parametrize("text", ["Growth (%)", "Royalty (Rs. Cr.)", "Drilling (Lakh m)", "MW"])
def test_find_unit_other(text):
    assert find_unit(text).kind == "other"


def test_find_unit_none():
    assert find_unit("Coal production") is None


@pytest.mark.parametrize(
    "text, code",
    [
        ("Mahanadi Coalfields Limited", "MCL"),
        ("MCL", "MCL"),
        ("M.C.L.", "MCL"),
        ("South Eastern Coalfields", "SECL"),
        ("SECL", "SECL"),
        ("North Eastern Coalfields", "NEC"),
        ("Eastern Coalfields Ltd", "ECL"),
        ("Bharat Coking Coal Ltd", "BCCL"),
        ("Coal India Limited", "CIL"),
        ("Singareni Collieries", "SCCL"),
        ("Captive/Others", "CAPTIVE"),
    ],
)
def test_subsidiary_aliases(text, code):
    codes, _ = match_subsidiaries(text)
    assert codes == {code}


def test_subsidiary_match_returns_the_rest_of_the_label():
    assert match_subsidiaries("1 ECL RAJMAHAL OC") == ({"ECL"}, "1 RAJMAHAL OC")


@pytest.mark.parametrize(
    "text, state",
    [("ODISHA", "Odisha"), ("Orissa", "Odisha"), ("Jammu and Kashmir", "Jammu & Kashmir"),
     ("Nagaland", "Nagaland"), ("Total", None), ("MCL", None)],
)  # fmt: skip
def test_match_state(text, state):
    assert match_state(text) == state


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2023-24", (PeriodType.FY, "FY 2023-24")),
        ("2019-\n20\nActual", (PeriodType.FY, "FY 2019-20")),
        ("FY 25", (PeriodType.FY, "FY 2024-25")),
        ("FY 23-24", (PeriodType.FY, "FY 2023-24")),
        ("Annual Target 24-25", (PeriodType.FY, "FY 2024-25")),
        ("Dec'24", (PeriodType.MONTH, "2024-12")),
        ("December 2024", (PeriodType.MONTH, "2024-12")),
        ("2024-12", (PeriodType.MONTH, "2024-12")),
        ("AS ON 01.04.2024", (PeriodType.MONTH, "2024-04")),
        ("1st April 2024", (PeriodType.MONTH, "2024-04")),
        ("Production during Dec FY 25", (PeriodType.MONTH, "2024-12")),  # Dec of FY 2024-25
        ("During Jan FY 25", (PeriodType.MONTH, "2025-01")),  # Jan is in the FY's second year
        ("दिसंबर 2024", (PeriodType.MONTH, "2024-12")),
        ("Monthly Target", None),
        ("Measured (331)", None),
        ("0-300", None),
    ],
)
def test_find_period(text, expected):
    assert resolve_period(find_period(text)) == expected


def test_ranges_and_projections_are_marked():
    assert find_period("Production upto Dec FY 25").cumulative
    assert find_period("2024-25 (Apr'24-Nov'24) (Prov.)").cumulative
    assert find_period("Apr-Dec 2024").cumulative
    assert find_period("2024-25 (Proj.)").projected
    assert not find_period("2024-25 (Prov.)").projected


def test_two_periods_in_one_header_is_not_resolved():
    assert resolve_period(find_period("Growth FY25 over FY24")) is None


def test_fy_of_month():
    assert fy_of_month("2024-12") == "FY 2024-25"
    assert fy_of_month("2025-03") == "FY 2024-25"
    assert fy_of_month("2025-04") == "FY 2025-26"
