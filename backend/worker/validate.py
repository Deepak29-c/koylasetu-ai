"""Validation rules V01-V08 (guide section 8). One small function per rule.

Each rule gets the facts extracted from one document (`drafts`) and, where it needs them,
facts already stored from other documents (`others`), and returns issues. A fact with any
issue goes to the Reviewer (FLAGGED); a fact with none is accepted automatically (VERIFIED).
The share of facts accepted automatically is the "% automation" the problem statement asks for.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from app.models.enums import Metric, PeriodType, Severity
from app.services.normalise import CIL_SUBSIDIARIES
from worker.extract import CONFIDENCE_THRESHOLD, FactDraft

TOLERANCE = 0.005  # 0.5 %
MAX_SUBSIDIARY_MT = 1500  # V03: no single company produces more than this in a year
YOY_LIMIT = 0.5  # V06: ±50 %
YOY_MIN_MT = 0.5  # V06: ignore tiny figures, where one decimal changes the % a lot


@dataclass
class Other:
    """A fact already in the database, from another document."""

    id: uuid.UUID
    key: tuple
    value_std: float
    document_title: str


@dataclass
class Issue:
    fact: int  # index into drafts
    rule: str
    severity: Severity
    message: str
    related_draft: int | None = None
    related_fact_id: uuid.UUID | None = None


def _close(a: float, b: float, parts: int = 1) -> bool:
    # 0.5 % of the larger value, plus rounding slack: each part printed to 2 decimals
    return abs(a - b) <= max(TOLERANCE * max(abs(a), abs(b)), 0.005 * parts)


def _fmt(v: float) -> str:
    return f"{v:,.2f}"


def v01_totals(drafts: list[FactDraft]) -> list[Issue]:
    """Sum of subsidiaries = CIL total; CIL + SCCL + Captive = all India; states = India."""
    issues: list[Issue] = []
    groups: dict[tuple, dict[str, int]] = defaultdict(dict)
    for i, f in enumerate(drafts):
        who = f.subsidiary or (f"STATE:{f.state}" if f.state else None)
        if who:
            groups[(f.metric, f.category, f.period_type, f.period, f.subsidiary is None)][who] = i

    ALL = "STATE:ALL_INDIA"  # noqa: N806
    for members in groups.values():
        checks = [
            ("CIL", [s for s in CIL_SUBSIDIARIES if s in members], len(CIL_SUBSIDIARIES)),
            ("ALL_INDIA", [s for s in ("CIL", "SCCL", "CAPTIVE") if s in members], 3),
            ("STATE:ALL_INDIA", [m for m in members if m.startswith("STATE:") and m != ALL], 3),
        ]  # fmt: skip
        for total_key, parts, needed in checks:
            if total_key not in members or len(parts) < needed:
                continue
            total = drafts[members[total_key]]
            s = sum(drafts[members[p]].value_std for p in parts)
            if not _close(s, total.value_std, len(parts)):
                name = total_key.replace("STATE:", "") or total_key
                issues.append(
                    Issue(
                        members[total_key], "V01", Severity.HIGH,
                        f"{name} total {_fmt(total.value_std)} ≠ sum of {len(parts)} parts "
                        f"{_fmt(s)} ({', '.join(p.replace('STATE:', '') for p in parts)})",
                    )  # fmt: skip
                )
    return issues


def v02_conflicts(drafts: list[FactDraft], others: list[Other]) -> list[Issue]:
    """Same figure in another document differs by more than 0.5 %."""
    by_key: dict[tuple, list[Other]] = defaultdict(list)
    for o in others:
        by_key[o.key].append(o)
    issues = []
    for i, f in enumerate(drafts):
        for o in by_key.get(f.key(), []):
            if not _close(f.value_std, o.value_std, 2):
                issues.append(
                    Issue(i, "V02", Severity.HIGH,
                          f"Differs from {_fmt(o.value_std)} in '{o.document_title}'",
                          related_fact_id=o.id)  # fmt: skip
                )
                break
    return issues


def v03_impossible(drafts: list[FactDraft]) -> list[Issue]:
    issues = []
    for i, f in enumerate(drafts):
        if f.value_std < 0:
            issues.append(Issue(i, "V03", Severity.HIGH, "Negative value"))
        elif f.subsidiary and f.subsidiary != "ALL_INDIA" and f.value_std > MAX_SUBSIDIARY_MT:
            issues.append(
                Issue(i, "V03", Severity.HIGH,
                      f"{_fmt(f.value_std)} MT: more than any company produces")  # fmt: skip
            )
    return issues


def v04_unit(drafts: list[FactDraft]) -> list[Issue]:
    return [
        Issue(i, "V04", Severity.MEDIUM, "Unit not stated in the table or page; assumed MT")
        for i, f in enumerate(drafts)
        if f.unit_guessed
    ]


def v05_confidence(drafts: list[FactDraft]) -> list[Issue]:
    return [
        Issue(i, "V05", Severity.MEDIUM, f"Low extraction confidence ({f.confidence:.2f})")
        for i, f in enumerate(drafts)
        if f.confidence < CONFIDENCE_THRESHOLD
    ]


def _previous_period(period_type: PeriodType | None, period: str | None) -> str | None:
    if not period or period_type not in (PeriodType.MONTH, PeriodType.YTD, PeriodType.FY):
        return None
    if period_type == PeriodType.FY:  # "FY 2024-25" -> "FY 2023-24"
        start = int(period[3:7]) - 1
        return f"FY {start}-{(start + 1) % 100:02d}"
    return f"{int(period[:4]) - 1}{period[4:]}"  # "2024-12" -> "2023-12"


def v06_year_on_year(drafts: list[FactDraft], others: list[Other]) -> list[Issue]:
    known: dict[tuple, float] = {o.key: o.value_std for o in others}
    known.update({f.key(): f.value_std for f in drafts})
    issues = []
    for i, f in enumerate(drafts):
        prev = _previous_period(f.period_type, f.period)
        if prev is None or f.metric == Metric.COAL_RESOURCE:
            continue
        base = known.get((*f.key()[:5], prev))
        if base is None or (base < YOY_MIN_MT and f.value_std < YOY_MIN_MT) or base == 0:
            continue
        change = (f.value_std - base) / base
        if abs(change) > YOY_LIMIT:
            issues.append(
                Issue(i, "V06", Severity.LOW,
                      f"{change:+.0%} vs {_fmt(base)} a year earlier; typo?")  # fmt: skip
            )
    return issues


def v07_duplicates(drafts: list[FactDraft]) -> list[Issue]:
    first: dict[tuple, int] = {}
    issues = []
    for i, f in enumerate(drafts):
        k = f.key()
        if k in first:
            j = first[k]
            same = _close(f.value_std, drafts[j].value_std)
            issues.append(
                Issue(i, "V07", Severity.HIGH if not same else Severity.LOW,
                      "Same figure appears again in this document"
                      + ("" if same else f" with a different value ({_fmt(drafts[j].value_std)})"),
                      related_draft=j)  # fmt: skip
            )
        else:
            first[k] = i
    return issues


def v08_period(drafts: list[FactDraft]) -> list[Issue]:
    return [
        Issue(i, "V08", Severity.MEDIUM, "Period could not be identified from the table")
        for i, f in enumerate(drafts)
        if not f.period
    ]


def validate(drafts: list[FactDraft], others: list[Other]) -> list[Issue]:
    return [
        *v01_totals(drafts),
        *v02_conflicts(drafts, others),
        *v03_impossible(drafts),
        *v04_unit(drafts),
        *v05_confidence(drafts),
        *v06_year_on_year(drafts, others),
        *v07_duplicates(drafts),
        *v08_period(drafts),
    ]
