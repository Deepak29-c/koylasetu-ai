"""Map screen (#97): which facts it may use, and which one it shows per place."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.core.db import get_db
from app.main import app
from app.models.enums import FactStatus, Metric, PeriodType
from app.services.map_figures import base_statement, pick

HQ = SimpleNamespace(org_unit=SimpleNamespace(code="CIL_HQ"), org_unit_id=None)
UNIT = SimpleNamespace(org_unit=SimpleNamespace(code="MCL"), org_unit_id=uuid.uuid4())


def sql(metric: Metric, category: str | None = None, user=HQ) -> str:
    stmt = base_statement(metric, category, user)
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def fact(place: str, period: str | None, value: float, status=FactStatus.EXTRACTED, conf=0.9):
    return SimpleNamespace(
        id=uuid.uuid4(),
        state=place,
        subsidiary=place,
        period=period,
        period_type=PeriodType.MONTH,
        value_std=value,
        value_raw=str(value),
        unit="MT",
        status=status,
        confidence=conf,
        document_id=uuid.uuid4(),
        page_no=3,
    )


def test_never_uses_rejected_unconverted_or_undated_facts():
    q = sql(Metric.COAL_PRODUCTION)
    assert "facts.status != 'REJECTED'" in q
    assert "facts.value_std IS NOT NULL" in q
    assert "facts.period IS NOT NULL" in q
    assert "IS DISTINCT FROM 'YTD'" in q


def test_resources_are_by_state_and_total_has_no_category():
    q = sql(Metric.COAL_RESOURCE)
    assert "facts.state IS NOT NULL" in q and "facts.category IS NULL" in q
    assert "facts.category LIKE 'Measured%" in sql(Metric.COAL_RESOURCE, "Measured")


def test_production_is_by_subsidiary_without_totals():
    q = sql(Metric.COAL_OFFTAKE)
    assert "'MCL'" in q and "'SCCL'" in q
    assert "'CIL'" not in q and "'INDIA'" not in q and "'CAPTIVE'" not in q


def test_scoped_to_the_users_unit():
    assert "documents.org_unit_id" not in sql(Metric.COAL_PRODUCTION)
    assert "documents.org_unit_id" in sql(Metric.COAL_PRODUCTION, user=UNIT)


def test_latest_period_by_default_and_asked_period_when_it_exists():
    rows = [(fact("MCL", "2023-12", 10), "A"), (fact("MCL", "2024-12", 12), "A")]
    shown, periods, chosen = pick(rows, Metric.COAL_PRODUCTION, None)
    assert shown == "2024-12" and periods == ["2024-12", "2023-12"]
    assert [f.value_std for f, _ in chosen] == [12]
    assert pick(rows, Metric.COAL_PRODUCTION, "2023-12")[0] == "2023-12"
    # A period with no figures falls back to the newest rather than showing an empty map
    assert pick(rows, Metric.COAL_PRODUCTION, "2019-01")[0] == "2024-12"


def test_verified_wins_then_higher_confidence():
    flagged = fact("Odisha", "2024-04", 100975.78, FactStatus.FLAGGED, conf=0.99)
    verified = fact("Odisha", "2024-04", 99203.83, FactStatus.VERIFIED, conf=0.5)
    _, _, chosen = pick([(flagged, "B"), (verified, "A")], Metric.COAL_RESOURCE, None)
    assert [(f.value_std, t) for f, t in chosen] == [(99203.83, "A")]

    low, high = fact("MCL", "2024-12", 1, conf=0.4), fact("MCL", "2024-12", 2, conf=0.8)
    assert pick([(low, "A"), (high, "A")], Metric.COAL_PRODUCTION, None)[2][0][0] is high


def test_no_figures():
    assert pick([], Metric.COAL_RESOURCE, None) == (None, [], [])


class StubSession:
    """Answers the facts query with these rows; the depth query (resources) finds none."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, stmt):
        rows = [] if "depth_resources" in str(stmt) else self.rows
        return SimpleNamespace(all=lambda: rows)


def test_needs_login():
    assert TestClient(app).get("/map/figures").status_code == 401


@pytest.mark.parametrize("role", ["viewer", "analyst", "operator"])
def test_api_returns_one_item_per_place(client_as, role):
    client = client_as([role], "CIL_HQ")
    rows = [
        (fact("Odisha", "2024-04", 99203.83, FactStatus.VERIFIED), "Inventory"),
        (fact("Jharkhand", "2024-04", 91811.57, FactStatus.VERIFIED), "Inventory"),
    ]
    app.dependency_overrides[get_db] = lambda: StubSession(rows)
    res = client.get("/map/figures", params={"metric": "coal_resource"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["level"] == "state" and body["period"] == "2024-04"
    assert body["period_type"] == "MONTH" and body["unit"] == "MT"
    assert [i["key"] for i in body["items"]] == ["Odisha", "Jharkhand"]
    assert body["items"][0]["document_title"] == "Inventory"


def test_category_is_ignored_for_production(client_as):
    client = client_as(["viewer"], "CIL_HQ")
    app.dependency_overrides[get_db] = lambda: StubSession([])
    res = client.get("/map/figures", params={"metric": "coal_production", "category": "Measured"})
    assert res.status_code == 200
    assert res.json() == {
        "metric": "coal_production",
        "level": "subsidiary",
        "unit": "MT",
        "category": None,
        "period": None,
        "period_type": None,
        "periods": [],
        "depth": None,
        "depths": [],
        "items": [],
    }


def test_unknown_metric_is_rejected(client_as):
    client = client_as(["viewer"], "CIL_HQ")
    assert client.get("/map/figures", params={"metric": "ob_removal"}).status_code == 422
