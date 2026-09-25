"""Table -> facts extraction and validation rules V01-V08, on tables shaped like the real ones."""

import copy
import uuid

import pytest

from app.models.enums import Metric, PeriodType
from worker.extract import extract_facts
from worker.parse import Table
from worker.validate import Other, validate

# Shaped like Monthly Coal Statistics Dec 2024, page 1 (values from that document).
HEADER = ["Sl No", "Subs", "Monthly\nTarget", "Production during Dec", "", "", "",
          "Production upto Dec", "", ""]  # fmt: skip
ROWS = [
    ["1", "ECL", "5.43", "FY 25\n5.06", "Achmt.(%)\n93.17", "FY 24\n4.62", "Growth (%)\n▲ 9.43",
     "FY 25\n33.82", "FY 24\n30.01", "Growth (%)\n▲ 12.68"],
    ["2", "BCCL", "4.01", "3.55", "88.43", "3.63", "▼ 2.37", "29.07", "29.83", "▼ 2.58"],
    ["3", "CCL", "9.54", "8.08", "84.66", "7.94", "▲ 1.79", "57.73", "55.77", "▲ 3.51"],
    ["4", "NCL", "12.16", "12.70", "104.44", "11.80", "▲ 7.58", "104.90", "103.90", "▲ 0.96"],
    ["5", "WCL", "7.39", "7.12", "96.33", "7.03", "▲ 1.21", "45.10", "43.59", "▲ 3.47"],
    ["6", "SECL", "18.30", "14.33", "78.32", "16.60", "▼ 13.68", "111.54", "123.28", "▼ 9.52"],
    ["7", "MCL", "20.51", "21.51", "104.86", "20.24", "▲ 6.30", "161.02", "145.54", "▲ 10.64"],
    ["8", "NEC", "0.03", "0.03", "111.11", "0.03", "▲ 11.11", "0.18", "0.12", "▲ 45.53"],
    ["CIL", "", "77.37", "72.37", "93.54", "71.89", "▲ 0.66", "543.36", "532.05", "▲ 2.13"],
]  # fmt: skip
CONTEXT = "FY 25 FY 24 Fig. in MT Coal Production"


def production_table(rows=None, context=CONTEXT, fy="FY 2024-25"):
    rows = copy.deepcopy(rows or ROWS)
    boxes = [
        [[c * 10, r * 10, c * 10 + 9, r * 10 + 9] for c in range(10)] for r in range(len(rows) + 1)
    ]
    return extract_facts(Table([HEADER, *rows], [0, 0, 100, 100], cells=boxes), 1, context, fy)


def find(facts, **kw):
    return [f for f in facts if all(getattr(f, k) == v for k, v in kw.items())]


def test_monthly_statistics_layout():
    facts = production_table()
    (ncl,) = find(facts, subsidiary="NCL", metric=Metric.COAL_PRODUCTION,
                  period_type=PeriodType.MONTH, period="2024-12")  # fmt: skip
    assert (ncl.value_raw, ncl.value_std, ncl.unit, ncl.confidence) == ("12.70", 12.70, "MT", 1.0)
    assert ncl.bbox == [30, 40, 39, 49]  # the exact cell it came from
    (target,) = find(facts, subsidiary="NCL", metric=Metric.PRODUCTION_TARGET)
    assert (target.value_raw, target.period) == ("12.16", "2024-12")
    (ytd_prev,) = find(facts, subsidiary="NCL", period_type=PeriodType.YTD, period="2023-12")
    assert ytd_prev.value_raw == "103.90"


def test_glued_sub_headers_are_split_and_row_label_kept():
    ecl = find(production_table(), subsidiary="ECL", metric=Metric.COAL_PRODUCTION)
    assert {(f.period_type, f.period, f.value_raw) for f in ecl} == {
        (PeriodType.MONTH, "2024-12", "5.06"), (PeriodType.MONTH, "2023-12", "4.62"),
        (PeriodType.YTD, "2024-12", "33.82"), (PeriodType.YTD, "2023-12", "30.01"),
    }  # fmt: skip


def test_percent_and_growth_columns_are_not_facts():
    assert not [f for f in production_table() if f.value_raw in ("93.17", "104.44", "▲ 9.43")]


def test_topic_from_page_text():
    coking = production_table(context="Coking Coal Production Fig. in MT")
    assert {f.metric for f in coking} == {Metric.COKING_COAL_PRODUCTION}  # no coking target metric


def test_lakh_tonnes_are_converted_to_mt():
    f, *_ = find(production_table(context="Coal Production (in Lakh Tonnes)"), subsidiary="NCL")
    assert f.unit.lower().startswith("lakh") and f.value_std == pytest.approx(f.value * 0.1)


def test_missing_unit_is_guessed_and_halves_confidence():
    facts = production_table(context="Coal Production")
    assert all(f.unit_guessed and f.confidence <= 0.5 for f in facts)


def test_state_resource_table_with_stacked_row():
    header = ["State", "Measured\n(331)", "Indicated\n(332)", "Inferred\n(333)", "Resource"]
    rows = [
        ["ODISHA", "55009.74", "38780.51", "7185.53", "100975.78"],
        ["JHARKHAND\nCHHATTISGARH", "60290.47\n45462.69", "27121.64\n38340.18",
         "5841.95\n1460.35", "93254.06\n85263.22"],
        ["Total", "160762.90", "104242.33", "14487.83", "279493.06"],
    ]  # fmt: skip
    facts = extract_facts(
        Table([header, *rows]), 29, "(Resource in million tonne) (As on 01-04-2025)", None
    )
    (chh,) = find(facts, state="CHHATTISGARH", category="Total")
    assert (chh.value_raw, chh.period_type, chh.period) == (
        "85263.22",
        PeriodType.AS_ON,
        "2025-04-01",
    )
    assert find(facts, state="ALL_INDIA", category="Measured")[0].value_std == 160762.90
    assert not validate(facts, [])  # 3 states add up to the total row


def test_mine_wise_tables_are_skipped():
    header = ["Sr. No", "Subsidiary", "Mines", "Prod. during Dec'24 (MT)"]
    assert (
        extract_facts(
            Table([header, ["1", "NCL", "Jayant", "1.5"], ["2", "NCL", "Dudhichua", "2.1"]]),
            10,
            "",
            "FY 2024-25",
        )
        == []
    )


# --- validation -----------------------------------------------------------------------------------


def rules(issues):
    return sorted({i.rule for i in issues})


def test_clean_table_passes_every_rule():
    assert validate(production_table(), []) == []


def test_v01_subsidiaries_must_add_up_to_cil():
    rows = copy.deepcopy(ROWS)
    rows[3][3] = "13.70"  # NCL one tonne higher than printed
    issues = validate(production_table(rows), [])
    assert "V01" in rules(issues)
    (v01,) = [i for i in issues if i.rule == "V01"]
    assert "72.37" in v01.message and "73.38" in v01.message


def test_v02_conflict_with_another_document():
    facts = production_table()
    (ncl,) = find(
        facts,
        subsidiary="NCL",
        metric=Metric.COAL_PRODUCTION,
        period_type=PeriodType.MONTH,
        period="2024-12",
    )
    other = Other(uuid.uuid4(), ncl.key(), 12.10, "PIB release")
    issues = [i for i in validate(facts, [other]) if i.rule == "V02"]
    assert len(issues) == 1 and issues[0].related_fact_id == other.id


def test_v03_negative_and_impossible():
    rows = copy.deepcopy(ROWS)
    rows[0][7] = "(3.00)"  # accounting-style negative
    rows[6][7] = "1610.20"  # a decimal slipped: MCL
    assert {"V03"} <= set(rules(validate(production_table(rows), [])))


def test_v04_v05_unit_and_confidence():
    assert {"V04", "V05"} <= set(rules(validate(production_table(context="Coal Production"), [])))


def test_v06_year_on_year_jump():
    rows = copy.deepcopy(ROWS)
    rows[3][3] = "1.27"  # NCL 12.70 typed as 1.27: -89 % vs Dec 2023
    assert "V06" in rules(validate(production_table(rows), []))


def test_v07_duplicate_in_same_document():
    facts = production_table()
    assert rules(validate(facts + facts[:1], [])) == ["V07"]


def test_v08_period_unknown():
    # No FY anywhere: not in the header, the page, or the document's upload details.
    table = Table([["Subs", "Production during Dec"], ["NCL", "12.70"], ["MCL", "21.51"]])
    facts = extract_facts(table, 1, "Coal Production Fig. in MT", None)
    assert facts and all(f.period is None for f in facts)
    assert "V08" in rules(validate(facts, []))
