import pytest

from app.models.enums import Metric, PeriodType, QaRoute
from app.services.router import extract_filters, route


def test_ncl_production_vs_target_in_a_month():
    r = route("What was NCL coal production in December 2024 compared to its monthly target?")
    assert r.route == QaRoute.NUMERIC
    f = r.filters
    assert set(f.metrics) == {Metric.PRODUCTION_TARGET, Metric.COAL_PRODUCTION}
    assert f.subsidiaries == ["NCL"]
    assert (f.period_type, f.periods) == (PeriodType.MONTH, ["2024-12"])


@pytest.mark.parametrize(
    ("q", "period_type", "periods"),
    [
        ("Coal production of CIL in 2023-24", PeriodType.FY, ["FY 2023-24"]),
        ("Coal production of CIL in FY24", PeriodType.FY, ["FY 2023-24"]),
        ("CIL production in 2023-24 and 2024-25", PeriodType.FY, ["FY 2023-24", "FY 2024-25"]),
        ("MCL despatch in Dec'24", PeriodType.MONTH, ["2024-12"]),
        ("MCL despatch in January 2025", PeriodType.MONTH, ["2025-01"]),
        ("CIL production upto December 2024", PeriodType.YTD, ["2024-12"]),
        ("Total coal resource of India as on 01.04.2025", PeriodType.AS_ON, ["2025-04-01"]),
    ],
)
def test_periods(q, period_type, periods):
    f = extract_filters(q)
    assert (f.period_type, f.periods) == (period_type, periods)


def test_full_company_names_and_states():
    f = extract_filters("Coal production of Mahanadi Coalfields and Northern Coalfields in 2023-24")
    assert set(f.subsidiaries) == {"MCL", "NCL"}
    f = extract_filters("Measured coal resources in Orissa and Jharkhand")
    assert f.states == ["JHARKHAND", "ODISHA"] and f.category == "Measured"
    assert f.metrics == [Metric.COAL_RESOURCE]


def test_coking_coal():
    f = extract_filters("Coking coal production of BCCL in December 2024")
    assert f.metrics == [Metric.COKING_COAL_PRODUCTION] and f.coking and f.subsidiaries == ["BCCL"]
    assert not extract_filters("Non-coking coal resources of Odisha").coking


def test_subsidiary_wise_breakdown_is_numeric():
    r = route("Subsidiary-wise coal production of CIL in December 2024")
    assert r.route == QaRoute.NUMERIC and r.filters.breakdown


@pytest.mark.parametrize(
    "q",
    [
        "What steps were taken to meet the coal shortage at power plants?",
        "Why did coal stock at thermal plants fall in October 2021?",
        "What is the policy on commercial coal mining?",
    ],
)
def test_explanations_are_textual(q):
    assert route(q).route == QaRoute.TEXTUAL


def test_numbers_plus_steps_is_mixed():
    r = route("What was NCL production in December 2024 and what steps are taken to increase it?")
    assert r.route == QaRoute.MIXED


def test_word_ncl_inside_other_words_is_not_a_company():
    assert extract_filters("the uncle of the minister").subsidiaries == []
