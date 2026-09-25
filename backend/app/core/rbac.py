"""Roles, permissions and org-unit scoping (developer guide section 2)."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    ANALYST = "analyst"
    APPROVER = "approver"
    VIEWER = "viewer"


class Permission(StrEnum):
    MANAGE_ADMIN = "manage_admin"  # users / roles / templates / rules
    UPLOAD_DOCUMENTS = "upload_documents"
    VIEW_PROCESSING = "view_processing"
    REVIEW_FACTS = "review_facts"
    ASK_QUESTIONS = "ask_questions"
    EDIT_REPORTS = "edit_reports"
    APPROVE_REPORTS = "approve_reports"
    EXPORT_REPORTS = "export_reports"
    VIEW_TOPICS = "view_topics"
    VIEW_AUDIT = "view_audit"
    VIEW_METRICS = "view_metrics"  # accuracy, time saved, automation %, usage (guide 12)


R, P = Role, Permission

# Permission matrix, copied from guide section 2.1. Change it there first, then here.
PERMISSIONS: dict[Permission, frozenset[Role]] = {
    P.MANAGE_ADMIN: frozenset({R.ADMIN}),
    P.UPLOAD_DOCUMENTS: frozenset({R.ADMIN, R.OPERATOR, R.REVIEWER}),
    P.VIEW_PROCESSING: frozenset({R.ADMIN, R.OPERATOR, R.REVIEWER, R.ANALYST}),
    P.REVIEW_FACTS: frozenset({R.ADMIN, R.REVIEWER}),
    P.ASK_QUESTIONS: frozenset(Role),
    P.EDIT_REPORTS: frozenset({R.ANALYST, R.APPROVER}),
    P.APPROVE_REPORTS: frozenset({R.APPROVER}),
    P.EXPORT_REPORTS: frozenset({R.ADMIN, R.ANALYST, R.APPROVER, R.VIEWER}),
    P.VIEW_TOPICS: frozenset(Role),
    P.VIEW_AUDIT: frozenset({R.ADMIN, R.APPROVER}),
    P.VIEW_METRICS: frozenset({R.ADMIN, R.APPROVER}),
}


def has_permission(roles: list[str], permission: Permission) -> bool:
    """A user can hold several roles; any one of them is enough."""
    allowed = PERMISSIONS[permission]
    return any(r in allowed for r in roles)


# Org units whose users see every unit's data.
ALL_SCOPE_ORG_CODES = frozenset({"CIL_HQ", "MINISTRY"})
