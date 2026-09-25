"""Grounding check (guide 9.1): every number in an answer must exist in the retrieved data.

A number counts as grounded if it matches a number in the passages or in the question
itself within ±0.5%. Dates (25.11.2021, 25/11/21) must match exactly. Anything else is
returned as unmatched, exactly as written in the answer, so the UI can highlight it and the
answer is flagged "needs verification". This is the code side of the core rule: the model
may write the sentences, but it may not invent a figure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.normalise import to_ascii_digits

TOLERANCE = 0.005

_CITATION = re.compile(r"\[\s*[CF]\d+\s*\]")
# References, not figures: "Table 1", "page 8", "p. 12", "Annexure-II", "Question No. 55".
_REFERENCE = re.compile(
    r"\b(?:tables?|pages?|pp?\.|annexure|annex|para(?:graph)?|chapter|section|"
    r"(?:starred |unstarred )?question\s+no\.?|q\.\s*no\.?)\s*[-–:]?\s*\*?\d+[a-z]?\b",
    re.IGNORECASE,
)
_LIST_MARKER = re.compile(r"^\s*\(?\d{1,2}[.)]\s", re.M)  # "1. " / "2) " at line start
_DATE = re.compile(r"(?<![\w.])(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?![\w.]*\d)")
_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


@dataclass(frozen=True)
class Value:
    token: str  # as written, e.g. "4,00,715.45" or "25.11.2021"
    number: float | None = None
    date: str | None = None  # "2021-11-25"


def _prepare(text: str) -> str:
    text = to_ascii_digits(text)
    text = _CITATION.sub(" ", text)
    text = _REFERENCE.sub(" ", text)
    return _LIST_MARKER.sub(" ", text)


def extract_values(text: str) -> list[Value]:
    text = _prepare(text)
    values: list[Value] = []

    def take_date(m: re.Match) -> str:
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= day <= 31 and 1 <= month <= 12:
            full = int(year) + 2000 if len(year) == 2 else int(year)
            values.append(Value(m.group(0), date=f"{full:04d}-{month:02d}-{day:02d}"))
            return " "
        return m.group(0)

    text = _DATE.sub(take_date, text)
    for match in _NUMBER.findall(text):
        cleaned = match.replace(",", "").rstrip(".")
        try:
            values.append(Value(match.rstrip(".,"), number=float(cleaned)))
        except ValueError:
            continue
    return values


def extract_numbers(text: str) -> list[float]:
    return [v.number for v in extract_values(text) if v.number is not None]


def _matches(value: Value, numbers: list[float], dates: set[str]) -> bool:
    if value.date is not None:
        return value.date in dates
    for k in numbers:
        if k == value.number or (k != 0 and abs(value.number - k) <= TOLERANCE * abs(k)):
            return True
    return False


def check(answer: str, sources: list[str]) -> list[str]:
    """Return the values in `answer` (as written) that no source supports."""
    known = [v for s in sources for v in extract_values(s)]
    numbers = [v.number for v in known if v.number is not None]
    dates = {v.date for v in known if v.date is not None}
    return [v.token for v in extract_values(answer) if not _matches(v, numbers, dates)]
