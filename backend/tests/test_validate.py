"""Validation rules V01-V08, run on facts from the real extractor (worker/extract.py)."""

import copy
import uuid
from dataclasses import replace

from app.models.enums import Metric, PeriodType
from worker.extract import facts_from_table
from worker.validate import Other, key, validate

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
TITLE = "FY 25 FY 24 Fig. in MT Coal Production"


def production(rows=None, title=TITLE):
    """Monthly production facts (the target column has no single period in this title)."""
    facts = facts_from_table([HEADER, *copy.deepcopy(rows or ROWS)], title=title)
    return [f for f in facts if f.metric == Metric.COAL_PRODUCTION]


def rules(issues):
    return sorted({i.rule for i in issues})


def find(facts, **kw):
    return [f for f in facts if all(getattr(f, k) == v for k, v in kw.items())]


def test_clean_table_passes_every_rule():
    facts = production()
    assert len(facts) == 18  # 9 rows x (Dec 2024, Dec 2023)
    assert validate(facts, []) == []


def test_v01_subsidiaries_must_add_up_to_cil():
    rows = copy.deepcopy(ROWS)
    rows[3][3] = "13.70"  # NCL one tonne higher than printed
    issues = [i for i in validate(production(rows), []) if i.rule == "V01"]
    assert len(issues) == 1
    assert "72.37" in issues[0].message and "73.38" in issues[0].message


def test_v01_states_must_add_up_to_india():
    def resource(state, subsidiary, value):
        return replace(production()[0], metric=Metric.COAL_RESOURCE, subsidiary=subsidiary,
                       state=state, category="Measured", period_type=PeriodType.FY,
                       period="FY 2024-25", value_std=value)  # fmt: skip

    facts = [
        resource("Odisha", None, 55009.74),
        resource("Jharkhand", None, 60290.47),
        resource("Chhattisgarh", None, 45462.69),
        resource(None, "INDIA", 160762.90),
    ]
    assert "V01" not in rules(validate(facts, []))
    facts[-1] = replace(facts[-1], value_std=170762.90)
    assert "V01" in rules(validate(facts, []))


def test_v02_conflict_with_another_document():
    facts = production()
    (ncl,) = find(facts, subsidiary="NCL", period_type=PeriodType.MONTH, period="2024-12")
    other = Other(uuid.uuid4(), key(ncl), 12.10, "PIB release")
    issues = [i for i in validate(facts, [other]) if i.rule == "V02"]
    assert len(issues) == 1 and issues[0].related_fact_id == other.id


def test_v03_negative_and_impossible():
    facts = production()
    facts[0] = replace(facts[0], value_std=-3.0)
    facts[1] = replace(facts[1], value_std=1610.2)  # a decimal slipped
    assert [i.fact for i in validate(facts, []) if i.rule == "V03"] == [0, 1]


def test_v03_ignores_resources_and_all_india():
    f = replace(production()[0], metric=Metric.COAL_RESOURCE, value_std=400715.45)
    india = replace(production()[0], subsidiary="INDIA", value_std=1600.0)
    assert "V03" not in rules(validate([f, india], []))


def test_v04_v05_unit_not_stated():
    facts = production(title="FY 25 FY 24 Coal Production")  # no "in MT" anywhere
    assert facts and all(f.unit is None for f in facts)
    assert {"V04", "V05"} <= set(rules(validate(facts, [])))


def test_v04_unit_that_cannot_be_converted():
    f = replace(production()[0], unit="Rs crore", value_std=None)
    assert rules(validate([f], [])) == ["V04"]


def test_v06_year_on_year_jump():
    rows = copy.deepcopy(ROWS)
    rows[3][3] = "1.27"  # NCL 12.70 typed as 1.27: -89 % vs Dec 2023
    assert "V06" in rules(validate(production(rows), []))


def test_v07_duplicate_in_same_document():
    facts = production()
    assert rules(validate(facts + facts[:1], [])) == ["V07"]


def test_v08_period_unknown():
    facts = facts_from_table([HEADER, *ROWS], title=TITLE)
    targets = [i for i, f in enumerate(facts) if f.metric == Metric.PRODUCTION_TARGET]
    v08 = [i.fact for i in validate(facts, []) if i.rule == "V08"]
    assert targets and v08 == targets  # "Monthly Target" under two FYs has no single period


def test_facts_without_a_period_are_only_v08():
    # "Monthly Target" and "Annual Target" of the same company, neither with a period
    a = replace(production()[0], metric=Metric.PRODUCTION_TARGET, period_type=None, period=None)
    b = replace(a, value_std=a.value_std * 10)
    other = Other(uuid.uuid4(), key(a), 999.0, "Another report")
    assert rules(validate([a, b], [other])) == ["V08"]
