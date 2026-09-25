"""Read a Parliament Question out of the text of an ingested PQ answer (guide sections 10-11).

The Ministry's PQ answer PDFs all start with the same header:

    GOVERNMENT OF INDIA / MINISTRY OF COAL / LOK SABHA
    UNSTARRED QUESTION NO. 3749 / TO BE ANSWERED ON 11.12.2019
    <subject line>
    3749. SHRI GAURAV GOGOI:
    Will the Minister of COAL be pleased to state:
    (a) whether ...
    ANSWER
    MINISTER OF PARLIAMENTARY AFFAIRS, COAL AND MINES
    ...

Older files are scans whose text layer came from OCR, so the patterns look at the shape of
the header rather than exact spelling ("AITSWER", "2O21", "I,OK SABIIA"). Pure functions, no
database, so it is unit-tested on real header text. The Hindi header words (लोक सभा,
अतारांकित प्रश्न, उत्तर) are understood too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.models.enums import House, QuestionType


@dataclass
class ParsedPq:
    house: House | None
    q_type: QuestionType
    q_no: str | None
    answer_date: date | None
    subject: str | None
    mp_names: list[str]
    question_text: str
    answer_text: str | None
    parts: list[dict] = field(default_factory=list)  # [{"label": "a", "text": "..."}]


_LS = re.compile(r"\b[LIT1][,.]?OK\s+[ST]\S{2,6}|लोक\s*सभा")
_RS = re.compile(r"RAJYA\s+S\S{2,6}|राज्य\s*सभा", re.I)
_UNSTARRED = re.compile(r"\S{0,3}NS\S{0,2}ARR?\S{0,2}D|UN-\s*STARRED|अतारांकित", re.I)
_STARRED = re.compile(r"STARR?ED|तारांकित", re.I)
_Q_LINE = re.compile(r"Q\S{2,8}\s+N\S{0,3}|प्रश्न", re.I)
_TRAILING_NO = re.compile(r"([0-9OoIlS][0-9OoIlS ]{0,6}[0-9Il])\s*$")
_DATE = re.compile(
    r"(?<![0-9])([0-9OoIlLEBA()]{1,4})\s*[.,/-]\s*([0-9OoIlLEBA(),]{1,4})\s*[.,/-]\s*"
    r"((?:19|20|2O|2o)/?[0-9OoIlL]{2})(?![0-9])"
)
# The minister's name line that starts every answer: "MINISTER OF PARLIAMENTARY AFFAIRS, ..."
# (OCR: "MINISTIR OF ...", "MINISTER Otr'PARLIAMENTARY ...").
_MINISTER_LINE = re.compile(
    r"^\W{0,2}M\S{4,7}\s+O\S{0,3}\s*(?:PAR|STATE|COAL|FOR)|^मंत्री|^कोयला\s+.*मंत्री", re.I
)
_ANSWER = re.compile(r"^\s*(?:AN\S{2,4}R|उत्तर)\s*$", re.I)
# "Will the Minister of COAL be pleased to state:"; OCR gives "VIiII the Mlalster ofCoal".
_WILL_MINISTER = re.compile(r"^\S{1,6}(?:\s+\S)?\s+th\S\s+M\S{3,8}\s*of|क्या\s+\S*\s*मंत्री", re.I)
_STATE = re.compile(r"\S?tate\S{0,2}\s*$|बताने\s+की\s+कृपा\s+करेंगे", re.I)
# The first MP line starts with the question number: "3749. SHRI X:", "*142. SHRI X:",
# "1681 SHRI X:", "I 1628. SHRI X".
_MP_PREFIX = r"^\W{0,2}[^\s0-9]?\s?\*?([0-9OoIlSA]{1,5})\s*\.?\s+"
_MP_NUMBER = re.compile(_MP_PREFIX + r"\S")
_PART = re.compile(r"(?:^|\s)\(([a-hA-H])\)\s*")
_OCR_DIGITS = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "L": "1",
        "S": "5",
        "E": "8",
        "B": "8",
        "A": "8",
        ",": "",
        "/": "",
    }
)


def _digits(text: str) -> str:
    """Undo OCR letter-for-digit slips inside a number: '2O2L' -> '2021'."""
    return text.replace("()", "0").translate(_OCR_DIGITS).replace(" ", "")


def parse_house(header: str) -> House | None:
    if _RS.search(header):
        return House.RAJYA_SABHA
    if _LS.search(header):
        return House.LOK_SABHA
    return None


def parse_q_type(header: str) -> QuestionType:
    if _UNSTARRED.search(header):
        return QuestionType.UNSTARRED
    if _STARRED.search(header):
        return QuestionType.STARRED
    return QuestionType.UNSTARRED  # most PQs are unstarred; the header may be unreadable


def parse_answer_date(line: str) -> date | None:
    """'TO BE ANSWERED ON 28.O7.2O2L' -> 2021-07-28."""
    m = _DATE.search(line)
    if not m:
        return None
    try:
        day, month, year = (int(_digits(g)) for g in m.groups())
        return date(year, month, day)
    except ValueError:
        return None


def split_parts(question: str) -> list[dict]:
    """'(a) whether ... (b) the extent ...' -> [{"label": "a", "text": "whether ..."}, ...]."""
    pieces = _PART.split(question)
    parts = []
    for i in range(1, len(pieces) - 1, 2):
        text = " ".join(pieces[i + 1].split()).rstrip(" ;")
        if text:
            parts.append({"label": pieces[i].lower(), "text": text})
    return parts


def _answer_start(lines: list[str], after: int) -> int | None:
    """Index of the "ANSWER" line (or of the minister line when "ANSWER" is unreadable)."""
    for i in range(after, len(lines)):
        if _ANSWER.match(lines[i]):
            return i
        if _MINISTER_LINE.match(lines[i]):
            prev = lines[i - 1]
            # A garbled "ANSWER" just above the minister line is a short single word.
            return i - 1 if i - 1 > after and len(prev) <= 12 and " " not in prev else i
    return None


def _strip_number(mp_line: str) -> str:
    return re.sub(_MP_PREFIX, "", mp_line).strip(" :")


def parse_pq(text: str) -> ParsedPq | None:
    """Parse the full text of a PQ answer. None if it does not look like one."""
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    will_at = next((i for i, ln in enumerate(lines[:60]) if _WILL_MINISTER.search(ln)), None)
    if will_at is None:
        return None
    answer_at = _answer_start(lines, will_at + 1)
    if answer_at is None:
        return None
    date_at = next((i for i, ln in enumerate(lines[:will_at]) if _DATE.search(ln)), None)
    header_end = date_at if date_at is not None else min(4, will_at - 1)
    header = "\n".join(lines[: header_end + 1])

    # Between the date line and "Will the Minister": the subject, then one line per MP. The
    # first MP line is the first one that ends with ":" or starts with the question number.
    between = lines[header_end + 1 : will_at]
    first_mp = next(
        (i for i, ln in enumerate(between) if ln.endswith(":") or _MP_NUMBER.match(ln)),
        len(between),
    )
    subject = " ".join(between[:first_mp]).strip() or None
    mp_lines = between[first_mp:]

    q_line = next((ln for ln in lines[: header_end + 1] if _Q_LINE.search(ln)), "")
    q_no_match = _TRAILING_NO.search(q_line)
    q_no = _digits(q_no_match.group(1)) if q_no_match else None
    if not (q_no and q_no.isdigit()) and mp_lines:
        first = _MP_NUMBER.match(mp_lines[0])
        q_no = _digits(first.group(1)) if first else None
    if q_no and not q_no.isdigit():
        q_no = None

    # Drop the "Will the Minister ... be pleased to state:" sentence (one or two lines).
    skip = 1
    if not _STATE.search(lines[will_at]) and will_at + 1 < answer_at:
        skip = 2 if _STATE.search(lines[will_at + 1]) else 1
    question = " ".join(" ".join(lines[will_at + skip : answer_at]).split())
    if not question:
        return None
    answer = " ".join(" ".join(lines[answer_at + 1 :]).split()) or None
    return ParsedPq(
        # An unreadable header house: the answer body usually says "Lok Sabha Starred ...".
        house=parse_house(header) or parse_house(text),
        q_type=parse_q_type(header),
        q_no=q_no[:16] if q_no else None,
        answer_date=parse_answer_date(lines[date_at]) if date_at is not None else None,
        subject=subject[:500] if subject else None,
        mp_names=[n for n in (_strip_number(ln) for ln in mp_lines) if n],
        question_text=question,
        answer_text=answer,
        parts=split_parts(question),
    )
