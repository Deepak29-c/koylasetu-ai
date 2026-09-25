import pytest

from app.core.rbac import Permission as P
from app.core.rbac import Role as R
from app.core.rbac import has_permission

# Spot checks straight from the permission matrix in guide section 2.1.
CASES = [
    (R.ADMIN, P.MANAGE_ADMIN, True),
    (R.OPERATOR, P.MANAGE_ADMIN, False),
    (R.OPERATOR, P.UPLOAD_DOCUMENTS, True),
    (R.ANALYST, P.UPLOAD_DOCUMENTS, False),
    (R.VIEWER, P.UPLOAD_DOCUMENTS, False),
    (R.REVIEWER, P.REVIEW_FACTS, True),
    (R.ANALYST, P.REVIEW_FACTS, False),
    (R.VIEWER, P.ASK_QUESTIONS, True),
    (R.ADMIN, P.EDIT_REPORTS, False),
    (R.APPROVER, P.EDIT_REPORTS, True),
    (R.ANALYST, P.APPROVE_REPORTS, False),
    (R.APPROVER, P.APPROVE_REPORTS, True),
    (R.VIEWER, P.EXPORT_REPORTS, True),
    (R.OPERATOR, P.EXPORT_REPORTS, False),
    (R.APPROVER, P.VIEW_AUDIT, True),
    (R.ANALYST, P.VIEW_AUDIT, False),
    (R.APPROVER, P.VIEW_PROCESSING, False),
    (R.APPROVER, P.VIEW_METRICS, True),
    (R.ADMIN, P.VIEW_METRICS, True),
    (R.ANALYST, P.VIEW_METRICS, False),
]


@pytest.mark.parametrize(("role", "perm", "allowed"), CASES)
def test_matrix(role, perm, allowed):
    assert has_permission([role.value], perm) is allowed


def test_multiple_roles_combine():
    assert not has_permission(["analyst"], P.APPROVE_REPORTS)
    assert has_permission(["analyst", "approver"], P.APPROVE_REPORTS)


def test_unknown_role_has_nothing():
    assert not any(has_permission(["intruder"], p) for p in P)
