"""Check eval/pq_benchmark.jsonl, the benchmark of past Parliament questions (guide 15.2, #16).

Every line must be one JSON object in the format eval/run_eval.py reads: id, house, date,
question, official_answer, expected_numbers [{"value", "unit"}], topic. Extra fields
(question_no, title, source_url, ...) are allowed.

It also checks that every expected number really appears in the official answer, so no
figure in the benchmark is made up: 42871 matches "42,871" (and Indian "4,28,710" style
grouping), 13.2 matches "13.20", and 12 does not match inside "112" or "12.5".

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


def number_pattern(value: float | int) -> re.Pattern:
    """Regex for a number as it may be printed: digit groups with optional commas (Western
    or Indian grouping), trailing zeros after the decimal point allowed, not part of a
    longer number."""
    text = f"{abs(value):f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
    whole, _, frac = text.lstrip("-").partition(".")
    digits = ",?".join(whole)  # a comma may sit between any two digits
    tail = rf"\.{frac}0*" if frac else r"(?:\.0+)?"
    return re.compile(rf"(?<![\d.,]){digits}{tail}(?![\d]|[.,]\d)")


def number_in_text(value: float | int, text: str) -> bool:
    return bool(number_pattern(value).search(text))


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
        if not isinstance(num, dict) or set(num) < {"value", "unit"}:
            errors.append(f"expected_numbers[{i}] needs value and unit")
            continue
        value, unit = num["value"], num["unit"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"expected_numbers[{i}].value should be a number")
        elif not isinstance(unit, str) or not unit.strip():
            errors.append(f"expected_numbers[{i}].unit should be a non-empty string")
        elif not number_in_text(value, entry["official_answer"]):
            errors.append(f"expected_numbers[{i}] {value} {unit} is not in official_answer")
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
