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
    COAL_STATES,
    MONTHS,
    SUBSIDIARY_ALIASES,
    month_in_fy,
    normalise_fy,
    to_ascii_digits,
)

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

# Aliases people use in questions, beyond the codes (e.g. "Mahanadi Coalfields")
_SUBSIDIARY_NAMES = {
    "ECL": ["eastern coalfields"],
    "BCCL": ["bharat coking coal"],
    "CCL": ["central coalfields"],
    "NCL": ["northern coalfields"],
    "WCL": ["western coalfields"],
    "SECL": ["south eastern coalfields", "south-eastern coalfields"],
    "MCL": ["mahanadi coalfields"],
    "NEC": ["north eastern coalfields"],
    "CIL": ["coal india"],
    "SCCL": ["singareni"],
    "CAPTIVE": ["captive", "commercial mines"],
    "ALL_INDIA": [
        "all india",
        "whole country",
        "the country",
        "india's",
        "indian coal",
        "national",
    ],
}


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
    found = []
    for code, aliases in SUBSIDIARY_ALIASES.items():
        names = [a for a in aliases if len(a) <= 5] + _SUBSIDIARY_NAMES.get(code, [])
        for name in names:
            pattern = rf"\b{re.escape(name)}\b" if len(name) <= 5 else re.escape(name)
            flags = 0 if len(name) <= 5 and name.isupper() else re.I
            if re.search(pattern, q, flags):
                found.append(code)
                break
    # "CIL" also matches inside "coal india"; a named subsidiary + CIL stays as asked
    return found


def _find_states(q: str) -> list[str]:
    ql = q.lower().replace("orissa", "odisha")
    return [s for s in COAL_STATES if re.search(rf"\b{re.escape(s.lower())}\b", ql)]


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
        f.period_type = PeriodType.AS_ON
        f.periods = [f"{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"]
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
