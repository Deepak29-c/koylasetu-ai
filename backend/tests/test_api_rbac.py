"""Endpoint-level RBAC: wrong role -> 403, no token -> 401 (guide 15.1)."""

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_no_token_is_401():
    client = TestClient(app)
    assert client.get("/me").status_code == 401
    assert client.get("/documents").status_code == 401


def test_login_accepts_demo_local_domain():
    from app.schemas.auth import LoginIn

    assert LoginIn(email="  Operator@KoylaSetu.local ", password="x").email == (
        "operator@koylasetu.local"
    )


def test_viewer_cannot_upload(client_as):
    res = client_as(["viewer"]).post(
        "/documents",
        data={"doc_type": "annual_report"},
        files={"files": ("a.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert res.status_code == 403


def test_approver_cannot_list_processing(client_as):
    assert client_as(["approver"]).get("/documents").status_code == 403


def test_operator_cannot_mark_public(client_as):
    res = client_as(["operator"], "CMPDI").post(
        "/documents",
        data={"doc_type": "other", "is_public": "true"},
        files={"files": ("a.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert res.status_code == 403


def test_title_only_for_a_single_file(client_as):
    pdf = ("a.pdf", b"%PDF-1.7", "application/pdf")
    res = client_as(["admin"], "CIL_HQ").post(
        "/documents",
        data={"doc_type": "other", "title": "Coal Stock"},
        files=[("files", pdf), ("files", ("b.pdf", b"%PDF-1.7", "application/pdf"))],
    )
    assert res.status_code == 422
    assert "single file" in res.json()["detail"]
    res = client_as(["admin"], "CIL_HQ").post(
        "/documents", data={"doc_type": "other", "title": "x" * 501}, files={"files": pdf}
    )
    assert res.status_code == 422


def test_unclear_fy_is_rejected_before_saving(client_as):
    res = client_as(["operator"]).post(
        "/documents",
        data={"doc_type": "other", "fy": "last year"},
        files={"files": ("a.pdf", b"%PDF-1.7", "application/pdf")},
    )
    assert res.status_code == 422
    assert "FY 2024-25" in res.json()["detail"]


def test_me_lists_permissions(client_as):
    body = client_as(["analyst", "approver"], "CIL_HQ").get("/me").json()
    assert "approve_reports" in body["permissions"]
    assert "upload_documents" not in body["permissions"]
    assert body["org_unit"]["code"] == "CIL_HQ"


def test_only_reviewer_or_admin_can_open_review_queue(client_as):
    assert client_as(["analyst"]).get("/review/issues").status_code == 403
    assert client_as(["viewer"]).post("/review/facts/00000000-0000-0000-0000-000000000000",
                                      json={"action": "ACCEPT"}).status_code == 403  # fmt: skip


def test_edit_and_reject_need_a_comment(client_as):
    url = "/review/facts/00000000-0000-0000-0000-000000000000"
    reviewer = client_as(["reviewer"])
    assert reviewer.post(url, json={"action": "REJECT"}).status_code == 422
    assert reviewer.post(url, json={"action": "EDIT", "comment": "typo"}).status_code == 422


def test_viewer_cannot_list_raw_facts(client_as):
    doc_id = "00000000-0000-0000-0000-000000000001"
    assert client_as(["viewer"]).get(f"/documents/{doc_id}/facts").status_code == 403


def test_facts_needs_login():
    doc_id = "00000000-0000-0000-0000-000000000001"
    assert TestClient(app).get(f"/documents/{doc_id}/facts").status_code == 401
