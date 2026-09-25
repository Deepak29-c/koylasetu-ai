"""Validation rules V01-V08 (guide section 8). One small function per rule.

Each rule gets the facts extracted from one document (`facts`) and, where it needs them,
facts already stored from other documents (`others`), and returns issues. A fact with any
issue goes to the Reviewer (FLAGGED); a fact with none is accepted automatically (VERIFIED).
The share of facts accepted automatically is the "% automation" the problem statement asks for.

The rules only read the fields below, so they work on `Fact` rows and on `FactDraft`s alike.
A fact with no period is flagged by V08 only: without a period it can't be compared with
another figure, so V01 / V02 / V07 skip it (else "Annual Target" and "Monthly Target" collide).
`validate_document` runs them on a document's saved facts after extraction.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Document, Fact, ValidationIssue
from app.models.enums import FactStatus, Metric, PeriodType, Severity
from app.services.normalise import ALL_INDIA, CIL_SUBSIDIARIES
from worker.extract import REVIEW_THRESHOLD, STANDARD_UNIT

log = logging.getLogger(__name__)

TOLERANCE = 0.005  # 0.5 %
MAX_SUBSIDIARY_MT = 1500  # V03: no single company produces more than this in a year
YOY_LIMIT = 0.5  # V06: ±50 %
YOY_MIN_MT = 0.5  # V06: ignore tiny figures, where one decimal changes the % a lot
# NEC is tiny and often left out of subsidiary tables; the CIL check runs without it.
_CIL_MAIN = CIL_SUBSIDIARIES - {"NEC"}
# V03 only applies to yearly company output in MT (not resources, not OB in Mcum).
_OUTPUT_METRICS = {
    Metric.COAL_PRODUCTION,
    Metric.COAL_OFFTAKE,
    Metric.PRODUCTION_TARGET,
    Metric.COKING_COAL_PRODUCTION,
}


class FactLike(Protocol):
    metric: Metric
    subsidiary: str | None
    state: str | None
    category: str | None
    period_type: PeriodType | None
    period: str | None
    unit: str | None
    value_std: float | None
    confidence: float


def key(f: FactLike) -> tuple:
    """Identity of a figure, used by the duplicate / conflict / year-on-year rules."""
    return (f.metric, f.subsidiary, f.state, f.category, f.period_type, f.period)


@dataclass
class Other:
    """A fact already in the database, from another document."""

    id: uuid.UUID
    key: tuple
    value_std: float
    document_title: str


@dataclass
class Issue:
    fact: int  # index into facts
    rule: str
    severity: Severity
    message: str
    related: int | None = None  # index into facts
    related_fact_id: uuid.UUID | None = None


def _close(a: float, b: float, parts: int = 1) -> bool:
    # 0.5 % of the larger value, plus rounding slack: each part printed to 2 decimals
    return abs(a - b) <= max(TOLERANCE * max(abs(a), abs(b)), 0.005 * parts)


def _fmt(v: float) -> str:
    return f"{v:,.2f}"


def _std(f: FactLike) -> float | None:
    return None if f.value_std is None else float(f.value_std)


def v01_totals(facts: Sequence[FactLike]) -> list[Issue]:
    """Sum of subsidiaries = CIL total; CIL + SCCL + Captive = all India; states = India."""
    issues: list[Issue] = []
    groups: dict[tuple, dict[str, int]] = defaultdict(dict)
    for i, f in enumerate(facts):
        who = f.subsidiary or (f"STATE:{f.state}" if f.state else None)
        if who and f.period and _std(f) is not None:
            groups[(f.metric, f.category, f.period_type, f.period)].setdefault(who, i)

    for members in groups.values():
        states = [m for m in members if m.startswith("STATE:")]
        checks = [
            ("CIL", [s for s in sorted(CIL_SUBSIDIARIES) if s in members],
             all(s in members for s in _CIL_MAIN)),
            (ALL_INDIA, [s for s in ("CIL", "SCCL", "CAPTIVE") if s in members],
             all(s in members for s in ("CIL", "SCCL", "CAPTIVE"))),
            (ALL_INDIA, states, len(states) >= 3),
        ]  # fmt: skip
        for total_key, parts, complete in checks:
            if total_key not in members or not complete:
                continue
            total = facts[members[total_key]]
            s = sum(_std(facts[members[p]]) for p in parts)
            if not _close(s, _std(total), len(parts)):
                issues.append(
                    Issue(
                        members[total_key], "V01", Severity.HIGH,
                        f"{total_key} total {_fmt(_std(total))} ≠ sum of {len(parts)} parts "
                        f"{_fmt(s)} ({', '.join(p.replace('STATE:', '') for p in parts)})",
                    )  # fmt: skip
                )
    return issues


def v02_conflicts(facts: Sequence[FactLike], others: list[Other]) -> list[Issue]:
    """Same figure in another document differs by more than 0.5 %."""
    by_key: dict[tuple, list[Other]] = defaultdict(list)
    for o in others:
        by_key[o.key].append(o)
    issues = []
    for i, f in enumerate(facts):
        if not f.period or _std(f) is None:
            continue
        for o in by_key.get(key(f), []):
            if not _close(_std(f), o.value_std, 2):
                issues.append(
                    Issue(i, "V02", Severity.HIGH,
                          f"Differs from {_fmt(o.value_std)} in '{o.document_title}'",
                          related_fact_id=o.id)  # fmt: skip
                )
                break
    return issues


def v03_impossible(facts: Sequence[FactLike]) -> list[Issue]:
    issues = []
    for i, f in enumerate(facts):
        v = _std(f)
        if v is None:
            continue
        if v < 0:
            issues.append(Issue(i, "V03", Severity.HIGH, "Negative value"))
        elif (
            f.metric in _OUTPUT_METRICS
            and f.subsidiary
            and f.subsidiary != ALL_INDIA
            and v > MAX_SUBSIDIARY_MT
        ):
            issues.append(
                Issue(i, "V03", Severity.HIGH,
                      f"{_fmt(v)} MT: more than any company produces")  # fmt: skip
            )
    return issues


def v04_unit(facts: Sequence[FactLike]) -> list[Issue]:
    issues = []
    for i, f in enumerate(facts):
        std = STANDARD_UNIT[f.metric]
        if f.unit is None:
            issues.append(
                Issue(i, "V04", Severity.MEDIUM, f"Unit not stated in the table; assumed {std}")
            )
        elif f.value_std is None:
            issues.append(
                Issue(i, "V04", Severity.MEDIUM, f"Unit '{f.unit}' cannot be converted to {std}")
            )
    return issues


def v05_confidence(facts: Sequence[FactLike]) -> list[Issue]:
    return [
        Issue(i, "V05", Severity.MEDIUM, f"Low extraction confidence ({f.confidence:.2f})")
        for i, f in enumerate(facts)
        if f.confidence < REVIEW_THRESHOLD
    ]


def _previous_period(period_type: PeriodType | None, period: str | None) -> str | None:
    if not period or period_type not in (PeriodType.MONTH, PeriodType.YTD, PeriodType.FY):
        return None
    if period_type == PeriodType.FY:  # "FY 2024-25" -> "FY 2023-24"
        start = int(period[3:7]) - 1
        return f"FY {start}-{(start + 1) % 100:02d}"
    return f"{int(period[:4]) - 1}{period[4:]}"  # "2024-12" -> "2023-12"


def v06_year_on_year(facts: Sequence[FactLike], others: list[Other]) -> list[Issue]:
    known: dict[tuple, float] = {o.key: o.value_std for o in others}
    known.update({key(f): _std(f) for f in facts if _std(f) is not None})
    issues = []
    for i, f in enumerate(facts):
        v = _std(f)
        prev = _previous_period(f.period_type, f.period)
        if v is None or prev is None or f.metric == Metric.COAL_RESOURCE:
            continue
        base = known.get((*key(f)[:5], prev))
        if base is None or (base < YOY_MIN_MT and v < YOY_MIN_MT) or base == 0:
            continue
        change = (v - base) / base
        if abs(change) > YOY_LIMIT:
            issues.append(
                Issue(i, "V06", Severity.LOW,
                      f"{change:+.0%} vs {_fmt(base)} a year earlier; typo?")  # fmt: skip
            )
    return issues


def v07_duplicates(facts: Sequence[FactLike]) -> list[Issue]:
    first: dict[tuple, int] = {}
    issues = []
    for i, f in enumerate(facts):
        if not f.period:
            continue
        k = key(f)
        if k in first:
            j = first[k]
            a, b = _std(f), _std(facts[j])
            same = a is not None and b is not None and _close(a, b)
            issues.append(
                Issue(i, "V07", Severity.LOW if same else Severity.HIGH,
                      "Same figure appears again in this document"
                      + ("" if same or b is None else f" with a different value ({_fmt(b)})"),
                      related=j)  # fmt: skip
            )
        else:
            first[k] = i
    return issues


def v08_period(facts: Sequence[FactLike]) -> list[Issue]:
    return [
        Issue(i, "V08", Severity.MEDIUM, "Period could not be identified from the table")
        for i, f in enumerate(facts)
        if not f.period
    ]


def validate(facts: Sequence[FactLike], others: list[Other]) -> list[Issue]:
    return [
        *v01_totals(facts),
        *v02_conflicts(facts, others),
        *v03_impossible(facts),
        *v04_unit(facts),
        *v05_confidence(facts),
        *v06_year_on_year(facts, others),
        *v07_duplicates(facts),
        *v08_period(facts),
    ]


def validate_document(db: Session, doc_id: uuid.UUID) -> int:
    """Run the rules on a document's saved facts: VERIFIED when clean, FLAGGED with
    ValidationIssue rows otherwise. Returns the number of issues. Does not commit."""
    facts = list(
        db.scalars(
            select(Fact)
            .where(Fact.document_id == doc_id)
            .order_by(Fact.page_no, Fact.created_at, Fact.id)
        )
    )
    db.execute(delete(ValidationIssue).where(ValidationIssue.fact_id.in_([f.id for f in facts])))
    if not facts:
        return 0
    others = [
        Other(f.id, key(f), float(f.value_std), title)
        for f, title in db.execute(
            select(Fact, Document.title)
            .join(Document, Document.id == Fact.document_id)
            .where(
                Fact.metric.in_({f.metric for f in facts}),
                Fact.document_id != doc_id,
                Fact.status != FactStatus.REJECTED,
                Fact.value_std.is_not(None),
            )
        ).all()
    ]
    issues = validate(facts, others)
    flagged = {i.fact for i in issues}
    for index, f in enumerate(facts):
        f.status = FactStatus.FLAGGED if index in flagged else FactStatus.VERIFIED
    for issue in issues:
        related = facts[issue.related].id if issue.related is not None else None
        db.add(
            ValidationIssue(
                fact_id=facts[issue.fact].id,
                rule_code=issue.rule,
                message=issue.message,
                severity=issue.severity,
                related_fact_id=related or issue.related_fact_id,
            )
        )
    log.info("Document %s: %d facts, %d flagged", doc_id, len(facts), len(flagged))
    return len(issues)
