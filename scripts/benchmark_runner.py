"""Benchmark runner (guide section 15.2, issue #11): how accurate the Q&A really is.

Asks every question in eval/pq_benchmark.jsonl through the running API (POST /qa/ask, as the
demo analyst), compares the figures in each answer with the official answer's
expected_numbers, and writes a dated result folder. The command line is eval/run_eval.py;
the logic lives here so CI lints and tests it.

Metric definitions (all computed by the functions below):

- Figure found: an expected number counts as found when some number in the system's answer
  (answer text plus the cells of the answer table, if any) equals it within 0.5% after unit
  conversion. Units are read from the words right after the number (and "Rs"/"₹" before it):
  "4.2 lakh tonnes" = 0.42 MT, "42,000 tonnes" = 0.042 MT, "1.2 GW" = 1,200 MW, "Rs 2,000
  crore", "Rs.1,313 per tonne", "84.2%". Indian and Western digit grouping both work. A number
  with no unit word next to it is compared as written, except for % figures: an expected %
  must be written as % / per cent in the answer ("% must stay %"). A number whose unit is of a
  different kind (12% for 12 MT, 12 MW for 12 MT, 1.3 MT/day for 1.3 MTPA) is "wrong unit",
  not found. "Per year" / "per day" only conflict when both sides say it: "27.18 MT of annual
  linkage" matches 27.18 MTPA. Signs are ignored ("fell by 2.5%" matches -2.5 %), because
  answers usually say a decrease in words.
- Unsupported number: a number in the answer (not a date, citation id or "Table 2" reference)
  that does not occur, within 0.5%, in the official answer or the question. These are not
  necessarily wrong (the system may know a newer figure) but are worth a look.
- Numeric accuracy = expected figures found / all expected figures of the questions asked.
  Errors and "not found" replies count as misses here; "among answered" leaves them out.
- All-correct rate = questions where every expected figure was found / questions asked.
- Grounded % = answers the API marked grounded / answered questions (not errors, not "not
  found": a not-found reply has no figures, so it is trivially grounded).
- Not found = replies the API marked not_found. Errors = timeouts, connection failures and
  non-200 responses (e.g. 503 when the local model is down); the run records them and goes on.
- Latency: the API's own latency_ms (p50 / average / max over successful replies), plus the
  wall-clock time the runner waited, which includes the network.
- Citation correctness % (manual, guide 15.2): up to 20 answered questions with citations are
  written to citation_check.csv; a person fills the "correct" column with Y or N per citation,
  then `run_eval.py --rescore <folder>` reports Y / (Y + N).
- Time saved % (manual): from a CSV of timed trials (id, manual_seconds, assisted_seconds),
  1 - total assisted time / total manual time. Given with --time-trials.
- Automation % (guide 15.2): facts auto-accepted without review / all facts, counted in the
  database when --database-url is given: VERIFIED facts that have no review_actions row, over
  all facts. Nothing marks facts VERIFIED automatically yet, so today it reads 0% or n/a.

Output: eval/results/<run date>/ with results.json (every API reply and its scoring),
summary.json (the headline numbers, for the Metrics screen), report.md (readable) and
citation_check.csv. results.json and the CSV hold answer text and passages from our documents,
so they are git-ignored; summary.json and report.md hold only ids, counts and labels and may
be committed to track accuracy over time.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "backend"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import check_benchmark  # noqa: E402  (sibling script: loads and validates the benchmark)

from app.services import grounding  # noqa: E402  (same number reading as the API's check)

TOLERANCE = 0.005  # ±0.5%, as in the grounding check (guide 9.1 / 15.2)
RESULTS_DIR = ROOT / "eval" / "results"
DEFAULT_EMAIL = "analyst@koylasetu.local"
CITATION_SAMPLE = 20
CITATION_FIELDS = [
    "question_id",
    "citation_id",
    "kind",
    "document",
    "page",
    "answer",
    "cited_text",
    "correct",
    "note",
]

# --- Units ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class UnitSpec:
    kind: str  # mass | percent | power | energy | money | money_per_tonne | rakes | days ...
    scale: float  # multiply to get the kind's base unit (MT, MW, BU, Rs crore)
    rate: str | None = None  # "year" | "day" when the unit is per period


# Every unit of the benchmark (scripts/check_benchmark.py UNITS), in base units.
EXPECTED_UNITS: dict[str, UnitSpec] = {
    "MT": UnitSpec("mass", 1),
    "MTPA": UnitSpec("mass", 1, "year"),
    "MT/day": UnitSpec("mass", 1, "day"),
    "thousand tonnes": UnitSpec("mass", 1e-3),
    "tonnes/year": UnitSpec("mass", 1e-6, "year"),
    "tonnes/day": UnitSpec("mass", 1e-6, "day"),
    "rakes/day": UnitSpec("rakes", 1, "day"),
    "BU": UnitSpec("energy", 1),
    "MW": UnitSpec("power", 1),
    "GW": UnitSpec("power", 1000),
    "%": UnitSpec("percent", 1),
    "Rs crore": UnitSpec("money", 1),
    "Rs/tonne": UnitSpec("money_per_tonne", 1),
    "days": UnitSpec("days", 1),
    "years": UnitSpec("years", 1),
    "count": UnitSpec("count", 1),
}

_MASS_SCALE = {
    "lakh": 0.1,
    "lakhs": 0.1,
    "lac": 0.1,
    "lacs": 0.1,
    "crore": 10,
    "crores": 10,
    "billion": 1000,
    "million": 1,
    "mill": 1,
    "mil": 1,
    "mn": 1,
    "thousand": 1e-3,
    "'000": 1e-3,
}
_RATE = (
    r"\s*(?:\([^)]{0,12}\)\s*)?(?:of\s+[a-z]+\s+)?"  # "(MT) of coal per day"
    r"(?P<rate>per\s+annum|per\s+year|/\s*(?:year|annum|yr)|p\.?\s?a\b|a\s+year|annually"
    r"|per\s+day|/\s*day|a\s+day|daily)?"
)
_UNIT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\s*(?:%|per\s*cent\b|percent\b)"), "percent"),
    (re.compile(r"\s*(?:rs\.?\s*)?(?:per|/)\s*(?:tonne|ton|te|t)\b"), "money_per_tonne"),
    (re.compile(r"\s*(?:mtpa|mty)\b"), "mtpa"),
    (
        re.compile(
            r"\s*(?P<scale>lakhs?|lacs?|crores?|billion|million|mill?|mn|thousand|'000)?\.?\s*"
            r"(?:metric\s+)?(?P<t>tonnes?|tons?|te|mmt|mts?|lt)\b" + _RATE
        ),
        "mass",
    ),
    (re.compile(r"\s*rakes?\b" + _RATE), "rakes"),
    (re.compile(r"\s*(?:bu\b|billion\s+units?\b|billion\s+kwh\b)"), "bu"),
    (re.compile(r"\s*(?:mu\b|million\s+units?\b)"), "mu"),
    (re.compile(r"\s*(?:mw\b|megawatts?\b)"), "mw"),
    (re.compile(r"\s*(?:gw\b|gigawatts?\b)"), "gw"),
    (re.compile(r"\s*(?:crores?|cr)\b"), "crore"),
    (re.compile(r"\s*(?:lakhs?|lacs?)\b"), "lakh"),
    (re.compile(r"\s*days?\b"), "days"),
    (re.compile(r"\s*years?\b"), "years"),
]
_RUPEE_BEFORE = re.compile(r"(?:\brs\.?|₹|\binr|rupees)\s*$")


def _rate(m: re.Match) -> str | None:
    rate = (m.groupdict().get("rate") or "").replace(" ", "")
    if not rate:
        return None
    return "day" if "day" in rate or rate == "daily" else "year"


def detect_unit(before: str, after: str) -> UnitSpec | None:
    """The unit written next to a number: `before` is the text just before it, `after` the
    text just after it (both lower case). None when no unit word is there."""
    rupee = bool(_RUPEE_BEFORE.search(before))
    for pattern, name in _UNIT_RULES:
        m = pattern.match(after)
        if not m:
            continue
        if name == "percent":
            return UnitSpec("percent", 1)
        if name == "money_per_tonne":
            return UnitSpec("money_per_tonne", 1)
        if name == "mtpa":
            return UnitSpec("mass", 1, "year")
        if name == "mass":
            scale, t = m.group("scale"), m.group("t")
            if scale:
                size = _MASS_SCALE[scale]
            elif t == "lt":
                size = 0.1  # LT = lakh tonnes
            elif t in ("mt", "mts", "mmt"):
                size = 1  # MT = million tonnes throughout the ministry's papers
            else:
                size = 1e-6  # plain tonnes
            return UnitSpec("mass", size, _rate(m))
        if name == "rakes":
            return UnitSpec("rakes", 1, _rate(m))
        if name in ("bu", "mu"):
            return UnitSpec("energy", 1 if name == "bu" else 1e-3)
        if name in ("mw", "gw"):
            return UnitSpec("power", 1 if name == "mw" else 1000)
        if name in ("crore", "lakh"):
            # "2,000 crore" in these answers is rupees; "crore tonnes" was caught as mass above
            return UnitSpec("money", 1 if name == "crore" else 0.01)
        return UnitSpec(name, 1)
    if rupee:
        return UnitSpec("rupees", 1)  # "Rs 1,313" with no crore / per tonne after it
    return None


# --- Numbers in an answer ------------------------------------------------------------------


@dataclass(frozen=True)
class AnswerNumber:
    token: str  # as written, e.g. "4,28,710"
    value: float  # sign ignored (see module docstring)
    unit: UnitSpec | None


_RS_DOT = re.compile(r"\b(rs|inr)\.\s*", re.IGNORECASE)


def answer_numbers(text: str) -> list[AnswerNumber]:
    """Every figure in the text with the unit written next to it. Dates, citation ids
    ([C1], [F2]), "Table 2" style references and list markers are skipped, exactly as in the
    API's grounding check."""
    t = _RS_DOT.sub("Rs ", grounding._prepare(text))  # "Rs.1,313": the dot hides the number
    t = grounding._DATE.sub(" ", t).lower()
    found = []
    for m in grounding._NUMBER.finditer(t):
        token = m.group(0).rstrip(".,")
        try:
            value = float(token.replace(",", ""))
        except ValueError:
            continue
        before = t[max(0, m.start() - 8) : m.start()]
        after = t[m.start() + len(token) : m.start() + len(token) + 45]
        found.append(AnswerNumber(token, value, detect_unit(before, after)))
    return found


def close(a: float, b: float) -> bool:
    return a == b or (b != 0 and abs(a - b) <= TOLERANCE * abs(b))


def match_expected(expected: dict, numbers: list[AnswerNumber]) -> tuple[str, str | None]:
    """("found" | "wrong_unit" | "missing", the answer token that decided it)."""
    spec = EXPECTED_UNITS[expected["unit"]]
    target = abs(float(expected["value"]))
    wrong_unit = None
    for n in numbers:
        if n.unit is None:
            if spec.kind != "percent" and close(n.value, target):
                return "found", n.token
            continue
        compatible = n.unit.kind == spec.kind or (
            n.unit.kind == "rupees" and spec.kind == "money_per_tonne"
        )
        rates_clash = n.unit.rate and spec.rate and n.unit.rate != spec.rate
        if compatible and not rates_clash:
            if close(n.value * n.unit.scale, target * spec.scale):
                return "found", n.token
        elif close(n.value, target) and wrong_unit is None:
            wrong_unit = n.token
    return ("wrong_unit", wrong_unit) if wrong_unit else ("missing", None)


# --- Scoring one reply ---------------------------------------------------------------------


def system_text(response: dict) -> str:
    """Answer text plus the answer table's cells (the NUMERIC route puts figures there)."""
    parts = [response.get("answer") or ""]
    table = response.get("table") or {}
    for row in table.get("rows") or []:
        parts.append(" ; ".join(str(c) for c in row))
    return "\n".join(parts)


def score_question(entry: dict, record: dict) -> dict:
    """Score one benchmark entry against the runner's record of its API call.

    record: {"ok": bool, "response": dict | None, "error": str | None, "http_status": int | None,
    "wall_ms": int}. Returns the scoring fields added to results.json for this question.
    """
    expected = entry["expected_numbers"]
    response = record.get("response") or {}
    if not record.get("ok"):
        status = "error"
    elif response.get("not_found"):
        status = "not_found"
    else:
        status = "answered"

    text = system_text(response) if status != "error" else ""
    numbers = answer_numbers(text)
    checks = []
    for num in expected:
        result, token = match_expected(num, numbers)
        checks.append({**num, "result": result, "answer_token": token})
    found = sum(c["result"] == "found" for c in checks)
    unsupported = (
        grounding.check(text, [entry["official_answer"], entry["question"]]) if text else []
    )
    return {
        "status": status,
        "expected": checks,
        "found": found,
        "expected_count": len(expected),
        "all_correct": found == len(expected),
        "unsupported_numbers": unsupported,
        "grounded": bool(response.get("grounded")) if status != "error" else None,
    }


# --- Summary -------------------------------------------------------------------------------


def pct(part: float, whole: float) -> float | None:
    return round(100 * part / whole, 1) if whole else None


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (q in 0..100); None for no values."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


def latency_stats(values: list[float]) -> dict:
    return {
        "p50": percentile(values, 50),
        "avg": round(sum(values) / len(values)) if values else None,
        "max": max(values) if values else None,
    }


def summarise(results: list[dict]) -> dict:
    """Headline numbers over the scored results (definitions in the module docstring)."""
    asked = len(results)
    by_status = {s: [r for r in results if r["status"] == s] for s in ("answered", "not_found")}
    errors = [r for r in results if r["status"] == "error"]
    answered = by_status["answered"]
    expected = sum(r["expected_count"] for r in results)
    found = sum(r["found"] for r in results)
    answered_expected = sum(r["expected_count"] for r in answered)
    answered_found = sum(r["found"] for r in answered)
    ok = [r for r in results if r["status"] != "error"]

    topics: dict[str, dict] = {}
    for r in results:
        t = topics.setdefault(
            r["topic"], {"questions": 0, "expected": 0, "found": 0, "all_correct": 0}
        )
        t["questions"] += 1
        t["expected"] += r["expected_count"]
        t["found"] += r["found"]
        t["all_correct"] += r["all_correct"]
    for t in topics.values():
        t["numeric_accuracy_pct"] = pct(t["found"], t["expected"])

    return {
        "questions_asked": asked,
        "answered": len(answered),
        "not_found": len(by_status["not_found"]),
        "errors": len(errors),
        "expected_numbers": expected,
        "found_numbers": found,
        "numeric_accuracy_pct": pct(found, expected),
        "numeric_accuracy_answered_pct": pct(answered_found, answered_expected),
        "all_correct_questions": sum(r["all_correct"] for r in results),
        "all_correct_pct": pct(sum(r["all_correct"] for r in results), asked),
        "grounded_pct": pct(sum(bool(r["grounded"]) for r in answered), len(answered)),
        "unsupported_numbers": sum(len(r["unsupported_numbers"]) for r in results),
        "latency_ms": latency_stats(
            [r["latency_ms"] for r in ok if r.get("latency_ms") is not None]
        ),
        "wall_ms": latency_stats([r["wall_ms"] for r in results if r.get("wall_ms") is not None]),
        "error_kinds": _count(r["error"] for r in errors),
        "by_topic": dict(sorted(topics.items())),
    }


def _count(items: Iterable[str | None]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        key = (item or "unknown").split(":")[0]
        out[key] = out.get(key, 0) + 1
    return out


# --- Manual parts: citation sheet, time trials, automation ---------------------------------


def citation_rows(results: list[dict], sample: int = CITATION_SAMPLE, seed: int = 15) -> list:
    """Rows of the manual citation check: every citation of up to `sample` answered questions
    that have citations, picked at random with a fixed seed so re-runs pick the same ids."""
    cited = sorted(
        (r for r in results if r["status"] == "answered" and r.get("citations")),
        key=lambda r: r["id"],
    )
    picked = sorted(
        random.Random(seed).sample(cited, min(sample, len(cited))), key=lambda r: r["id"]
    )
    rows = []
    for r in picked:
        for c in r["citations"]:
            rows.append(
                {
                    "question_id": r["id"],
                    "citation_id": c.get("id"),
                    "kind": c.get("kind") or ("fact" if c.get("fact_id") else "passage"),
                    "document": c.get("document"),
                    "page": c.get("page"),
                    "answer": r.get("answer", ""),
                    "cited_text": (c.get("text") or "")[:500],
                    "correct": "",
                    "note": "",
                }
            )
    return rows


def write_citation_sheet(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:  # BOM: Excel reads it as UTF-8
        writer = csv.DictWriter(f, fieldnames=CITATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def citation_correctness(path: Path) -> dict | None:
    """Y / (Y + N) from a filled citation sheet; None if the file is missing or unfilled."""
    if not path.exists():
        return None
    with path.open(encoding="utf-8-sig", newline="") as f:
        marks = [(row.get("correct") or "").strip().upper()[:1] for row in csv.DictReader(f)]
    yes, no = marks.count("Y"), marks.count("N")
    if not yes + no:
        return None
    return {"checked": yes + no, "correct": yes, "pct": pct(yes, yes + no)}


def time_saved(path: Path) -> dict:
    """1 - assisted / manual from timed trials (columns id, manual_seconds, assisted_seconds)."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    manual = sum(float(r["manual_seconds"]) for r in rows)
    assisted = sum(float(r["assisted_seconds"]) for r in rows)
    saved = round(100 * (1 - assisted / manual), 1) if manual else None
    return {"trials": len(rows), "manual_s": manual, "assisted_s": assisted, "pct": saved}


AUTOMATION_SQL = (
    "SELECT count(*) AS facts, count(*) FILTER (WHERE f.status = 'VERIFIED' AND NOT EXISTS "
    "(SELECT 1 FROM review_actions r WHERE r.fact_id = f.id)) AS auto_accepted FROM facts f"
)


def automation(database_url: str) -> dict:
    """Facts auto-accepted without review / all facts, counted in the database."""
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            facts, auto = conn.execute(text(AUTOMATION_SQL)).one()
    finally:
        engine.dispose()
    return {"facts": facts, "auto_accepted": auto, "pct": pct(auto, facts)}


# --- Report --------------------------------------------------------------------------------


def _fmt(value: Any, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value}{suffix}"


def render_report(meta: dict, summary: dict, results: list[dict]) -> str:
    s = summary
    cit, ts, auto = meta.get("citations"), meta.get("time_saved"), meta.get("automation")
    lines = [
        f"# Benchmark run {meta['run_date']}",
        "",
        f"API: `{meta['base_url']}` · benchmark: {meta['benchmark_questions']} questions · "
        f"asked: {s['questions_asked']} · runner timeout: {meta['timeout_s']} s",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Numeric accuracy (figures found / expected) | {_fmt(s['numeric_accuracy_pct'], '%')}"
        f" ({s['found_numbers']} of {s['expected_numbers']}) |",
        f"| Numeric accuracy, answered questions only | "
        f"{_fmt(s['numeric_accuracy_answered_pct'], '%')} |",
        f"| Questions with every figure right | {_fmt(s['all_correct_pct'], '%')}"
        f" ({s['all_correct_questions']} of {s['questions_asked']}) |",
        f"| Grounded (of answered) | {_fmt(s['grounded_pct'], '%')} |",
        f"| Answered / not found / errors | {s['answered']} / {s['not_found']} / {s['errors']} |",
        f"| Numbers not in the official answer | {s['unsupported_numbers']} |",
        f"| API latency p50 / avg / max | {_fmt(s['latency_ms']['p50'])} / "
        f"{_fmt(s['latency_ms']['avg'])} / {_fmt(s['latency_ms']['max'])} ms |",
        f"| Wall-clock p50 / avg / max | {_fmt(s['wall_ms']['p50'])} / "
        f"{_fmt(s['wall_ms']['avg'])} / {_fmt(s['wall_ms']['max'])} ms |",
        "| Citation correctness (manual) | "
        + (
            f"{cit['pct']}% ({cit['correct']} of {cit['checked']} citations)"
            if cit
            else "not checked yet: fill citation_check.csv, then --rescore"
        )
        + " |",
        "| Time saved (manual trials) | "
        + (f"{_fmt(ts['pct'], '%')} over {ts['trials']} questions" if ts else "no trials given")
        + " |",
        "| Automation (facts auto-accepted / all facts) | "
        + (
            f"{_fmt(auto['pct'], '%')} ({auto['auto_accepted']} of {auto['facts']})"
            if auto
            else "not counted (no --database-url)"
        )
        + " |",
        "",
    ]
    if s["error_kinds"]:
        kinds = ", ".join(f"{k}: {v}" for k, v in s["error_kinds"].items())
        lines += [f"Errors by kind: {kinds}.", ""]

    lines += [
        "## By topic",
        "",
        "| Topic | Questions | Figures found | Accuracy | All right |",
        "|---|---|---|---|---|",
    ]
    for topic, t in s["by_topic"].items():
        lines.append(
            f"| {topic} | {t['questions']} | {t['found']} / {t['expected']} | "
            f"{_fmt(t['numeric_accuracy_pct'], '%')} | {t['all_correct']} |"
        )

    lines += [
        "",
        "## By question",
        "",
        "| Id | Topic | Status | Found | Missed figures | Not in official answer | ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        missed = "; ".join(
            f"{c['value']} {c['unit']}"
            + (f" ({c['label']})" if c.get("label") else "")
            + (" [wrong unit]" if c["result"] == "wrong_unit" else "")
            for c in r["expected"]
            if c["result"] != "found"
        )
        status = r["status"] + (f": {r['error']}" if r["status"] == "error" else "")
        unsupported = ", ".join(r["unsupported_numbers"])
        lines.append(
            f"| {r['id']} | {r['topic']} | {_cell(status, 90)} | {r['found']} / "
            f"{r['expected_count']} | {_cell(missed, 2000)} | {_cell(unsupported, 300)}"
            f" | {_fmt(r.get('latency_ms'))} |"
        )
    lines += [
        "",
        "How each number is defined: see the docstring of `scripts/benchmark_runner.py`.",
        "",
    ]
    return "\n".join(lines)


def _cell(text: str, limit: int = 160) -> str:
    text = text.replace("|", "/").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- Talking to the API --------------------------------------------------------------------


class ApiSession:
    """Logged-in client for the Q&A API; logs in again once if the access token expires."""

    def __init__(self, client: httpx.Client, email: str, password: str) -> None:
        self.client, self.email, self.password = client, email, password
        self.token: str | None = None

    def login(self) -> None:
        res = self.client.post("/auth/login", json={"email": self.email, "password": self.password})
        if res.status_code != 200:
            raise SystemExit(f"Login as {self.email} failed: HTTP {res.status_code} {res.text}")
        self.token = res.json()["access_token"]

    def ask(self, question: str, timeout: float) -> dict:
        """One question -> record {ok, response, error, http_status, wall_ms}. Never raises
        for API problems: they are recorded so the run can go on. The per-question timeout is
        the client's (main() builds it with --timeout); `timeout` is for the message."""
        started = time.monotonic()
        record: dict[str, Any] = {"ok": False, "response": None, "error": None, "http_status": None}
        try:
            for attempt in range(2):
                res = self.client.post(
                    "/qa/ask",
                    json={"question": question},
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                if res.status_code == 401 and attempt == 0:
                    self.login()
                    continue
                break
            record["http_status"] = res.status_code
            if res.status_code == 200:
                record["ok"], record["response"] = True, res.json()
            else:
                kind = "model_unavailable" if res.status_code == 503 else f"http_{res.status_code}"
                record["error"] = f"{kind}: {_detail(res)}"
        except httpx.TimeoutException:
            record["error"] = f"timeout: no reply within {timeout} s"
        except httpx.HTTPError as e:
            record["error"] = f"connection: {e}"
        record["wall_ms"] = int((time.monotonic() - started) * 1000)
        return record


def _detail(res: httpx.Response) -> str:
    try:
        return str(res.json().get("detail"))[:300]
    except ValueError:
        return res.text[:300]


def result_row(entry: dict, record: dict) -> dict:
    """What results.json keeps per question: the entry's id/topic, the raw reply, the scoring."""
    response = record.get("response") or {}
    return {
        "id": entry["id"],
        "topic": entry["topic"],
        "question": entry["question"],
        "http_status": record.get("http_status"),
        "error": record.get("error"),
        "wall_ms": record.get("wall_ms"),
        "latency_ms": response.get("latency_ms"),
        "answer": response.get("answer"),
        "route": response.get("route"),
        "confidence": response.get("confidence"),
        "api_unmatched_numbers": response.get("unmatched_numbers"),
        "citations": response.get("citations") or [],
        "table": response.get("table"),
        "response": response or None,
        **score_question(entry, record),
    }


def rescore_row(entry: dict, row: dict) -> dict:
    """Score a saved row again (after a scoring change or with a newer benchmark)."""
    record = {
        "ok": row.get("error") is None and row.get("response") is not None,
        "response": row.get("response"),
        "error": row.get("error"),
        "http_status": row.get("http_status"),
        "wall_ms": row.get("wall_ms"),
    }
    return result_row(entry, record)


# --- Running -------------------------------------------------------------------------------


def select_entries(entries: list[dict], ids: list[str] | None, limit: int | None) -> list[dict]:
    if ids:
        known = {e["id"] for e in entries}
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise SystemExit(f"Unknown benchmark ids: {', '.join(unknown)}")
        entries = [e for e in entries if e["id"] in set(ids)]
    return entries[:limit] if limit else entries


def new_run_dir(base: Path, day: str) -> Path:
    """eval/results/<day>, or <day>-2, -3 ... when that day already has a run."""
    path, n = base / day, 1
    while path.exists():
        n += 1
        path = base / f"{day}-{n}"
    path.mkdir(parents=True)
    return path


def write_outputs(run_dir: Path, meta: dict, results: list[dict], sheet: bool = True) -> dict:
    """results.json, summary.json, report.md (+ a fresh citation_check.csv on a new run)."""
    summary = summarise(results)
    if sheet:
        write_citation_sheet(run_dir / "citation_check.csv", citation_rows(results))
    meta = {**meta, "citations": citation_correctness(run_dir / "citation_check.csv")}
    (run_dir / "results.json").write_text(
        json.dumps({"meta": meta, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text(
        json.dumps({**meta, **summary}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / "report.md").write_text(render_report(meta, summary, results), encoding="utf-8")
    return summary


def run(
    entries: list[dict],
    session: ApiSession,
    *,
    timeout: float,
    log=print,
) -> list[dict]:
    session.login()
    results = []
    for i, entry in enumerate(entries, 1):
        record = session.ask(entry["question"], timeout)
        row = result_row(entry, record)
        results.append(row)
        log(
            f"[{i}/{len(entries)}] {entry['id']}: {row['status']}"
            + (f" ({row['error']})" if row["error"] else "")
            + f", {row['found']}/{row['expected_count']} figures, {row['wall_ms']} ms"
        )
    return results


def load_benchmark(path: Path) -> list[dict]:
    entries, problems = check_benchmark.check_file(path)
    if problems:
        raise SystemExit(
            "Benchmark has problems (run scripts/check_benchmark.py):\n" + "\n".join(problems)
        )
    return entries


def demo_password() -> str | None:
    """SEED_DEMO_PASSWORD from the environment, else from backend/.env or the repo .env."""
    if os.environ.get("SEED_DEMO_PASSWORD"):
        return os.environ["SEED_DEMO_PASSWORD"]
    for env in (ROOT / "backend" / ".env", ROOT / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "SEED_DEMO_PASSWORD" and value.strip():
                    return value.strip().strip("'\"")
    return None


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the past-PQ benchmark against the Q&A API.")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--limit", type=int, help="ask only the first N questions")
    p.add_argument("--ids", help="comma-separated benchmark ids to ask")
    p.add_argument("--timeout", type=float, default=180, help="seconds per question")
    p.add_argument("--email", default=DEFAULT_EMAIL)
    p.add_argument("--password", help="default: SEED_DEMO_PASSWORD")
    p.add_argument("--benchmark", type=Path, default=check_benchmark.DEFAULT_PATH)
    p.add_argument("--out", type=Path, default=RESULTS_DIR, help="folder for dated results")
    p.add_argument("--database-url", help="count automation %% (facts) in this database")
    p.add_argument("--time-trials", type=Path, help="CSV: id, manual_seconds, assisted_seconds")
    p.add_argument(
        "--rescore",
        type=Path,
        metavar="RUN_DIR",
        help="re-score a saved run (and read its filled citation_check.csv) without asking again",
    )
    return p.parse_args(argv)


def _extras(args: argparse.Namespace, meta: dict) -> dict:
    if args.time_trials:
        meta["time_saved"] = time_saved(args.time_trials)
    if args.database_url:
        meta["automation"] = automation(args.database_url)
    return meta


def main(argv: list[str] | None = None, client: httpx.Client | None = None) -> Path:
    args = parse_args(argv)
    entries = load_benchmark(args.benchmark)

    if args.rescore:
        saved = json.loads((args.rescore / "results.json").read_text(encoding="utf-8"))
        by_id = {e["id"]: e for e in entries}
        results = [rescore_row(by_id[r["id"]], r) for r in saved["results"] if r["id"] in by_id]
        meta = _extras(args, {k: v for k, v in saved["meta"].items() if k != "citations"})
        meta["rescored_at"] = datetime.now().isoformat(timespec="seconds")
        summary = write_outputs(args.rescore, meta, results, sheet=False)
        accuracy = _fmt(summary["numeric_accuracy_pct"], "%")
        print(f"Re-scored {args.rescore}: numeric accuracy {accuracy}")
        return args.rescore

    ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else None
    chosen = select_entries(entries, ids, args.limit)
    password = args.password or demo_password()
    if not password:
        raise SystemExit("No password: pass --password or set SEED_DEMO_PASSWORD.")

    started = datetime.now()
    own_client = client is None
    client = client or httpx.Client(base_url=args.base_url, timeout=args.timeout)
    try:
        results = run(chosen, ApiSession(client, args.email, password), timeout=args.timeout)
    finally:
        if own_client:
            client.close()

    meta = _extras(
        args,
        {
            "run_date": started.date().isoformat(),
            "started_at": started.isoformat(timespec="seconds"),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "base_url": args.base_url,
            "benchmark_questions": len(entries),
            "timeout_s": args.timeout,
            "ids": [e["id"] for e in chosen],
        },
    )
    run_dir = new_run_dir(args.out, meta["run_date"])
    summary = write_outputs(run_dir, meta, results)
    print(
        f"Numeric accuracy {_fmt(summary['numeric_accuracy_pct'], '%')}, grounded "
        f"{_fmt(summary['grounded_pct'], '%')}, answered {summary['answered']}, not found "
        f"{summary['not_found']}, errors {summary['errors']}. Report: {run_dir / 'report.md'}"
    )
    return run_dir


if __name__ == "__main__":
    main()
