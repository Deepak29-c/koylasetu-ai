"""Tables -> facts (guide 7.2-7.4). Tables here copy the layouts of real CIL / Ministry of Coal
documents (monthly statistics, annual report, coal inventory). No database, no LLM."""

import pytest

from app.models.enums import Metric, PeriodType
from worker.extract import facts_from_table


def by_key(facts):
    return {(f.metric, f.subsidiary or f.state, f.period, f.category): f for f in facts}


def test_subsidiary_by_year_table_with_unit_in_title():
    rows = [
        ["Subsidiary", "2022-23", "2023-24"],
        ["MCL", "193.25", "204.62"],
        ["SECL", "167.00", "186.94"],
        ["CIL", "703.21", "773.81"],
    ]
    boxes = [
        [[0, r * 10, 50, r * 10 + 10], None, [100, r * 10, 150, r * 10 + 10]] for r in range(4)
    ]
    facts = facts_from_table(
        rows,
        title="Subsidiary-wise coal production (in million tonnes)",
        cell_bboxes=boxes,
        table_bbox=[0, 0, 150, 40],
    )
    assert len(facts) == 6
    f = by_key(facts)[(Metric.COAL_PRODUCTION, "MCL", "FY 2023-24", None)]
    assert (f.value, f.value_raw, f.unit, f.value_std) == (204.62, "204.62", "MT", 204.62)
    assert f.period_type == PeriodType.FY
    assert f.confidence == 1.0
    assert f.bbox == [100, 10, 150, 20]  # the exact cell
    # A cell without its own box falls back to the table's box.
    assert by_key(facts)[(Metric.COAL_PRODUCTION, "MCL", "FY 2022-23", None)].bbox == [
        0,
        0,
        150,
        40,
    ]


@pytest.mark.parametrize(
    "unit_text, factor",
    [("Lakh Tonnes", 0.1), ("'000 tonnes", 0.001), ("Tonnes", 1e-6), ("Mill. Te.", 1)],
)
def test_units_are_converted_to_mt_and_original_kept(unit_text, factor):
    rows = [["Company", "2023-24"], ["NCL", "1,357.50"]]
    (f,) = facts_from_table(rows, title=f"Coal Offtake ({unit_text})")
    assert f.metric == Metric.COAL_OFFTAKE
    assert f.value == 1357.5
    assert f.value_std == pytest.approx(1357.5 * factor)
    assert f.unit is not None


def test_missing_unit_is_guessed_and_halves_confidence():
    rows = [["Subsidiary", "2023-24"], ["WCL", "62.9"]]
    (f,) = facts_from_table(rows, title="Coal production", ocr_confidence=0.9)
    assert f.unit is None  # not stated in the source
    assert f.value_std == 62.9  # assumed to be MT
    assert f.confidence == pytest.approx(0.45)  # 0.9 OCR x 1.0 mapping x 0.5 guessed unit


def test_monthly_statistics_layout():
    """Merged header cells, sub-headers leaking into the first data row, a serial column,
    target / achievement % / growth columns, and cumulative "upto" columns."""
    rows = [
        ["Sl No", "Subs", "Monthly\nTarget", "Production during Dec", None, None, None,
         "Production upto Dec", None, None],
        ["1", "ECL", "5.43", "FY 25\n5.06", "Achmt.(%)\n93.17", "FY 24\n4.62",
         "Growth (%)\n▲ 9.43", "FY 25\n33.82", "FY 24\n30.01", "Growth (%)\n▲ 12.68"],
        ["2", "BCCL", "4.01", "3.55", "88.43", "3.63", "▼ 2.37", "29.07", "29.83", "▼ 2.58"],
        ["CIL", None, "77.37", "72.37", "93.54", "71.89", "▲ 0.66", "543.36", "532.05", "▲ 2.13"],
        ["10 Captives/Others", None, "13.13", "18.89", "143.87", "14.62", "▲ 29.19", "136.12",
         "102.76", "▲ 32.46"],
    ]  # fmt: skip
    facts = by_key(facts_from_table(rows, title="Coal Production Fig. in MT"))
    assert facts[(Metric.COAL_PRODUCTION, "ECL", "2024-12", None)].value == 5.06
    assert facts[(Metric.COAL_PRODUCTION, "ECL", "2023-12", None)].value == 4.62  # FY 24 Dec
    assert facts[(Metric.COAL_PRODUCTION, "BCCL", "2024-12", None)].value == 3.55
    assert facts[(Metric.COAL_PRODUCTION, "CIL", "2024-12", None)].value == 72.37
    assert facts[(Metric.COAL_PRODUCTION, "CAPTIVE", "2024-12", None)].value == 18.89
    assert facts[(Metric.PRODUCTION_TARGET, "ECL", None, None)].value == 5.43
    values = {f.value for f in facts.values()}
    assert not values & {93.17, 88.43, 33.82, 543.36, 1.0, 2.0}  # %, cumulative, serial no.
    assert len(facts) == 4 * 3


def test_text_only_subheader_in_first_row_marks_the_column():
    rows = [
        ["Subs", "Coking coal during Dec", None, None],
        ["BCCL", "FY 25\n3.41", "Achmt.(%)", "FY 24\n3.44"],
        ["CCL", "1.79", "67.3", "1.90"],
    ]
    facts = facts_from_table(rows, title="Coking Coal Production Fig. in MT")
    assert {f.value for f in facts} == {3.41, 3.44, 1.79, 1.90}
    assert {f.metric for f in facts} == {Metric.COKING_COAL_PRODUCTION}


def test_mine_rows_and_their_total_are_skipped_but_overall_rows_kept():
    rows = [
        ["Sr. No", "Subsidiary", "Mines", "Prod. during Dec'24 (MT)"],
        ["1", "ECL", "RAJMAHAL OC", "1.63"],
        ["2", "ECL", "SONEPUR BAZARI OC", "1.23"],
        ["3", "NCL", "JAYANT OC MINE", "2.76"],
        ["Total", None, None, "5.62"],
    ]
    assert facts_from_table(rows, title="Top 35 Mines Production") == []

    rows = [
        ["Subs", "Types of Mines", "No of Mines", "During Dec FY 25"],
        ["ECL", "Top 35", "2", "2.86"],
        [None, "Rest", "68", "1.49"],
        ["Overall ECL", None, "75", "5.06"],
        ["Overall BCCL", None, "32", "3.55"],
        ["Overall CCL", None, "40", "8.08"],
    ]
    facts = facts_from_table(rows, title="Coal Production in mines of all Subsidiaries of CIL (MT)")
    assert {(f.subsidiary, f.value) for f in facts} == {
        ("ECL", 5.06),
        ("BCCL", 3.55),
        ("CCL", 8.08),
    }


def test_transposed_table_years_down_subsidiaries_across():
    rows = [
        ["Year", "ECL", "BCCL", "Total"],
        ["2022-23", "35.80", "36.46", "72.26"],
        ["2023-24", "47.60", "40.51", "88.11"],
    ]
    facts = by_key(facts_from_table(rows, title="Coal production (MT)"))
    assert facts[(Metric.COAL_PRODUCTION, "BCCL", "FY 2023-24", None)].value == 40.51
    # Only CIL subsidiaries listed, so "Total" is CIL.
    assert facts[(Metric.COAL_PRODUCTION, "CIL", "FY 2023-24", None)].value == 88.11


def test_grand_total_with_sccl_and_captives_is_all_india():
    rows = [
        ["Company", "Dec'24"],
        ["CIL", "68.41"],
        ["SCCL", "5.79"],
        ["Captives", "18.25"],
        ["Grand Total", "92.45"],
    ]
    facts = by_key(facts_from_table(rows, title="Coal Despatch Fig. in MT"))
    assert facts[(Metric.COAL_OFFTAKE, "INDIA", "2024-12", None)].value == 92.45
    assert facts[(Metric.COAL_OFFTAKE, "CAPTIVE", "2024-12", None)].value == 18.25


def test_state_wise_resources_with_categories_and_as_on_date():
    rows = [
        ["State", "Measured (331)", "Indicated (332)", "Inferred (333)", "Resource"],
        ["ODISHA", "53799.43", "39053.01", "6351.39", "99203.83"],
        ["JHARKHAND", "59876.88", "27135.39", "4799.30", "91811.57"],
        ["Total", "212207.16", "148716.53", "28497.65", "389421.34"],
    ]
    title = (
        "STATE-WISE GEOLOGICAL RESOURCES OF COAL IN INDIA AS ON 01.04.2024 "
        "(Resource in million tonnes)"
    )
    facts = by_key(facts_from_table(rows, title=title))
    f = facts[(Metric.COAL_RESOURCE, "Odisha", "2024-04", "Measured")]
    assert (f.value_std, f.state, f.subsidiary, f.period_type) == (
        53799.43,
        "Odisha",
        None,
        PeriodType.MONTH,
    )
    assert facts[(Metric.COAL_RESOURCE, "Jharkhand", "2024-04", None)].value == 91811.57
    assert facts[(Metric.COAL_RESOURCE, "INDIA", "2024-04", "Inferred")].value == 28497.65
    assert len(facts) == 12


def test_resource_breakdowns_we_cannot_store_are_skipped():
    """Coal grades and depth ranges have no column in facts, so they (and a total of them
    alone) are not stored. "Proved" is read as Measured; dates in row labels are periods."""
    grades = [
        ["Coal Type", "Proved", "Indicated", "Inferred", "Total"],
        ["Prime Coking", "5132.65", "310.76", "0.00", "5443.41"],
        ["Non-Coking", "188542.55", "136794.29", "25609.33", "350946.17"],
        ["Grand Total", "212207.16", "148716.53", "28497.65", "389421.34"],
    ]
    assert facts_from_table(grades, title="Coal resources (million tonnes)") == []
    depth = [["Depth Range (m)", "Proved", "Total"], ["0-300", "140920.59", "206277.11"]]
    assert facts_from_table(depth, title="Coal resources (million tonnes)") == []

    dated = [
        ["Inventory as on", "Proved", "Indicated", "Total"],
        ["1st April 2024", "212207.16", "148716.53", "389421.34"],
        ["1st April 2023", "199903.90", "151682.06", "378207.28"],
        ["Difference", "12303.26", "-2965.53", "11214.06"],
    ]
    facts = by_key(facts_from_table(dated, title="(Resource in million tonnes)"))
    assert facts[(Metric.COAL_RESOURCE, None, "2023-04", "Measured")].value == 199903.90
    assert len(facts) == 6  # the "Difference" row is not a fact


def test_lignite_tables_are_not_coal():
    rows = [["State", "Measured (331)"], ["Tamilnadu", "5476.00"], ["Rajasthan", "1203.85"]]
    assert facts_from_table(rows, title="Lignite resources (million tonnes)") == []


def test_rows_as_metrics_with_subsidiary_in_title():
    rows = [
        ["Particulars", "2022-23", "2023-24"],
        ["Coal Production (MT)", "193.25", "204.62"],
        ["Coal Offtake (MT)", "195.49", "207.53"],
        ["OB Removal (M.Cum)", "210.3", "236.8"],
        ["OB Removal (Lakh cum)", "2103", "2368"],
    ]
    facts = facts_from_table(rows, title="Performance of Mahanadi Coalfields Limited")
    assert {f.subsidiary for f in facts} == {"MCL"}
    got = {(f.metric, f.period, f.value_std) for f in facts}
    assert (Metric.COAL_OFFTAKE, "FY 2023-24", 207.53) in got
    assert (Metric.OB_REMOVAL, "FY 2022-23", 210.3) in got
    # The same OB figure in lakh cum and in Mcum is one fact, not a conflict.
    ob_2023 = [f for f in facts if f.metric == Metric.OB_REMOVAL and f.period == "FY 2023-24"]
    assert len(ob_2023) == 1 and ob_2023[0].value_std == 236.8


def test_target_actual_coking_and_non_coking_columns():
    rows = [
        ["Subsidiary", "Target 2024-25", "Actual 2024-25", "Coking", "Non-Coking"],
        ["BCCL", "45.00", "40.51", "34.10", "6.41"],
    ]
    facts = by_key(facts_from_table(rows, title="Coal production (MT)"))
    assert facts[(Metric.PRODUCTION_TARGET, "BCCL", "FY 2024-25", None)].value == 45.0
    assert facts[(Metric.COAL_PRODUCTION, "BCCL", "FY 2024-25", None)].value == 40.51
    assert facts[(Metric.COKING_COAL_PRODUCTION, "BCCL", None, None)].value == 34.10
    assert 6.41 not in {f.value for f in facts.values()}  # non-coking is not one of our metrics


def test_projected_and_range_periods_are_skipped():
    rows = [
        ["Subsidiary", "2023-24 Actual", "2024-25 (Apr'24-Nov'24) (Prov.)", "2024-25 (Proj.)"],
        ["NCL", "136.15", "88.10", "140.00"],
    ]
    (f,) = facts_from_table(rows, title="Coal production (MT)")
    assert (f.value, f.period) == (136.15, "FY 2023-24")


def test_annual_target_in_a_monthly_report_gets_the_financial_year():
    rows = [
        ["Subsidiary", "Annual Target (MT)", "Prod. during Dec'24 (MT)"],
        ["NCL", "139", "12.70"],
    ]
    facts = by_key(facts_from_table(rows, title="Coal production during Dec'2024"))
    assert facts[(Metric.PRODUCTION_TARGET, "NCL", "FY 2024-25", None)].value == 139
    assert facts[(Metric.COAL_PRODUCTION, "NCL", "2024-12", None)].value == 12.70


def test_same_fact_twice_with_different_values_is_dropped():
    """Rail / Road / MGR columns whose header was not read: all look like 'offtake Dec'24'."""
    rows = [
        ["Company\nECL", "Dec'24\n2.92", "Dec'24\n0.34", "Dec'24\n1.13", "Dec'24\n4.38"],
        ["BCCL", "2.68", "0.76", "0.00", "3.45"],
    ]
    assert facts_from_table(rows, title="CIL Offtake in MT") == []


def test_overburden_in_tonnes_keeps_value_but_no_standard_value():
    rows = [["Subsidiary", "OB removal 2023-24 (tonnes)"], ["SECL", "5000"]]
    (f,) = facts_from_table(rows, title="")
    assert (f.metric, f.unit, f.value_std) == (Metric.OB_REMOVAL, "Tonnes", None)


def test_column_number_row_and_money_columns_are_ignored():
    rows = [
        ["Subsidiary", "Production 2023-24 (MT)", "Royalty 2023-24 (Rs. Cr.)"],
        ["1", "2", "3"],
        ["MCL", "204.62", "3,410.55"],
    ]
    (f,) = facts_from_table(rows)
    assert (f.subsidiary, f.value) == ("MCL", 204.62)


def test_hindi_table():
    rows = [["कंपनी", "२०२३-२४"], ["MCL", "२०४.६२"], ["कोल इंडिया", "७७३.८१"]]
    facts = by_key(facts_from_table(rows, title="कोयला उत्पादन (मिलियन टन)"))
    assert facts[(Metric.COAL_PRODUCTION, "MCL", "FY 2023-24", None)].value == 204.62
    assert facts[(Metric.COAL_PRODUCTION, "CIL", "FY 2023-24", None)].unit == "MT"


def test_llm_names_the_metric_only_when_rules_find_none():
    calls = []

    def classify(title, headers, rows):
        calls.append(rows)
        return Metric.COAL_IMPORT

    rows = [["Year", "Quantity (MT)"], ["2022-23", "237.67"], ["2023-24", "264.53"]]
    facts = facts_from_table(rows, title="Table 4", classify=classify)
    assert calls == [["2022-23", "2023-24"]]  # row labels only; no numbers are sent
    assert {f.metric for f in facts} == {Metric.COAL_IMPORT}
    assert {f.confidence for f in facts} == {0.8}

    calls.clear()
    facts_from_table(rows, title="Coal import", classify=classify)
    assert calls == []  # the rules already know the metric


def test_llm_answer_none_means_no_facts():
    rows = [["Year", "Quantity (MT)"], ["2023-24", "264.53"]]
    assert facts_from_table(rows, title="Table 4", classify=lambda *_: None) == []


def test_ask_llm_validates_the_answer(monkeypatch):
    from worker import extract

    class FakeResponse:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": self.content}}

    extract._ask_llm.cache_clear()
    monkeypatch.setattr(
        extract.httpx, "post", lambda *a, **k: FakeResponse('{"metric": "ob_removal"}')
    )
    assert extract._ask_llm("t", ("h",), ("r",)) == Metric.OB_REMOVAL

    extract._ask_llm.cache_clear()
    monkeypatch.setattr(extract.httpx, "post", lambda *a, **k: FakeResponse('{"metric": "gold"}'))
    assert extract._ask_llm("t", ("h",), ("r",)) is None  # not one of our metrics
    extract._ask_llm.cache_clear()
