"""Status and type values used across the models (developer guide sections 3 and 6)."""

from enum import StrEnum


class OrgType(StrEnum):
    SUBSIDIARY = "subsidiary"
    HQ = "hq"
    MINISTRY = "ministry"


class DocType(StrEnum):
    ANNUAL_REPORT = "annual_report"
    COAL_INVENTORY = "coal_inventory"
    MONTHLY_STATS = "monthly_stats"
    PQ_ANSWER = "pq_answer"
    OTHER = "other"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class FactStatus(StrEnum):
    EXTRACTED = "EXTRACTED"
    FLAGGED = "FLAGGED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class PeriodType(StrEnum):
    FY = "FY"  # "FY 2023-24"
    MONTH = "MONTH"  # "2024-12"
    YTD = "YTD"  # "2024-12" = April up to and including December of that FY
    AS_ON = "AS_ON"  # "2025-04-01" = stock figure on a date (coal resources)


class Metric(StrEnum):
    """Fixed metric list (guide 6.1). Standard unit in the comment."""

    COAL_PRODUCTION = "coal_production"  # MT
    COAL_OFFTAKE = "coal_offtake"  # MT
    OB_REMOVAL = "ob_removal"  # Mcum
    PRODUCTION_TARGET = "production_target"  # MT
    COKING_COAL_PRODUCTION = "coking_coal_production"  # MT
    COAL_RESOURCE = "coal_resource"  # MT, category = Measured / Indicated / Inferred
    COAL_IMPORT = "coal_import"  # MT


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ReviewAction(StrEnum):
    ACCEPT = "ACCEPT"
    EDIT = "EDIT"
    REJECT = "REJECT"


class House(StrEnum):
    LOK_SABHA = "LS"
    RAJYA_SABHA = "RS"


class QuestionType(StrEnum):
    STARRED = "starred"
    UNSTARRED = "unstarred"


class ReportType(StrEnum):
    PQ_REPLY = "pq_reply"
    MONTHLY = "monthly"
    BRIEFING = "briefing"


class ReportStatus(StrEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    RETURNED = "RETURNED"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"


class QaRoute(StrEnum):
    NUMERIC = "NUMERIC"
    TEXTUAL = "TEXTUAL"
    MIXED = "MIXED"
