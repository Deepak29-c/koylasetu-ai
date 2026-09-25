from pydantic import BaseModel


class QaMetricsOut(BaseModel):
    """Live Q&A usage, from qa_logs (scoped to the caller's units)."""

    questions_total: int
    questions_this_month: int
    grounded: int  # answers whose every figure was found in the sources
    grounded_pct: float | None
    avg_latency_ms: int | None
    helpful: int
    not_helpful: int
    helpful_pct: float | None  # of the answers that got feedback


class FactMetricsOut(BaseModel):
    """Figures extracted from documents and what happened to them (guide 15.2 automation %)."""

    total: int
    auto_verified: int  # passed every validation rule, no human needed
    reviewed_verified: int
    flagged: int
    rejected: int
    automation_pct: float | None


class ReportMetricsOut(BaseModel):
    total: int
    drafts: int
    in_review: int
    approved: int  # approved or exported


class BenchmarkOut(BaseModel):
    """Headline numbers of the latest eval/run_eval.py run (summary.json)."""

    run_date: str
    questions_asked: int
    answered: int
    not_found: int
    errors: int
    numeric_accuracy_pct: float | None
    all_correct_pct: float | None
    grounded_pct: float | None
    median_latency_ms: int | None
    time_saved_pct: float | None
    citation_correct_pct: float | None
    automation_pct: float | None


class MetricsOut(BaseModel):
    qa: QaMetricsOut
    facts: FactMetricsOut
    reports: ReportMetricsOut
    benchmark: BenchmarkOut | None  # null until the benchmark has been run on this machine
