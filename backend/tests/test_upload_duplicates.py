"""A file belongs to a unit, not to the whole system (#44).

Before this, the sha256 check was global and unscoped: the second unit to upload a
shared public circular was told "This exact file was uploaded before", given nothing to
open, and left without a copy of their own.
"""

from sqlalchemy import select

from app.core.deps import scope_to_user
from app.models import Document
from tests.conftest import fake_user

SHA = "a" * 64


def duplicate_lookup(user) -> str:
    """The query the upload route runs to decide whether this is a duplicate."""
    stmt = scope_to_user(select(Document).where(Document.sha256 == SHA), Document, user)
    return str(stmt.whereclause)


def test_a_subsidiary_only_matches_its_own_or_a_public_copy():
    where = duplicate_lookup(fake_user(["operator"], "CMPDI"))
    assert "documents.org_unit_id" in where
    assert "documents.is_public" in where  # a shared public copy still counts


def test_hq_matches_any_copy():
    """CIL HQ and the Ministry see every unit, so any existing copy is theirs already."""
    where = duplicate_lookup(fake_user(["operator"], "CIL_HQ"))
    assert "org_unit_id" not in where


def test_the_same_file_is_unique_per_unit_not_globally():
    (constraint,) = [
        c for c in Document.__table__.constraints if c.name == "uq_documents_org_unit_id"
    ]
    assert [c.name for c in constraint.columns] == ["org_unit_id", "sha256"]
    assert not Document.__table__.c.sha256.unique
