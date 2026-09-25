import os
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256")

from app.core.db import get_db  # noqa: E402
from app.core.deps import get_current_user  # noqa: E402
from app.main import app  # noqa: E402


def fake_user(roles: list[str], org_code: str = "CMPDI") -> SimpleNamespace:
    org_id = uuid.uuid4()
    return SimpleNamespace(
        id=uuid.uuid4(),
        name="Test",
        email="t@koylasetu.local",
        roles=roles,
        is_active=True,
        org_unit_id=org_id,
        org_unit=SimpleNamespace(id=org_id, code=org_code, name=org_code, type="subsidiary"),
    )


@pytest.fixture
def client_as():
    """client_as(["viewer"]) -> TestClient logged in as a user with those roles (no DB)."""

    def make(roles: list[str], org_code: str = "CMPDI") -> TestClient:
        user = fake_user(roles, org_code)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: None
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()
