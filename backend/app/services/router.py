"""Question router (guide 9.1): NUMERIC, TEXTUAL or MIXED, plus the filters for a facts query.

Rules first (no model call): fast, predictable and testable. A question is NUMERIC when it
names a measured quantity (production, despatch, target, resources...) together with a
company, state or period; TEXTUAL when it asks for reasons, steps or policy; MIXED when it
does both, e.g. "production of NCL in 2023-24 and steps taken to increase it".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import Metric, PeriodType, QaRoute
from app.services.normalise import (
    ALL_INDIA,
    match_state,
    match_subsidiaries,
    month_in_fy,
    normalise_fy,
    to_ascii_digits,
)

MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}

_METRIC_WORDS = [
    (
        Metric.COKING_COAL_PRODUCTION,
        r"coking\s+coal\s+(?:production|output)|production\s+of\s+coking",
    ),
    (Metric.PRODUCTION_TARGET, r"\btargets?\b"),
    (Metric.COAL_OFFTAKE, r"\b(?:despatch|dispatch|off-?take|supply of coal|coal supply)"),
    (Metric.OB_REMOVAL, r"\bover\s*burden\b|\bOBR?\b"),
    (Metric.COAL_RESOURCE, r"\b(?:resources?|reserves?)\b"),
    (Metric.COAL_PRODUCTION, r"\b(?:produc(?:tion|ed)|output)\b"),
]
_TEXT_INTENT = re.compile(
    r"\b(?:steps?|measures?|reasons?|why|how|initiatives?|policy|policies|plans?|action|"
    r"details? of (?:the )?(?:scheme|project)|remedial|proposal|impact|views)\b",
    re.I,
)
_CATEGORY = re.compile(r"\b(measured|indicated|inferred|proved|proven)\b", re.I)
_FY = re.compile(
    r"\b(?:F\.?Y\.?\s*)?(20\d{2})\s*[-–/]\s*(\d{2}|\d{4})\b|\bF\.?Y\.?\s*'?(\d{2})\b", re.I
)
_MONTH_YEAR = re.compile(r"\b(" + "|".join(MONTHS) + r")[a-z]*\.?\s*[',’]?\s*(\d{2}|\d{4})\b", re.I)
_AS_ON = re.compile(r"\bas\s+on\s+(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})", re.I)
_UPTO = re.compile(r"\b(?:up\s*to|upto|till|until|cumulative|so far|april\s*[-–to]+)\b", re.I)

# Company names and codes come from the extractor's alias map (normalise.match_subsidiaries);
# these extra phrases mean the all-India total, stored as subsidiary "INDIA".
_ALL_INDIA = re.compile(
    r"\ball[\s-]+india\b|\bwhole country\b|\bthe country\b|\bindia's\b|\bindian coal\b"
    r"|\bnational\b",
    re.I,
)
_ORDER = ["ECL", "BCCL", "CCL", "NCL", "WCL", "SECL", "MCL", "NEC", "CIL", "SCCL", "CAPTIVE"]


@dataclass
class Filters:
    metrics: list[Metric] = field(default_factory=list)
    subsidiaries: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    category: str | None = None
    coking: bool = False
    period_type: PeriodType | None = None
    periods: list[str] = field(default_factory=list)
    # "subsidiary-wise" / "state-wise": return every company / state, not just named ones
    breakdown: bool = False

    def describe(self) -> str:
        parts = [
            "metric=" + ",".join(m.value for m in self.metrics),
            "subsidiary=" + ",".join(self.subsidiaries) if self.subsidiaries else "",
            "state=" + ",".join(self.states) if self.states else "",
            f"category={self.category}" if self.category else "",
            "coking" if self.coking else "",
            f"period_type={self.period_type.value}" if self.period_type else "",
            "period=" + ",".join(self.periods) if self.periods else "",
            "breakdown" if self.breakdown else "",
        ]
        return "; ".join(p for p in parts if p)


@dataclass
class Route:
    route: QaRoute
    filters: Filters


def _find_subsidiaries(q: str) -> list[str]:
    codes, _ = match_subsidiaries(q)
    found = [c for c in _ORDER if c in codes]
    if _ALL_INDIA.search(q):
        found.append(ALL_INDIA)
    return found


def _find_states(q: str) -> list[str]:
    """States named in the question, as stored in facts ("Odisha"); longest phrase first."""
    words = re.findall(r"[A-Za-z&]+", q)
    found: set[str] = set()
    used: set[int] = set()
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            span = set(range(i, i + n))
            if not span & used and (state := match_state(" ".join(words[i : i + n]))):
                used |= span
                found.add(state)
    return sorted(found)


def extract_filters(question: str) -> Filters:
    q = to_ascii_digits(question)
    f = Filters()
    for metric, pattern in _METRIC_WORDS:
        if re.search(pattern, q, re.I):
            f.metrics.append(metric)
    if Metric.COKING_COAL_PRODUCTION in f.metrics and Metric.COAL_PRODUCTION in f.metrics:
        f.metrics.remove(Metric.COAL_PRODUCTION)  # "coking coal production" is one metric
    if Metric.PRODUCTION_TARGET in f.metrics and len(f.metrics) == 1:
        f.metrics.append(Metric.COAL_PRODUCTION)  # "target" alone: show it against actuals
    if re.search(r"\bcoking\b", q, re.I) and not re.search(r"non-?\s?coking", q, re.I):
        f.coking = True

    f.subsidiaries = _find_subsidiaries(q)
    f.states = _find_states(q)
    f.breakdown = bool(re.search(r"(?:subsidiary|company|state|coalfield)[-\s]?wise", q, re.I))
    if m := _CATEGORY.search(q):
        word = m.group(1).lower()
        f.category = "Measured" if word in ("proved", "proven") else word.capitalize()

    if m := _AS_ON.search(q):
        # The extractor stores an "as on 01.04.2025" figure under its month, "2025-04"
        f.period_type = PeriodType.MONTH
        f.periods = [f"{int(m.group(3)):04d}-{int(m.group(2)):02d}"]
    else:
        fys = []
        for m in _FY.finditer(q):
            try:
                fy = normalise_fy(f"FY{m.group(3)}" if m.group(3) else f"{m.group(1)}-{m.group(2)}")
            except ValueError:
                continue
            if fy not in fys:
                fys.append(fy)
        months = []
        for m in _MONTH_YEAR.finditer(q):
            month = MONTHS[m.group(1).lower()[:3]]
            year = int(m.group(2)) + (2000 if len(m.group(2)) == 2 else 0)
            fy_start = year if month >= 4 else year - 1
            months.append(month_in_fy(month, f"FY {fy_start}-{(fy_start + 1) % 100:02d}"))
        if months:
            f.period_type = PeriodType.YTD if _UPTO.search(q) else PeriodType.MONTH
            f.periods = months
        elif fys:
            f.period_type = PeriodType.FY
            f.periods = fys
    return f


def route(question: str) -> Route:
    f = extract_filters(question)
    has_target = bool(f.subsidiaries or f.states or f.periods or f.breakdown)
    numeric = bool(f.metrics) and (
        has_target or re.search(r"\bhow much\b|\btotal\b", question, re.I)
    )
    textual = bool(_TEXT_INTENT.search(question))
    if numeric and textual:
        return Route(QaRoute.MIXED, f)
    if numeric:
        return Route(QaRoute.NUMERIC, f)
    return Route(QaRoute.TEXTUAL, f)
