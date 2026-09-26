"""Import every model here so Alembic and the app see the full schema."""

from app.models.base import Base
from app.models.depth import DepthResource
from app.models.document import Chunk, Document, ExtractedTable, Page
from app.models.fact import Fact, ReviewActionLog, ValidationIssue
from app.models.org import OrgUnit, User
from app.models.report import (
    AuditLog,
    ParliamentQuestion,
    QaLog,
    Report,
    ReportCitation,
    ReportVersion,
    Topic,
)

__all__ = [
    "AuditLog",
    "Base",
    "Chunk",
    "DepthResource",
    "Document",
    "ExtractedTable",
    "Fact",
    "OrgUnit",
    "Page",
    "ParliamentQuestion",
    "QaLog",
    "Report",
    "ReportCitation",
    "ReportVersion",
    "ReviewActionLog",
    "Topic",
    "User",
    "ValidationIssue",
]
