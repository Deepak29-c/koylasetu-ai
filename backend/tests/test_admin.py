"""Admin screens: validation rules, report templates and system status (guide W8)."""

import re
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.db import get_db
from app.main import app
from app.models.enums import DocumentStatus
from app.services import briefing_note, monthly_report, report_templates, system_status
from tests.conftest import fake_user
from worker.validate import RULES

HEAD = system_status.migration_head()
ADMIN = fake_user(["admin"], "CIL_HQ")


class StubResult(list):
    def all(self):
        return list(self)


class StubSession:
    """Answers SELECT 1, the alembic version and the grouped counts; `down` fails them all."""

    def __init__(self, rows=(), version=HEAD, down=False):
        self.rows, self.version, self.down = list(rows), version, down

    def execute(self, stmt):
        if self.down:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))
        return StubResult(self.rows)

    def scalars(self, stmt):
        return [self.version] if self.version else []

    def rollback(self):
        pass


@pytest.fixture
def admin_as(client_as):
    def make(roles=("admin",), session=None):
        client = client_as(list(roles), "CIL_HQ")
        app.dependency_overrides[get_db] = lambda: session or StubSession()
        return client

    return make


@pytest.mark.parametrize("path", ["/admin/rules", "/admin/templates", "/admin/status"])
def test_needs_login(path):
    assert TestClient(app).get(path).status_code == 401


@pytest.mark.parametrize("path", ["/admin/rules", "/admin/templates", "/admin/status"])
@pytest.mark.parametrize("role", ["operator", "reviewer", "analyst", "approver", "viewer"])
def test_only_admin(admin_as, path, role):
    assert admin_as([role]).get(path).status_code == 403


# --- rules ---------------------------------------------------------------------------------------


def test_rules_come_from_the_registry_with_open_counts(admin_as):
    res = admin_as(session=StubSession(rows=[("V01", 3), ("V05", 7)])).get("/admin/rules")
    assert res.status_code == 200, res.text
    body = res.json()
    assert [r["code"] for r in body] == [f"V0{i}" for i in range(1, 9)]
    counts = {r["code"]: r["open_issues"] for r in body}
    assert counts["V01"] == 3 and counts["V05"] == 7 and counts["V02"] == 0
    v03 = next(r for r in body if r["code"] == "V03")
    assert v03["thresholds"] == [{"key": "max_subsidiary_mt", "value": 1500, "unit": "MT"}]
    assert next(r for r in body if r["code"] == "V07")["severities"] == ["low", "high"]


def test_registry_lists_every_rule_the_code_raises():
    """A rule added to validate.py but not to RULES would never run; this catches it."""
    source = (Path(__file__).resolve().parents[1] / "worker" / "validate.py").read_text("utf-8")
    raised = set(re.findall(r'Issue\(\s*[\w\[\]]+,\s*"(V\d\d)"', source))
    assert raised == {r.code for r in RULES}


# --- templates -----------------------------------------------------------------------------------


def test_templates_list_the_three_generators(admin_as):
    res = admin_as().get("/admin/templates")
    assert res.status_code == 200, res.text
    body = {t["report_type"]: t for t in res.json()}
    assert set(body) == {"pq_reply", "monthly", "briefing"}
    monthly = {s["key"]: s for s in body["monthly"]["sections"]}
    assert monthly["production"]["columns"][:3] == ["Subsidiary", "Target (MT)", "Actual (MT)"]
    assert "All India" in monthly["production"]["rows"]
    assert body["pq_reply"]["generator"] == "app.services.pq_reply"


def _by_key(template_type: str) -> dict:
    (t,) = [t for t in report_templates.templates() if t.report_type.value == template_type]
    return {s.key: s for s in t.sections if s.kind != "sources"}


def test_monthly_template_matches_a_real_draft():
    draft = monthly_report.build_content([], "2024-12").content
    sections = {s["id"]: s for s in draft["sections"]}
    template = _by_key("monthly")
    assert list(sections) == list(template)
    for key, s in sections.items():
        assert s["heading"] == template[key].heading
        if s["table"]:
            assert len(s["table"]["columns"]) == len(template[key].columns)
            assert [r[0] for r in s["table"]["rows"]] == list(template[key].rows)


def test_briefing_template_matches_a_real_draft():
    none = SimpleNamespace(not_found=True, answer="")
    draft = briefing_note.build_content("coal production", [], none, none).content
    template = _by_key("briefing")
    for s in draft["sections"]:
        assert s["id"] in template
        assert s["heading"].startswith(template[s["id"]].heading)


# --- status --------------------------------------------------------------------------------------


def _settings(**kw) -> Settings:
    return Settings(
        storage_dir=str(Path(__file__).parent),
        llm_model="qwen2.5:3b-instruct",
        embed_model="bge-m3",
        **kw,
    )


class FakeQueue:
    def __init__(self, name, connection):
        self.name, self.count = name, 2
        self.failed_job_registry = SimpleNamespace(count=1 if name == "ingest" else 0)


def healthy(monkeypatch):
    monkeypatch.setattr(system_status, "redis_connection", lambda url: SimpleNamespace(ping=bool))
    monkeypatch.setattr(system_status, "Queue", FakeQueue)
    monkeypatch.setattr(system_status, "Worker", SimpleNamespace(count=lambda connection: 1))
    tags = {"models": [{"name": "qwen2.5:3b-instruct"}, {"name": "bge-m3:latest"}]}
    monkeypatch.setattr(system_status, "fetch_tags", lambda base: httpx.Response(200, json=tags))


def by_key(status) -> dict:
    return {c.key: c for c in status.checks}


def test_everything_up(monkeypatch):
    healthy(monkeypatch)
    rows = [(DocumentStatus.PROCESSED, 5)]
    status = system_status.collect(StubSession(rows=rows), ADMIN, _settings())
    checks = by_key(status)
    assert checks["database"].status == "ok"
    assert checks["migrations"].status == "ok"
    assert checks["worker"].status == "ok"
    assert checks["redis"].status == "warn"  # one failed ingest job
    assert checks["models"].status == "ok"
    assert [q.name for q in status.queues] == ["ingest", "topics", "reports"]
    assert status.documents["PROCESSED"] == 5 and status.documents["FAILED"] == 0
    assert all(m.pulled for m in status.models)


def test_redis_down_is_an_error_not_an_exception(monkeypatch):
    healthy(monkeypatch)

    def refuse(url):
        raise RedisConnectionError("connection refused")

    monkeypatch.setattr(system_status, "redis_connection", refuse)
    checks = by_key(system_status.collect(StubSession(), ADMIN, _settings()))
    assert checks["redis"].status == "error" and checks["redis"].code == "unreachable"
    assert checks["worker"].status == "error"


def test_redis_not_checked_when_jobs_run_inline(monkeypatch):
    healthy(monkeypatch)
    monkeypatch.setattr(system_status, "redis_connection", lambda url: 1 / 0)
    checks = by_key(system_status.collect(StubSession(), ADMIN, _settings(ingest_inline=True)))
    assert checks["redis"].code == "not_used" and "worker" not in checks


def test_model_server_down_is_a_warning(monkeypatch):
    healthy(monkeypatch)

    def refuse(base):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(system_status, "fetch_tags", refuse)
    status = system_status.collect(StubSession(), ADMIN, _settings())
    assert by_key(status)["model_server"].status == "warn"
    assert [m.pulled for m in status.models] == [None, None]


def test_missing_model_is_named(monkeypatch):
    healthy(monkeypatch)
    only_embed = httpx.Response(200, json={"models": [{"name": "bge-m3:latest"}]})
    monkeypatch.setattr(system_status, "fetch_tags", lambda base: only_embed)
    check = by_key(system_status.collect(StubSession(), ADMIN, _settings()))["models"]
    assert check.status == "warn" and check.details["missing"] == ["qwen2.5:3b-instruct"]


def test_database_down_and_behind(monkeypatch):
    healthy(monkeypatch)
    down = by_key(system_status.collect(StubSession(down=True), ADMIN, _settings()))
    assert down["database"].status == "error" and down["migrations"].status == "error"
    behind = by_key(system_status.collect(StubSession(version="0001"), ADMIN, _settings()))
    assert behind["migrations"].code == "behind"


def test_one_broken_check_does_not_hide_the_others(monkeypatch):
    healthy(monkeypatch)

    def boom(path):
        raise PermissionError("denied")

    monkeypatch.setattr(system_status, "disk_usage", boom)
    status = system_status.collect(StubSession(), ADMIN, _settings())
    checks = by_key(status)
    assert checks["storage"].status == "error" and checks["storage"].code == "check_failed"
    assert checks["database"].status == "ok"
    assert status.overall == "error"


def test_external_calls_flag_warns(monkeypatch):
    healthy(monkeypatch)
    status = system_status.collect(StubSession(), ADMIN, _settings(allow_external_calls=True))
    assert by_key(status)["external_calls"].status == "warn"


def test_status_endpoint_never_500s(admin_as, monkeypatch):
    healthy(monkeypatch)

    def refuse(*_):
        raise RedisConnectionError("down")

    monkeypatch.setattr(system_status, "redis_connection", refuse)
    monkeypatch.setattr(system_status, "fetch_tags", lambda base: 1 / 0)
    res = admin_as(session=StubSession(down=True)).get("/admin/status")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["overall"] == "error"
    assert body["version"] and body["flags"]["ingest_inline"] in (True, False)
    assert {c["key"] for c in body["checks"]} >= {"database", "redis", "model_server", "storage"}
