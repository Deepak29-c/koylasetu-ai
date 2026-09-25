from pydantic import BaseModel


class ReportsPanelOut(BaseModel):
    """Reports that need this person to do something."""

    my_drafts: int  # started by me, still a draft
    returned_to_me: int  # sent back by an Approver, waiting on me to fix
    awaiting_approval: int  # submitted, waiting for an Approver (approvers only)
    due_soon: int  # due within a week and not yet approved
    overdue: int  # past the due date and not yet approved


class DocumentsPanelOut(BaseModel):
    processing: int
    needs_review: int
    failed: int
    processed_this_month: int


class ReviewPanelOut(BaseModel):
    pending_facts: int  # extracted or flagged, no human decision yet
    flagged_facts: int  # subset of the above that a validation rule flagged


class ActivityPanelOut(BaseModel):
    questions_this_month: int  # asked by me


class DashboardSummaryOut(BaseModel):
    """Only the panels the caller is allowed to act on; the rest are null."""

    reports: ReportsPanelOut | None = None
    documents: DocumentsPanelOut | None = None
    review: ReviewPanelOut | None = None
    activity: ActivityPanelOut | None = None
