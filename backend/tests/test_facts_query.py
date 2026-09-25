"""NUMERIC route facts query: follows the extractor's conventions (worker/extract.py)."""

from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.models.enums import Metric
from app.services.facts_query import FactRow, _statement, query_facts
from app.services.router import Filters

HQ = SimpleNamespace(org_unit=SimpleNamespace(code="CIL_HQ"), org_unit_id=None)


def sql(f: Filters) -> str:
    stmt = _statement(f, HQ)
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_national_resource_is_the_india_total_without_category():
    q = sql(Filters(metrics=[Metric.COAL_RESOURCE]))
    assert "facts.subsidiary = 'INDIA'" in q and "facts.category IS NULL" in q


def test_resource_category_and_states():
    q = sql(Filters(metrics=[Metric.COAL_RESOURCE], states=["Odisha"], category="Measured"))
    assert "facts.state IN ('Odisha')" in q and "facts.category LIKE 'Measured%" in q


def test_unconvertible_units_are_never_used():
    assert "facts.value_std IS NOT NULL" in sql(Filters(metrics=[Metric.COAL_PRODUCTION]))


def test_coking_question_never_gets_an_overall_figure():
    def run(_):
        raise AssertionError("must not query")

    f = Filters(metrics=[Metric.COAL_OFFTAKE], coking=True)
    assert query_facts(None, HQ, f, run=run) == []
    f = Filters(metrics=[Metric.COAL_RESOURCE], coking=True)
    assert query_facts(None, HQ, f, run=run) == []
    seen = []
    f = Filters(metrics=[Metric.COKING_COAL_PRODUCTION], coking=True)
    query_facts(None, HQ, f, run=lambda stmt: seen.append(stmt) or [])
    assert len(seen) == 1


def test_resource_month_reads_as_on():
    row = FactRow(
        ref="F1", fact_id=None, metric="coal_resource", subsidiary="INDIA", state=None,
        category=None, period_type="MONTH", period="2025-04", value_raw="400715.45", unit="MT",
        value_std=400715.45, status="VERIFIED", document_id=None, document_title="Inventory",
        page_no=29, bbox=None,
    )  # fmt: skip
    assert row.period_text == "as on Apr 2025"
    assert FactRow(**{**row.__dict__, "metric": "coal_production"}).period_text == "Apr 2025"
