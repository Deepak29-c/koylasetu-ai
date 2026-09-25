"""Metrics screen: who may open it, and how the benchmark summary is read."""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.metrics import latest_benchmark
from app.core.db import get_db
from app.main import app

COUNT = 4


class StubSession:
    """Every count (and the average latency) comes back as the same number."""

    def scalar(self, _stmt) -> int:
        return COUNT


@pytest.fixture
def metrics_as(client_as, tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_RESULTS_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    def make(roles: list[str]):
        client = client_as(roles, "CIL_HQ")
        app.dependency_overrides[get_db] = StubSession
        return client.get("/metrics")

    yield make
    get_settings.cache_clear()


def test_needs_login():
    assert TestClient(app).get("/metrics").status_code == 401


@pytest.mark.parametrize("role", ["admin", "approver"])
def test_admin_and_approver_can_open_it(metrics_as, role):
    res = metrics_as([role])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["qa"]["questions_total"] == COUNT
    assert body["qa"]["grounded_pct"] == 100.0
    assert body["facts"]["automation_pct"] == 100.0
    assert body["reports"]["total"] == COUNT
    assert body["benchmark"] is None  # no run in the empty results folder


@pytest.mark.parametrize("role", ["operator", "reviewer", "analyst", "viewer"])
def test_other_roles_cannot(metrics_as, role):
    assert metrics_as([role]).status_code == 403


def test_latest_run_wins(tmp_path):
    for day, accuracy in (("2026-09-20", 61.0), ("2026-09-26", 74.5)):
        run = tmp_path / day
        run.mkdir()
        (run / "summary.json").write_text(
            json.dumps(
                {
                    "run_date": day,
                    "questions_asked": 30,
                    "answered": 27,
                    "not_found": 2,
                    "errors": 1,
                    "numeric_accuracy_pct": accuracy,
                    "grounded_pct": 88.9,
                    "all_correct_pct": 50.0,
                    "latency_ms": {"p50": 4210.4, "avg": 5000, "max": 9000},
                    "time_saved": {"trials": 5, "pct": 71.2},
                    "citations": {"checked": 40, "correct": 38, "pct": 95.0},
                }
            ),
            encoding="utf-8",
        )
    b = latest_benchmark(tmp_path)
    assert b is not None
    assert b.run_date == "2026-09-26"
    assert b.numeric_accuracy_pct == 74.5
    assert b.median_latency_ms == 4210
    assert b.time_saved_pct == 71.2
    assert b.citation_correct_pct == 95.0
    assert b.automation_pct is None  # not measured in this run


def test_missing_or_broken_results_are_not_an_error(tmp_path):
    assert latest_benchmark(tmp_path / "does-not-exist") is None
    run = tmp_path / "2026-09-26"
    run.mkdir()
    (run / "summary.json").write_text("{not json", encoding="utf-8")
    assert latest_benchmark(tmp_path) is None


def test_a_later_run_on_the_same_day_wins(tmp_path):
    for name, accuracy in (("2026-09-26-2", 50.0), ("2026-09-26-10", 80.0), ("2026-09-26", 10.0)):
        run = tmp_path / name
        run.mkdir()
        (run / "summary.json").write_text(
            json.dumps({"run_date": "2026-09-26", "numeric_accuracy_pct": accuracy}),
            encoding="utf-8",
        )
    assert latest_benchmark(tmp_path).numeric_accuracy_pct == 80.0


def test_relative_results_dir_is_resolved_from_the_repo():
    from app.api.metrics import REPO_ROOT, results_dir

    assert results_dir("../eval/results") == (REPO_ROOT / "eval" / "results").resolve()
