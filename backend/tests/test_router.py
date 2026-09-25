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
        ("Total coal resource of India as on 01.04.2025", PeriodType.MONTH, ["2025-04"]),
    ],
)
def test_periods(q, period_type, periods):
    f = extract_filters(q)
    assert (f.period_type, f.periods) == (period_type, periods)


def test_full_company_names_and_states():
    f = extract_filters("Coal production of Mahanadi Coalfields and Northern Coalfields in 2023-24")
    assert set(f.subsidiaries) == {"MCL", "NCL"}
    f = extract_filters("Measured coal resources in Orissa and Jharkhand")
    assert f.states == ["Jharkhand", "Odisha"] and f.category == "Measured"
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


def test_states_and_all_india_use_the_extractor_names():
    assert extract_filters("Coal resources of West Bengal and Madhya Pradesh").states == [
        "Madhya Pradesh",
        "West Bengal",
    ]
    assert extract_filters("All India coal production in 2023-24").subsidiaries == ["INDIA"]
    assert extract_filters("Production of South Eastern Coalfields").subsidiaries == ["SECL"]
    assert extract_filters("Coal India's production in 2023-24").subsidiaries == ["CIL"]


# --- Hindi and paraphrased questions (#7) -------------------------------------------------------


@pytest.mark.parametrize(
    ("q", "subsidiary"),
    [
        ("दिसंबर 2024 में सीआईएल का कोयला उत्पादन कितना था?", "CIL"),
        ("दिसंबर 2024 में एनसीएल का कोयला उत्पादन कितना था?", "NCL"),
        ("दिसंबर 2024 में कोल इंडिया का कोयला उत्पादन", "CIL"),
        ("नॉर्दर्न कोलफील्ड्स का दिसंबर २०२४ में उत्पादन", "NCL"),
        ("दिसम्बर 2024 में एसईसीएल ने कितना कोयला उत्पादित किया?", "SECL"),
    ],
)
def test_hindi_figure_question_is_numeric(q, subsidiary):
    r = route(q)
    assert r.route == QaRoute.NUMERIC
    assert r.filters.metrics == [Metric.COAL_PRODUCTION]
    assert r.filters.subsidiaries == [subsidiary]
    assert (r.filters.period_type, r.filters.periods) == (PeriodType.MONTH, ["2024-12"])


@pytest.mark.parametrize(
    ("q", "metrics"),
    [
        ("एमसीएल का दिसंबर 2024 में कोयला प्रेषण", [Metric.COAL_OFFTAKE]),
        ("एमसीएल का दिसंबर 2024 में डिस्पैच", [Metric.COAL_OFFTAKE]),
        ("एमसीएल का दिसंबर 2024 में कोयला उठाव", [Metric.COAL_OFFTAKE]),
        ("वित्त वर्ष 2023-24 में भारत का कोयला आयात", [Metric.COAL_IMPORT]),
        ("सीसीएल का 2023-24 का उत्पादन लक्ष्य", [Metric.PRODUCTION_TARGET, Metric.COAL_PRODUCTION]),
        ("डब्ल्यूसीएल का 2023-24 में ओबी", [Metric.OB_REMOVAL]),
        ("ईसीएल का 2023-24 में अधिभार निष्कासन", [Metric.OB_REMOVAL]),
        ("बीसीसीएल का दिसंबर 2024 में कोकिंग कोयला उत्पादन", [Metric.COKING_COAL_PRODUCTION]),
    ],
)
def test_hindi_metric_words(q, metrics):
    r = route(q)
    assert r.route == QaRoute.NUMERIC and r.filters.metrics == metrics


def test_hindi_company_names_and_all_india():
    assert extract_filters("सिंगरेनी और कैप्टिव खानों का उत्पादन 2023-24").subsidiaries == [
        "SCCL",
        "CAPTIVE",
    ]
    assert extract_filters("एससीसीएल और एनईसी का उत्पादन").subsidiaries == ["NEC", "SCCL"]
    assert extract_filters("भारत का कोयला संसाधन").subsidiaries == ["INDIA"]
    # BCCL's name contains "भारत": it is not the all-India figure
    assert extract_filters("भारत कोकिंग कोल का उत्पादन 2023-24").subsidiaries == ["BCCL"]


def test_hindi_cumulative_and_coking():
    f = extract_filters("दिसंबर 2024 तक सीआईएल का कुल उत्पादन")
    assert (f.period_type, f.periods) == (PeriodType.YTD, ["2024-12"])
    assert extract_filters("बीसीसीएल का कोकिंग कोयला उत्पादन").coking
    assert not extract_filters("ओडिशा में नॉन-कोकिंग कोयला संसाधन").coking


def test_hindi_reason_question_is_textual_or_mixed():
    assert route("कोयले की कमी क्यों हुई?").route == QaRoute.TEXTUAL
    assert route("दिसंबर 2024 में एनसीएल का उत्पादन क्यों घटा?").route == QaRoute.MIXED


@pytest.mark.parametrize(
    ("q", "metric"),
    [
        ("How much coal did Northern Coalfields dig out in December 2024?", Metric.COAL_PRODUCTION),
        ("How much coal did NCL mine in December 2024?", Metric.COAL_PRODUCTION),
        ("Coal mined by MCL in 2023-24", Metric.COAL_PRODUCTION),
        ("Coal raised by SECL in 2023-24", Metric.COAL_PRODUCTION),
        ("How much coal was extracted by CCL in 2023-24?", Metric.COAL_PRODUCTION),
        ("Output of Mahanadi Coalfields in December 2024", Metric.COAL_PRODUCTION),
        ("Coal dispatched by MCL in December 2024", Metric.COAL_OFFTAKE),
        ("How much coal was supplied by MCL in 2023-24?", Metric.COAL_OFFTAKE),
        ("Coal lifted from NCL in December 2024", Metric.COAL_OFFTAKE),
        ("How much coal was sent by WCL in December 2024?", Metric.COAL_OFFTAKE),
    ],
)
def test_english_paraphrases_are_numeric(q, metric):
    r = route(q)
    assert r.route == QaRoute.NUMERIC and r.filters.metrics == [metric]


def test_how_much_is_not_a_request_for_reasons():
    # "how" alone asks for an explanation; "how much" / "how many" asks for a figure
    assert route("How much coal did NCL produce in December 2024?").route == QaRoute.NUMERIC
    assert route("How did NCL increase production in December 2024?").route == QaRoute.MIXED


def test_despatch_question_and_bare_metric():
    r = route("What was the coal despatch of MCL in December 2024?")
    assert r.route == QaRoute.NUMERIC and r.filters.metrics == [Metric.COAL_OFFTAKE]
    assert r.filters.subsidiaries == ["MCL"]
    # nothing to look up a figure for: left to the text search
    assert route("coal production").route == QaRoute.TEXTUAL


def test_raised_in_other_senses_is_not_production():
    assert extract_filters("Issues raised by NCL workers in 2023-24").metrics == []
