from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.report import ReportOut
from app.services.monthly_report import ROW_CODES

MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


class MonthlyDraftIn(BaseModel):
    """Guide W5: the month, and optionally which subsidiaries (default: all rows)."""

    month: str = Field(pattern=MONTH, examples=["2024-12"])
    subsidiaries: list[str] | None = Field(default=None, max_length=len(ROW_CODES))

    @field_validator("subsidiaries")
    @classmethod
    def known_codes(cls, value: list[str] | None) -> list[str] | None:
        if not value:
            return None
        codes = [v.strip().upper() for v in value]
        unknown = [c for c in codes if c not in ROW_CODES]
        if unknown:
            raise ValueError(f"Unknown subsidiary code(s): {', '.join(unknown)}")
        return codes


class BriefingDraftIn(BaseModel):
    """Guide W6: the topic and an optional month range."""

    model_config = ConfigDict(populate_by_name=True)

    topic: str = Field(min_length=3, max_length=500)
    from_month: str | None = Field(default=None, alias="from", pattern=MONTH)
    to_month: str | None = Field(default=None, alias="to", pattern=MONTH)

    @model_validator(mode="after")
    def ordered(self) -> "BriefingDraftIn":
        if self.from_month and self.to_month and self.from_month > self.to_month:
            raise ValueError("'from' must not be after 'to'")
        return self


class ReportDraftOut(BaseModel):
    report: ReportOut  # content_json holds the sections, sources and the plain text
