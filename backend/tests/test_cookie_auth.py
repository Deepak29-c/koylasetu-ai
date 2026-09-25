"""Login cookies for the browser, the CSRF header they need, and Bearer tokens for scripts."""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.cookies import ACCESS_COOKIE, CSRF_HEADER, CSRF_VALUE, REFRESH_COOKIE
from app.core.db import get_db
from app.core.security import create_token, hash_password
from app.main import app

CSRF = {CSRF_HEADER: CSRF_VALUE}
PASSWORDS = {"current_password": "pw", "new_password": "a-longer-password"}


class FakeDb:
    """Just enough session for login, refresh, the current-user lookup and a password change."""

    def __init__(self, user):
        self.user = user

    def scalar(self, _stmt):
        return self.user

    def get(self, _model, _id):
        return self.user

    def add(self, _obj):
        pass

    def commit(self):
        pass


@pytest.fixture
def user():
    org = SimpleNamespace(id=uuid.uuid4(), code="CMPDI", name="CMPDI", type="subsidiary")
    u = SimpleNamespace(
        id=uuid.uuid4(),
        email="operator@koylasetu.local",
        name="Operator",
        roles=["operator"],
        is_active=True,
        password_hash=hash_password("pw"),
        org_unit_id=org.id,
        org_unit=org,
    )
    app.dependency_overrides[get_db] = lambda: FakeDb(u)
    yield u
    app.dependency_overrides.clear()


def logged_in() -> TestClient:
    client = TestClient(app)
    res = client.post("/auth/login", json={"email": "operator@koylasetu.local", "password": "pw"})
    assert res.status_code == 200
    return client


def test_login_sets_httponly_cookies_and_still_returns_tokens(user):
    client = TestClient(app)
    res = client.post("/auth/login", json={"email": "operator@koylasetu.local", "password": "pw"})
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"] and body["refresh_token"]

    cookies = {c.split("=", 1)[0]: c for c in res.headers.get_list("set-cookie")}
    access, refresh = cookies[ACCESS_COOKIE], cookies[REFRESH_COOKIE]
    for cookie in (access, refresh):
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie
        assert "Secure" not in cookie  # COOKIE_SECURE is off by default for http://localhost
    assert "Path=/;" in access
    assert f"Max-Age={get_settings().access_token_minutes * 60}" in access
    assert "Path=/auth" in refresh


def test_cookie_authenticates_reads(user):
    res = logged_in().get("/me")
    assert res.status_code == 200
    assert res.json()["email"] == "operator@koylasetu.local"


def test_cookie_post_without_csrf_header_is_403(user):
    res = logged_in().post("/me/password", json=PASSWORDS)
    assert res.status_code == 403
    assert CSRF_HEADER in res.json()["detail"]


def test_cookie_post_with_csrf_header_works(user):
    assert logged_in().post("/me/password", json=PASSWORDS, headers=CSRF).status_code == 204


def test_bearer_needs_no_csrf_header(user):
    token = create_token(user.id, "access")
    res = TestClient(app).post(
        "/me/password", json=PASSWORDS, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 204


def test_refresh_with_cookie(user):
    client = logged_in()
    assert client.post("/auth/refresh").status_code == 403  # no CSRF header
    res = client.post("/auth/refresh", headers=CSRF)
    assert res.status_code == 200
    assert ACCESS_COOKIE in res.cookies


def test_refresh_with_body_still_works(user):
    token = create_token(user.id, "refresh")
    res = TestClient(app).post("/auth/refresh", json={"refresh_token": token})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_refresh_without_any_token_is_401(user):
    assert TestClient(app).post("/auth/refresh", headers=CSRF).status_code == 401


def test_logout_clears_cookies(user):
    client = logged_in()
    res = client.post("/auth/logout", headers=CSRF)
    assert res.status_code == 204
    cleared = {c.split("=", 1)[0]: c for c in res.headers.get_list("set-cookie")}
    assert "Max-Age=0" in cleared[ACCESS_COOKIE]
    assert "Path=/auth" in cleared[REFRESH_COOKIE] and "Max-Age=0" in cleared[REFRESH_COOKIE]
    assert client.get("/me").status_code == 401
