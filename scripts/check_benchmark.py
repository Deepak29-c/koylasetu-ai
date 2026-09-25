"""Check eval/pq_benchmark.jsonl, the benchmark of past Parliament questions (guide 15.2, #16).

Every line must be one JSON object in the format eval/run_eval.py reads: id, house, date,
question, official_answer, expected_numbers [{"value", "unit"}], topic. Extra fields
(question_no, title, source_url, ...) are allowed. Each expected number may also have an
optional "label" saying which figure it is (e.g. "CIL supply to Andhra Pradesh 2021-22"),
used where the figure comes from a table or could be confused with another one.

Units must come from UNITS below, so the runner can compare like with like.

For every expected number it checks that the value occurs in the official answer as a
standalone number with the right sign: 42871 matches "42,871" (and Indian "4,28,710"
grouping), 13.2 matches "13.20", 1313 matches "Rs.1,313", -0.382 matches "-0.382" but not
"0.382"; 12 does not match inside "112", "12.5", "G12" or "-12". A number at the end of a
range ("1192-1325") counts. It does NOT check the unit or that the right cell or sentence
was meant: that is what the labels and the hand spot-checks are for.

Usage: python scripts/check_benchmark.py [path]   (exit code 1 if anything is wrong)
"""

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "eval" / "pq_benchmark.jsonl"
REQUIRED = {
    "id": str,
    "house": str,
    "date": str,
    "question": str,
    "official_answer": str,
    "expected_numbers": list,
    "topic": str,
}
HOUSES = {"LS", "RS"}
NUMBER_KEYS = {"value", "unit", "label"}
# The controlled vocabulary of units. MT = million tonnes, MTPA = million tonnes per annum
# (capacities and annual linkages), BU = billion units, count = a number of things (mines,
# agreements, FIRs ...; the label says what).
UNITS = {
    "MT",
    "MTPA",
    "MT/day",
    "thousand tonnes",
    "tonnes/year",
    "tonnes/day",
    "rakes/day",
    "BU",
    "MW",
    "GW",
    "%",
    "Rs crore",
    "Rs/tonne",
    "days",
    "years",
    "count",
}
MINUS = "-−"


def number_pattern(value: float | int) -> re.Pattern:
    """Regex for the digits of abs(value) as they may be printed: optional commas between
    digits (Western or Indian grouping), trailing zeros after the decimal point allowed,
    not followed by more digits. What comes before is checked in number_in_text."""
    text = f"{abs(value):f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
    whole, _, frac = text.lstrip("-").partition(".")
    digits = ",?".join(whole)  # a comma may sit between any two digits
    tail = rf"\.{frac}0*" if frac else r"(?:\.0+)?"
    return re.compile(rf"(?<!\d){digits}{tail}(?![\d]|[.,]\d)")


def _standalone_with_sign(text: str, start: int, negative: bool) -> bool:
    before = text[start - 1] if start else " "
    if before in ".,":
        # "Rs.1,313" is fine; ".5" or "1,5" is part of another number
        return text[max(0, start - 3) : start].lower() == "rs." and not negative
    if before.isalpha():  # a label like "G10" or "Wash-IV"
        return False
    if before in MINUS:
        # a minus sign only if it does not join two words/numbers ("9-10", "2014-15")
        is_sign = start < 2 or not text[start - 2].isalnum()
        return is_sign == negative
    return not negative


def number_in_text(value: float | int, text: str) -> bool:
    """True if value occurs in text as a standalone number with the same sign."""
    return any(
        _standalone_with_sign(text, m.start(), value < 0)
        for m in number_pattern(value).finditer(text)
    )


def check_number(i: int, num: object, answer: str) -> list[str]:
    where = f"expected_numbers[{i}]"
    if not isinstance(num, dict) or not {"value", "unit"} <= set(num):
        return [f"{where} needs value and unit"]
    errors = [f"{where} has unknown key {k!r}" for k in sorted(set(num) - NUMBER_KEYS)]
    value, unit = num["value"], num["unit"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"{where}.value should be a number")
    elif unit not in UNITS:
        errors.append(f"{where}.unit {unit!r} is not one of the allowed units")
    elif not number_in_text(value, answer):
        errors.append(f"{where} {value} {unit} is not in official_answer")
    if "label" in num and (not isinstance(num["label"], str) or not num["label"].strip()):
        errors.append(f"{where}.label should be a non-empty string")
    return errors


def check_entry(entry: object) -> list[str]:
    """Problems with one benchmark line; an empty list means it is fine."""
    if not isinstance(entry, dict):
        return ["not a JSON object"]
    errors = []
    for field, kind in REQUIRED.items():
        if field not in entry:
            errors.append(f"missing {field}")
        elif not isinstance(entry[field], kind):
            errors.append(f"{field} should be {kind.__name__}")
        elif kind is str and not entry[field].strip():
            errors.append(f"{field} is empty")
    if errors:
        return errors
    if entry["house"] not in HOUSES:
        errors.append(f"house should be LS or RS, got {entry['house']!r}")
    try:
        date.fromisoformat(entry["date"])
    except ValueError:
        errors.append(f"date should be YYYY-MM-DD, got {entry['date']!r}")
    for i, num in enumerate(entry["expected_numbers"]):
        errors += check_number(i, num, entry["official_answer"])
    return errors


def check_file(path: Path) -> tuple[list[dict], list[str]]:
    """(entries, problems) for the whole file, including duplicate ids and blank lines."""
    entries, problems, seen = [], [], set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            problems.append(f"line {n}: blank line")
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            problems.append(f"line {n}: not valid JSON ({e.msg})")
            continue
        problems += [f"line {n}: {p}" for p in check_entry(entry)]
        if isinstance(entry, dict):
            if entry.get("id") in seen:
                problems.append(f"line {n}: duplicate id {entry.get('id')}")
            seen.add(entry.get("id"))
            entries.append(entry)
    return entries, problems


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PATH
    entries, problems = check_file(path)
    for p in problems:
        print(p)
    numbers = sum(len(e.get("expected_numbers", [])) for e in entries)
    print(f"{len(entries)} questions, {numbers} expected numbers, {len(problems)} problems")
    for topic, count in Counter(e.get("topic") for e in entries).most_common():
        print(f"  {topic}: {count}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
