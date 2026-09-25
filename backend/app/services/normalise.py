"""Normalisation rules (guide section 7.3). Shared by the upload API and the fact extractor.

Everything here is a pure function on text, so each rule is easy to unit-test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import PeriodType

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# "2023-24", "2023–24", "2023/24", "2023-2024", "FY 2023-24", "F.Y. 2023-24"
_FY_RANGE = re.compile(r"^(?:F\.?\s*Y\.?)?\s*(\d{4})\s*[-–—/]\s*(\d{2}|\d{4})$", re.IGNORECASE)
# "FY24", "FY 24", "FY2024" (Indian convention: the year the FY ends in, so FY24 = 2023-24)
_FY_END = re.compile(r"^F\.?\s*Y\.?\s*(\d{2}|\d{4})$", re.IGNORECASE)


def to_ascii_digits(text: str) -> str:
    return text.translate(_DEVANAGARI_DIGITS)


def normalise_fy(value: str | None) -> str | None:
    """Return "FY 2023-24" style, None for blank input. Raises ValueError if unrecognised."""
    if value is None or not value.strip():
        return None
    text = to_ascii_digits(value.strip())

    if m := _FY_RANGE.match(text):
        start, end = int(m.group(1)), m.group(2)
        end_year = int(end) if len(end) == 4 else (start // 100) * 100 + int(end)
        if end_year == start + 1 or (len(end) == 2 and end_year + 100 == start + 1):
            return f"FY {start}-{(start + 1) % 100:02d}"
    elif m := _FY_END.match(text):
        end = int(m.group(1))
        end_year = end if end >= 1000 else 2000 + end
        start = end_year - 1
        return f"FY {start}-{end_year % 100:02d}"

    raise ValueError(f"Financial year not understood: {value!r}. Use a form like FY 2024-25.")


def _fy(start: int) -> str:
    return f"FY {start}-{(start + 1) % 100:02d}"


def clean_text(text: str | None) -> str:
    """One line, ASCII digits, plain dashes and quotes: the form every matcher below expects."""
    if not text:
        return ""
    text = to_ascii_digits(text)
    text = re.sub(r"[–—−]", "-", text)
    text = re.sub(r"[’‘`´]", "'", text)
    return " ".join(text.split())


# --- Numbers ------------------------------------------------------------------------------

_EMPTY_CELLS = {"", "-", "--", "na", "n.a.", "n.a", "n/a", "nil", "..", "...", "*", "x"}
_TRAILING_MARKS = re.compile(
    r"(?:\s*(?:[*#@$^†]+|\((?:p|prov\.?|provisional|r|e|rev\.?)\)))+$", re.IGNORECASE
)
_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def parse_number(text: str | None) -> float | None:
    """Parse a table cell as a number, or None if it is empty or not a plain number.

    Commas are removed for both Indian (1,23,456) and western (123,456) grouping, footnote
    marks and "(P)" provisional tags are ignored, "(12.5)" is negative, and "-" / "NA" are
    empty (guide 7.3). Anything with other text in it ("9%", "▲ 2.1") is not a number.
    """
    if text is None:
        return None
    s = clean_text(text)
    if s.lower() in _EMPTY_CELLS:
        return None
    s = _TRAILING_MARKS.sub("", s).strip()
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1].strip()
    s = s.replace(",", "")
    if not _NUMBER.match(s):
        return None
    value = float(s)
    return -value if negative else value


# --- Units --------------------------------------------------------------------------------

MASS, VOLUME, OTHER = "mass", "volume", "other"
_T = r"(?:metric\s*)?(?:tonnes?|tons?|te|t)"  # tonne spellings
_CUM = r"(?:cu(?:bic)?\s*m(?:etres?|eters?|trs?)?|m3|cum)"  # cubic metre spellings


@dataclass(frozen=True)
class Unit:
    label: str  # the unit as we store it in facts.unit, e.g. "Lakh tonnes"
    kind: str  # MASS (standard MT) | VOLUME (standard Mcum) | OTHER (money, %, counts...)
    to_std: float | None  # multiply a value by this to get MT or Mcum


# Checked in order, most specific first ("lakh MT" must not be read as "MT").
_UNIT_RULES: list[tuple[re.Pattern[str], Unit]] = [
    (re.compile(p, re.IGNORECASE), u)
    for p, u in [
        (
            rf"\b(?:million|mill?|mn)\s*{_CUM}\b|\bm\s?cum\b|\bmm3\b|\bmcm\b",
            Unit("Mcum", VOLUME, 1),
        ),
        (rf"\blakh\s*{_CUM}\b|\blcum\b", Unit("Lakh cum", VOLUME, 0.1)),
        (rf"(?:\bthousand|'000|\b000)\s*{_CUM}\b", Unit("Thousand cum", VOLUME, 0.001)),
        (rf"\b{_CUM}\b", Unit("Cum", VOLUME, 1e-6)),
        (rf"\bbillion\s*{_T}\b|\bbt\b", Unit("Billion tonnes", MASS, 1000)),
        (rf"\bcrore\s*(?:{_T}|mt)\b", Unit("Crore tonnes", MASS, 10)),
        (rf"\blakh\s*(?:{_T}|mt)\b|\blt\b|लाख\s*टन", Unit("Lakh tonnes", MASS, 0.1)),
        (
            rf"(?:\bthousand|\bth|'000|\b000)\s*(?:{_T}|mt)\b|हजार\s*टन|हज़ार\s*टन",
            Unit("Thousand tonnes", MASS, 0.001),
        ),
        (rf"\b(?:million|mill?|mn)\s*{_T}\b|\bmmt\b|\bmts?\b|मिलियन\s*टन", Unit("MT", MASS, 1)),
        (r"\b(?:tonnes?|tons?|te)\b", Unit("Tonnes", MASS, 1e-6)),
        (
            r"%|\bpercent|\brs\b|₹|\brupees?\b|\binr\b|\bcrores?\b|\blakh\s*m\b|\bmw\b|\bmu\b"
            r"|\bkwh\b|\bgw\b|\bkm\b|\brakes?\b|\bwagons?\b|\bkcal\b",
            Unit("other", OTHER, None),
        ),
    ]
]


def find_unit(text: str | None) -> Unit | None:
    """Find the unit mentioned in a header or title ("Production (Lakh Te)" -> Lakh tonnes)."""
    # Dots dropped so "M.T.", "M.Cum", "mill. te" and "Rs. Cr." all look like their plain form.
    t = clean_text(text).replace(".", "")
    for pattern, unit in _UNIT_RULES:
        if pattern.search(t):
            return unit
    return None


# --- Subsidiaries ---------------------------------------------------------------------------

CIL_SUBSIDIARIES = frozenset({"ECL", "BCCL", "CCL", "WCL", "SECL", "NCL", "MCL", "NEC"})
ALL_INDIA = "INDIA"  # facts.subsidiary for an all-India total

# Longer names first, so "North Eastern Coalfields" is not also read as ECL.
_SUBSIDIARY_ALIASES: list[tuple[str, str]] = sorted(
    [
        ("SECL", r"south\s*-?\s*eastern\s+coalfields?"),
        ("NEC", r"north\s*-?\s*eastern\s+coalfields?"),
        ("ECL", r"eastern\s+coalfields?"),
        ("BCCL", r"bharat\s+coking\s+coal"),
        ("CCL", r"central\s+coalfields?"),
        ("WCL", r"western\s+coalfields?"),
        ("NCL", r"northern\s+coalfields?"),
        ("MCL", r"mahanadi\s+coalfields?"),
        ("CIL", r"coal\s+india"),
        ("CIL", r"कोल\s*इंडिया"),
        ("SCCL", r"singareni(?:\s+collieries)?"),
        ("SCCL", r"सिंगरेनी"),
        ("CAPTIVE", r"captives?(?:\s*(?:/|&|and)\s*(?:others?|commercial))?"),
    ],
    key=lambda a: -len(a[1]),
) + [(code, rf"\b{code.lower()}\b") for code in sorted(CIL_SUBSIDIARIES | {"CIL", "SCCL"})]
_SUBSIDIARY_PATTERNS = [(code, re.compile(p, re.IGNORECASE)) for code, p in _SUBSIDIARY_ALIASES]


def match_subsidiaries(text: str | None) -> tuple[set[str], str]:
    """Return the subsidiary codes named in `text`, and the text with those names removed.

    "Mahanadi Coalfields", "MCL" and "M.C.L." all give MCL (guide 7.3 alias map).
    """
    t = clean_text(text)
    t = re.sub(r"(?<![A-Za-z])([A-Za-z])\.", r"\1", t)  # "M.C.L." -> "MCL"
    codes: set[str] = set()
    for code, pattern in _SUBSIDIARY_PATTERNS:
        if pattern.search(t):
            codes.add(code)
            t = pattern.sub(" ", t)
    return codes, " ".join(t.split())


# --- States ----------------------------------------------------------------------------------

_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Jammu & Kashmir", "Ladakh", "Puducherry", "Delhi",
]  # fmt: skip
_STATE_KEYS = {re.sub(r"[^a-z]", "", s.lower()): s for s in _STATES} | {
    "orissa": "Odisha",
    "chattisgarh": "Chhattisgarh",
    "tamilnadu": "Tamil Nadu",
    "jammukashmir": "Jammu & Kashmir",
    "jk": "Jammu & Kashmir",
    "pondicherry": "Puducherry",
}


def match_state(text: str | None) -> str | None:
    """The state's standard name if the whole label is a state ("ODISHA", "Orissa")."""
    t = clean_text(text).lower()
    return _STATE_KEYS.get(re.sub(r"[^a-z]", "", t)) or _STATE_KEYS.get(
        re.sub(r"[^a-z]", "", re.sub(r"\band\b", "", t))
    )


# --- Periods ---------------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "जनवरी": 1, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6, "जुलाई": 7,
    "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "अक्तूबर": 10,
    "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12,
}  # fmt: skip
_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r"|जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|सितम्बर|अक्टूबर|अक्तूबर|नवंबर|नवम्बर"
    r"|दिसंबर|दिसम्बर)"
)
_M = rf"(?<![a-z]){_MONTH}(?![a-z])"  # a month name as a whole word
_CUMULATIVE = re.compile(
    rf"\bup\s*to\b|\bupto\b|\btill\b|\bcumulative|\bprogressive|\bytd\b|\bso\s+far\b"
    rf"|{_M}\s*'?\s*(?:\d{{2,4}})?\s*(?:-|to)\s*{_M}",
    re.IGNORECASE,
)
_PROJECTED = re.compile(r"\bproj|\bestimat|\banticipat|\bforecast|\blikely\b", re.IGNORECASE)
_DATE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?[\s./-]+(\d{{1,2}}|{_MONTH})[\s./,-]+(\d{{4}})\b", re.IGNORECASE
)
_MONTH_YEAR = re.compile(rf"({_M})[\s'.,-]*(\d{{4}}|\d{{2}})(?!\d)", re.IGNORECASE)
_FY_LONG = re.compile(r"(?<!\d)(\d{4})\s*[-/]\s*(\d{4}|\d{2})(?!\d)")
_FY_SHORT_RANGE = re.compile(r"\bFY\s*'?(\d{2})\s*-\s*'?(\d{2})(?!\d)", re.IGNORECASE)
_FY_SHORT = re.compile(r"\bFY\s*'?(\d{4}|\d{2})(?!\d)", re.IGNORECASE)
_YY_RANGE = re.compile(r"(?<![\d.])(\d{2})\s*-\s*(\d{2})(?![\d.])")
_BARE_MONTH = re.compile(_M, re.IGNORECASE)


@dataclass(frozen=True)
class PeriodHint:
    """What a header, row label or title says about the period of the numbers under it."""

    months: frozenset[str] = frozenset()  # "2024-12" (explicit month + year, or a dated day)
    fys: frozenset[str] = frozenset()  # "FY 2024-25"
    bare_month: int | None = None  # "during Dec": a month without a year
    cumulative: bool = False  # "upto Dec", "Apr-Nov": a range, not one period we can store
    projected: bool = False  # "(Proj.)", "estimated": not an actual figure

    @property
    def empty(self) -> bool:
        return not (self.months or self.fys or self.bare_month)


def _month_no(name: str) -> int:
    name = name.lower()
    return _MONTHS.get(name[:3], _MONTHS.get(name, 0))


def _year(text: str) -> int:
    y = int(text)
    return y if y >= 1000 else 2000 + y


def find_period(text: str | None) -> PeriodHint:
    """Read every period mentioned in a header / label / title (guide 7.3 period rules).

    FY forms (2023-24, FY24, FY 23-24, 2023-2024) give "FY 2023-24"; months give "2024-12";
    a date like "As on 01.04.2024" gives its month. The caller decides what to do when more
    than one period, a range, or a projection is mentioned.
    """
    t = clean_text(text)
    months: set[str] = set()
    fys: set[str] = set()

    for m in _DATE.finditer(t):
        month = int(m.group(2)) if m.group(2).isdigit() else _month_no(m.group(2))
        if 1 <= month <= 12:
            months.add(f"{int(m.group(3))}-{month:02d}")
    t_nodate = _DATE.sub(" ", t)
    for m in _MONTH_YEAR.finditer(t_nodate):
        months.add(f"{_year(m.group(2))}-{_month_no(m.group(1)):02d}")
    t_rest = _MONTH_YEAR.sub(" ", t_nodate)

    for m in _FY_LONG.finditer(t_rest):
        start, end = int(m.group(1)), m.group(2)
        end_year = int(end) if len(end) == 4 else (start // 100) * 100 + int(end)
        if end_year % 100 == (start + 1) % 100 and (len(end) == 2 or end_year == start + 1):
            fys.add(_fy(start))
        elif len(end) == 2 and 1 <= int(end) <= 12 and m.group(0).count("-") == 1:
            months.add(f"{start}-{int(end):02d}")  # ISO month such as 2024-12
    t_rest = _FY_LONG.sub(" ", t_rest)
    for m in _FY_SHORT_RANGE.finditer(t_rest):
        if int(m.group(2)) == (int(m.group(1)) + 1) % 100:
            fys.add(_fy(2000 + int(m.group(1))))
    t_rest = _FY_SHORT_RANGE.sub(" ", t_rest)
    for m in _FY_SHORT.finditer(t_rest):
        fys.add(_fy(_year(m.group(1)) - 1))
    t_rest = _FY_SHORT.sub(" ", t_rest)
    for m in _YY_RANGE.finditer(t_rest):  # "Target 24-25"
        if int(m.group(2)) == (int(m.group(1)) + 1) % 100:
            fys.add(_fy(2000 + int(m.group(1))))

    bare = _BARE_MONTH.search(_YY_RANGE.sub(" ", t_rest))
    return PeriodHint(
        months=frozenset(months),
        fys=frozenset(fys),
        bare_month=_month_no(bare.group(0)) if bare else None,
        cumulative=bool(_CUMULATIVE.search(t)),
        projected=bool(_PROJECTED.search(t)),
    )


def month_in_fy(month: int, fy: str) -> str:
    """Month number inside a financial year -> "YYYY-MM" (April-March: Dec of FY 2024-25 is
    2024-12, Jan of FY 2024-25 is 2025-01)."""
    start = int(fy[3:7])
    return f"{start if month >= 4 else start + 1}-{month:02d}"


def fy_of_month(month: str) -> str:
    """ "2024-12" -> "FY 2024-25", "2025-01" -> "FY 2024-25"."""
    year, mm = int(month[:4]), int(month[5:7])
    return _fy(year if mm >= 4 else year - 1)


def resolve_period(hint: PeriodHint) -> tuple[PeriodType, str] | None:
    """One clear period from one hint, or None if it names none or several."""
    if len(hint.months) == 1 and len(hint.fys) <= 1:
        return PeriodType.MONTH, next(iter(hint.months))
    if not hint.months and len(hint.fys) == 1:
        fy = next(iter(hint.fys))
        if hint.bare_month:
            return PeriodType.MONTH, month_in_fy(hint.bare_month, fy)
        return PeriodType.FY, fy
    return None
