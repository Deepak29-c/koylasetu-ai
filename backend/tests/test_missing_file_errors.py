"""A missing original, or any unhandled error, reaches the browser as a readable reply (#69).

Before: `GET /documents/{id}/pages/1` opened the file with no existence check, the
exception escaped every middleware, and the 500 went out without CORS headers. The
browser hid it and the frontend said "Cannot reach the KoylaSetu server".

These run through the real app (middleware and all) with the database faked out.
"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.api import documents
from app.core.db import get_db
from app.main import app

ORIGIN = "http://localhost:3000"
SECRET_PATH = (
    "storage/originals/2c/2cbd2d32057ff5ba80cef0a2916405009aeb62dee9bbf0942cfcf6a212d75ee9.pdf"
)


def fake_doc(file_path: str, mime: str = "application/pdf", **extra) -> SimpleNamespace:
    fields = dict(
        id=uuid.uuid4(),
        title="Coal Directory 2023-24",
        original_filename="directory.pdf",
        doc_type="annual_report",
        fy="FY 2023-24",
        org_unit_id=uuid.uuid4(),
        is_public=False,
        language="en",
        mime_type=mime,
        size_bytes=10,
        status="PROCESSED",
        error_message=None,
        page_count=3,
        pages_done=3,
        source_url=None,
        created_at=datetime.now(UTC),
        file_path=file_path,
    )
    fields.update(extra)
    return SimpleNamespace(**fields)


class FakeDb:
    """Just enough of a Session for get_page: one processed page, no chunks or tables."""

    def scalar(self, _stmt):
        return SimpleNamespace(has_text_layer=True, ocr_used=False, ocr_confidence=None)

    def scalars(self, _stmt):
        return SimpleNamespace(all=lambda: [])


@pytest.fixture
def viewer(client_as, monkeypatch):
    """A logged-in analyst whose document lookup returns `doc` (set by each test)."""
    holder = {}
    monkeypatch.setattr(documents, "_get_scoped", lambda db, document_id, user: holder["doc"])
    client = client_as(["analyst"])
    app.dependency_overrides[get_db] = lambda: FakeDb()
    return client, holder


@pytest.mark.parametrize("suffix", ["", "/image"])
def test_a_missing_original_is_a_handled_404_with_cors(viewer, suffix, tmp_path):
    client, holder = viewer
    holder["doc"] = fake_doc(str(tmp_path / "gone.pdf"))
    res = client.get(f"/documents/{holder['doc'].id}/pages/1{suffix}", headers={"Origin": ORIGIN})
    assert res.status_code == 404
    assert res.headers["access-control-allow-origin"] == ORIGIN
    body = res.json()
    assert body["code"] == "file_missing"
    assert "Coal Directory 2023-24" in body["detail"]  # names the document
    assert "upload it again" in body["detail"]
    assert "gone.pdf" not in body["detail"] and str(tmp_path) not in body["detail"]


@pytest.mark.parametrize("suffix", ["", "/image"])
def test_a_damaged_original_is_a_handled_422(viewer, suffix, tmp_path):
    client, holder = viewer
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"this is not a pdf")
    holder["doc"] = fake_doc(str(broken))
    res = client.get(f"/documents/{holder['doc'].id}/pages/1{suffix}", headers={"Origin": ORIGIN})
    assert res.status_code == 422
    assert res.headers["access-control-allow-origin"] == ORIGIN
    assert res.json()["code"] == "damaged_file"


def test_a_file_type_without_pages_still_opens_even_if_the_file_is_gone(viewer, tmp_path):
    """Excel / Word pages have no image or size, so the file is never opened for them."""
    client, holder = viewer
    holder["doc"] = fake_doc(str(tmp_path / "gone.xlsx"), mime="text/csv")
    res = client.get(f"/documents/{holder['doc'].id}/pages/1", headers={"Origin": ORIGIN})
    assert res.status_code == 200
    assert res.json()["image_url"] is None


def test_an_unhandled_error_still_carries_cors_and_leaks_nothing(viewer, monkeypatch):
    client, _ = viewer

    def explode(db, document_id, user):
        raise RuntimeError(f"psycopg exploded reading {SECRET_PATH}")

    monkeypatch.setattr(documents, "_get_scoped", explode)
    res = client.get(f"/documents/{uuid.uuid4()}/pages/1", headers={"Origin": ORIGIN})
    assert res.status_code == 500
    assert res.headers["access-control-allow-origin"] == ORIGIN
    assert res.json()["code"] == "server_error"
    for leak in ("RuntimeError", "psycopg", "storage/originals", "Traceback"):
        assert leak not in res.text


def test_ordinary_http_errors_are_unchanged(client_as):
    """The safety net only catches what nothing else handled: 403s stay 403s."""
    client = client_as(["viewer"])
    res = client.post(f"/documents/{uuid.uuid4()}/retry", headers={"Origin": ORIGIN})
    assert res.status_code == 403
    assert res.headers["access-control-allow-origin"] == ORIGIN
