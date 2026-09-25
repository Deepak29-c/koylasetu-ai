"""Parliamentary Question reply builder (guide section 10.2).

pasted PQ -> split into parts (a), (b)… / (क), (ख)… / (i), (ii)… -> each part answered by the
Q&A service (guide section 9: text passages, and verified facts once the NUMERIC route is in)
-> one block per part {part, text, table, citations} -> tables with more than ~6 rows become
Annexures -> content_json for the report editor, plus a plain-text rendering for the plain
editor. `layout` turns a reply into lines and tables; the text, DOCX and PDF renderings all
come from it, so they always agree.

Core rule: numbers come only from the retrieved facts / passages. Every sentence that contains
a figure must cite a source, and the figure must be in the source it cites (the MP's question
does not count as a source, although it often states figures). Other sentences are dropped and
their figures listed on the block. A part with no source at all says "Information not found in
available documents" instead of guessing. Nothing here sends the draft anywhere: it is saved as
a DRAFT report for an Analyst to edit and an Approver to approve.

Limits inherited from the grounding check (services/grounding.py): numbers written as words
("ten") are not checked, units are not compared (12.16 MT passes against "12.16 lakh tonnes"),
and a small number can match part of a larger token ("24" in "2023-24").

Everything below except `draft_reply` is pure (no database, no model) so it can be unit-tested.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from app.llm import client
from app.models.enums import House, QuestionType
from app.services import grounding, qa

NOT_FOUND_PART = "Information not found in available documents."
NOT_FOUND_PART_HI = "उपलब्ध दस्तावेज़ों में जानकारी नहीं मिली।"
MINISTRY = "MINISTRY OF COAL"
MINISTER_LINE = "THE MINISTER OF COAL AND MINES (SHRI ____________________)"  # filled by hand
DEFAULT_INTRO = "Will the Minister of COAL be pleased to state:"
SOURCES_HEADING = "SOURCES (internal, remove before sending)"
ANSWER_HEADING = "ANSWER"
STATEMENT_HEADING = "STATEMENT"  # starred questions: the answers are laid as a Statement
ANNEXURE_PREFIX = "Annexure"  # Annexure-I, Annexure-II…
DRAFT_LINE = "DRAFT - for internal review. Not approved; not to be sent."
ANNEXURE_ROWS = 6  # tables with more rows than this go to an Annexure (guide 10.2)
MAX_PARTS = 10  # each part is one model call; a PQ rarely has more than (a)-(f)
HOUSE_LABEL = {House.LOK_SABHA: "LOK SABHA", House.RAJYA_SABHA: "RAJYA SABHA"}

_EN_LABELS = [chr(c) for c in range(ord("a"), ord("z") + 1)]
_HI_LABELS = [chr(c) for c in range(0x0915, 0x093A)]  # क ख ग घ ङ च … ह, in Unicode order
_ROMAN_LABELS = "i ii iii iv v vi vii viii ix x xi xii".split()
_HI_SKIPPABLE = {"ङ", "ञ"}  # some Hindi PQs go (घ) -> (च)
# "(a)" / "( ख )" / "(iii)" not glued to a word, or "a)" / "ii)" at the start or after a space.
_LABEL = r"[A-Za-z]{1,4}|[क-ह]"
_MARKER = re.compile(
    rf"(?<![\w)])\(\s*(?P<p>{_LABEL})\s*\)|(?:^|(?<=[\s;:,.]))(?P<b>{_LABEL})\)", re.M
)
# Parts that only make sense with the previous one: "(b) if so, the details thereof".
_DEPENDENT = re.compile(
    r"^\s*(?:if so|if not|if yes|if no|the details thereof|the reasons therefor|"
    r"यदि हाँ|यदि हां|यदि नहीं|तत्संबंधी|तत्सम्बन्धी)",
    re.IGNORECASE,
)
_WORD = re.compile(r"[0-9A-Za-zऀ-ॿ]+")
_LOCAL_REF = re.compile(r"\[\s*([CF]\d+)\s*\]")
_MARK = re.compile(r"\[S\d+\]")
# End of a sentence: . ! ? or danda, with any citation markers that follow it (they belong to
# the sentence before), then whitespace.
_SENTENCE_END = re.compile(r"[.!?।]+(?:\s*\[\s*[CF]\d+\s*\])*(?=\s|$)")
# Words that end with a dot but do not end a sentence (single letters as in "M.C.L." too).
_ABBREVIATIONS = {"no", "nos", "rs", "sh", "shri", "smt", "dr", "viz", "etc", "vs", "approx"}
_BULLET = re.compile(r"^\s*(?:[-•▪●*]|\d{1,2}[.)])\s+")
_ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


# --- 1. splitting the question ----------------------------------------------------------------


@dataclass
class Part:
    label: str  # "a", "b"…, "क", "ख"… or "i", "ii"…; "" when the question has no parts
    text: str


def _next_labels(labels: list[str], i: int) -> set[str]:
    """Labels accepted after position i-1 in the sequence (Hindi may skip ङ / ञ)."""
    if i >= len(labels):
        return set()
    accepted = {labels[i]}
    if labels[i] in _HI_SKIPPABLE and i + 1 < len(labels):
        accepted.add(labels[i + 1])
    return accepted


def _in_sequence(matches: list[re.Match], labels: list[str]) -> list[tuple[re.Match, str]]:
    accepted: list[tuple[re.Match, str]] = []
    pos = 0
    for m in matches:
        label = (m.group("p") or m.group("b")).lower()
        if label in _next_labels(labels, pos):
            accepted.append((m, label))
            pos = labels.index(label) + 1
    return accepted


def split_by_markers(question: str) -> tuple[str, list[Part]]:
    """Split on (a), (b)… / a), b)…, (क), (ख)… or (i), (ii)… that appear in order, starting
    from the first label. Markers out of sequence (an "(i)" inside part (b), a "(c)" quoted in
    the text) stay inside the part text; letters win over roman numerals, so "(a) … (i) … (ii)
    … (b)" is split on the letters only.

    Returns (intro, parts); parts is empty when the question has no usable markers."""
    matches = list(_MARKER.finditer(question))
    for labels in (_EN_LABELS, _HI_LABELS, _ROMAN_LABELS):
        accepted = _in_sequence(matches, labels)
        if accepted:
            break
    else:
        return question.strip(), []

    intro = question[: accepted[0][0].start()].strip()
    parts: list[Part] = []
    for i, (m, label) in enumerate(accepted):
        end = accepted[i + 1][0].start() if i + 1 < len(accepted) else len(question)
        text = " ".join(question[m.end() : end].split())
        if text:
            parts.append(Part(label, text))
    return intro, parts


SPLIT_SYSTEM = (
    "You split a Parliamentary Question into its separate parts. Copy the words of each part "
    "exactly from the question; do not add, answer or rephrase anything. Reply as JSON."
)
SPLIT_SCHEMA = {
    "type": "object",
    "properties": {
        "parts": {
            "type": "array",
            "items": {"type": "object", "properties": {"text": {"type": "string"}}},
        }
    },
    "required": ["parts"],
}


def _norm(text: str) -> str:
    return " ".join(text.split())


def split_with_llm(question: str, llm: Callable[..., str] = client.chat) -> list[Part]:
    """Fallback when there are no markers (guide 10.2). Each part must be copied word for word
    from the question, in order (the parts are printed as the MP's question, so a reworded or
    reordered part is not acceptable). Returns [] when the model is down, gives bad JSON, or any
    part fails that test, so the caller answers the whole question as one part."""
    try:
        raw = llm(SPLIT_SYSTEM, f"QUESTION:\n{question}", json_schema=SPLIT_SCHEMA)
        items = json.loads(raw).get("parts", [])
    except (client.LlmUnavailable, ValueError, AttributeError):
        return []
    texts = [_norm(str(it.get("text", ""))) for it in items if isinstance(it, dict)]
    texts = [t for t in texts if t]
    source, pos = _norm(question), 0
    for t in texts:
        found = source.find(t, pos)
        if found < 0:
            return []
        pos = found + len(t)
    if len(texts) < 2:
        return []
    labels = _HI_LABELS if qa.is_hindi(question) else _EN_LABELS
    return [Part(labels[i], t) for i, t in enumerate(texts)]


def split_question(
    question: str, llm: Callable[..., str] = client.chat
) -> tuple[str, list[Part], str]:
    """Returns (intro, parts, method) with method "markers", "llm" or "single"."""
    intro, parts = split_by_markers(question)
    if parts:
        return intro, parts, "markers"
    parts = split_with_llm(question, llm)
    if parts:
        return "", parts, "llm"
    return "", [Part("", _norm(question))], "single"


def part_query(subject: str | None, parts: list[Part], i: int) -> str:
    """The question sent to Q&A for part i. "(b) if so, the details thereof" means nothing on
    its own, so short or dependent parts carry the previous part; the subject adds context."""
    text = parts[i].text
    if i > 0 and (_DEPENDENT.match(text) or len(_WORD.findall(text)) < 6):
        text = f"{parts[i - 1].text} {text}"
    return f"{subject.strip()}: {text}" if subject and subject.strip() else text


# --- 2. keeping only sourced figures ------------------------------------------------------------


def _ends_sentence(text: str, dot_at: int) -> bool:
    """False for "M.C.L." / "No." / "Rs." style dots and when the next word is lower case."""
    if text[dot_at] != ".":
        return True
    word = re.search(r"([A-Za-z]+)$", text[:dot_at])
    if word and (len(word.group(1)) == 1 or word.group(1).lower() in _ABBREVIATIONS):
        return False
    rest = text[dot_at + 1 :].lstrip()
    rest = _LOCAL_REF.sub("", rest).lstrip() if rest.startswith("[") else rest
    return not (rest[:1].islower())


def sentences(line: str) -> list[str]:
    """Split one line into sentences; citation markers stay with the sentence they follow."""
    out, start = [], 0
    for m in _SENTENCE_END.finditer(line):
        if _ends_sentence(line, m.start()):
            out.append(line[start : m.end()].strip())
            start = m.end()
    out.append(line[start:].strip())
    return [s for s in out if s]


def split_lines(text: str) -> list[str]:
    """Lines of an answer; inline bullets ("… • NCL 12.7 • MCL 15.1") become lines too."""
    text = re.sub(r"\s+([•▪●])\s+", r"\n\1 ", text)
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def source_text(item: object) -> str:
    """The text a figure is checked against: a passage's text, or a fact's DATA line."""
    if getattr(item, "fact_id", None) is None:
        return getattr(item, "text", "")
    fact_line = getattr(qa, "fact_line", None)  # comes with the NUMERIC route
    if fact_line is not None:
        try:
            return fact_line(item)
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
    fields = ("who", "metric", "period_text", "period", "value_raw", "value_std", "value")
    return " ".join(str(getattr(item, f, "")) for f in fields)


def keep_sourced(text: str, local: dict[str, object]) -> tuple[str, list[str]]:
    """Drop every sentence that has a figure but no valid citation, or a figure that is not in
    the sources it cites. The question is not a source. Bullet lines without their own citation
    use the citations of their list. Returns (kept text, removed figures as written)."""
    lines = split_lines(text)
    list_refs: dict[int, list[str]] = {}
    run: list[int] = []
    for i, ln in enumerate(lines + [""]):
        if i < len(lines) and _BULLET.match(ln):
            run.append(i)
            continue
        refs = [r for j in run for r in _LOCAL_REF.findall(lines[j]) if r in local]
        list_refs |= {j: refs for j in run}
        run = []

    kept_lines, removed = [], []
    for i, ln in enumerate(lines):
        kept = []
        for s in sentences(ln):
            values = grounding.extract_values(s)
            if not values:
                kept.append(s)
                continue
            refs = [r for r in _LOCAL_REF.findall(s) if r in local] or list_refs.get(i, [])
            if not refs:
                removed += [v.token for v in values]
                continue
            bad = grounding.check(s, [source_text(local[r]) for r in dict.fromkeys(refs)])
            if bad:
                removed += bad
            else:
                kept.append(s)
        if kept:
            kept_lines.append(" ".join(kept))
    return "\n".join(kept_lines), removed


# --- 3. turning Q&A answers into blocks --------------------------------------------------------


@dataclass
class Source:
    """One document location a figure or sentence came from."""

    kind: str  # "fact" | "chunk"
    source_id: str  # fact_id or chunk_id
    document_id: str
    document: str
    page: int
    bbox: list[float] | None = None


def source_of(item: object) -> Source:
    """A Q&A citation (retrieval.Passage, or facts_query.FactRow on the NUMERIC route)."""
    fact_id = getattr(item, "fact_id", None)
    kind, sid = ("fact", fact_id) if fact_id is not None else ("chunk", item.chunk_id)
    return Source(
        kind=kind,
        source_id=str(sid),
        document_id=str(item.document_id),
        document=item.document_title,
        page=item.page_no,
        bbox=getattr(item, "bbox", None),
    )


@dataclass
class SourceRegistry:
    """Numbers sources S1, S2… across the whole reply, one number per fact / chunk."""

    sources: list[dict] = field(default_factory=list)
    _index: dict[tuple[str, str], str] = field(default_factory=dict)

    def add(self, s: Source, part: str) -> str:
        key = (s.kind, s.source_id)
        if key not in self._index:
            sid = f"S{len(self.sources) + 1}"
            self._index[key] = sid
            self.sources.append(
                {
                    "id": sid,
                    "kind": s.kind,
                    "fact_id": s.source_id if s.kind == "fact" else None,
                    "chunk_id": s.source_id if s.kind == "chunk" else None,
                    "document_id": s.document_id,
                    "document": s.document,
                    "page": s.page,
                    "bbox": s.bbox,
                    "parts": [],
                }
            )
        sid = self._index[key]
        entry = self.sources[int(sid[1:]) - 1]
        if part not in entry["parts"]:
            entry["parts"].append(part)
        return sid


def roman(n: int) -> str:
    out = ""
    for value, numeral in _ROMAN:
        while n >= value:
            out += numeral
            n -= value
    return out


def build_block(
    part: Part,
    answer: object,
    registry: SourceRegistry,
    *,
    annexure_no: int,
    hindi: bool = False,
) -> dict:
    """One reply block from one Q&A answer. `annexure_no` is the number the next Annexure
    would get; the block records its Annexure label if its table needs one.

    `answer` is a qa.Answer. `passages`, `table` and `facts` are read with getattr so this
    works with and without the NUMERIC route."""
    label = part.label or "reply"
    block_id = f"part-{label}"
    not_found_text = NOT_FOUND_PART_HI if hindi else NOT_FOUND_PART
    local: dict[str, object] = {}
    for key in ("citations", "passages", "facts"):
        for item in getattr(answer, key, None) or []:
            local.setdefault(item.ref, item)

    text = answer.answer.strip()
    note = None
    no_facts_note = getattr(qa, "NO_FACTS_NOTE", None)
    if no_facts_note and text.startswith(no_facts_note):
        text = text[len(no_facts_note) :].strip()
        note = no_facts_note.rstrip(": ").strip() + "."
    text, removed = keep_sourced(text, local)

    table = getattr(answer, "table", None)
    table_refs = {c for row in (table or {}).get("rows", []) for c in row if c in local}
    cited = [r for r in dict.fromkeys(_LOCAL_REF.findall(text)) if r in local]

    if answer.not_found or not (cited or table_refs):
        return {
            "id": block_id,
            "part": part.label,
            "question": part.text,
            "text": not_found_text,
            "table": None,
            "annexure": None,
            "citations": [],
            "not_found": True,
            "removed_numbers": removed,
            "note": note,
        }

    mapping = {r: registry.add(source_of(local[r]), part.label) for r in cited}
    mapping |= {r: registry.add(source_of(local[r]), part.label) for r in sorted(table_refs)}

    def renumber(m: re.Match) -> str:
        return f"[{mapping[m.group(1)]}]" if m.group(1) in mapping else ""

    text = _LOCAL_REF.sub(renumber, text)
    text = re.sub(r"[ \t]+([.,;।])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()

    annexure = None
    if table:
        table = {
            "columns": list(table.get("columns", [])),
            "rows": [[mapping.get(c, c) for c in row] for row in table.get("rows", [])],
        }
        if len(table["rows"]) > ANNEXURE_ROWS:
            annexure = f"{ANNEXURE_PREFIX}-{roman(annexure_no)}"
            text = re.sub(r"in the table below", f"in {annexure}", text, flags=re.I)
            if annexure not in text:
                text = f"{text} Details are given in {annexure}.".strip()

    return {
        "id": block_id,
        "part": part.label,
        "question": part.text,
        "text": text,
        "table": table,
        "annexure": annexure,
        "citations": list(dict.fromkeys(mapping.values())),
        "not_found": False,
        "removed_numbers": removed,
        "note": note,
    }


def citation_links(blocks: list[dict], sources: list[dict]) -> list[dict]:
    """One report_citations row per (block, source): which fact / chunk backs which part. The
    location ends with the reply-wide source number (":S3"), so the sources list can be rebuilt
    in the same order from these rows."""
    by_id = {s["id"]: s for s in sources}
    links = []
    for b in blocks:
        for sid in b["citations"]:
            s = by_id[sid]
            where = f"{b['annexure']}:{sid}" if b.get("annexure") else f"{b['id']}:{sid}"
            links.append(
                {
                    "fact_id": uuid.UUID(s["fact_id"]) if s["fact_id"] else None,
                    "chunk_id": uuid.UUID(s["chunk_id"]) if s["chunk_id"] else None,
                    "location_in_report": where,
                }
            )
    return links


def sources_from_links(rows: list[tuple[str, object, str, int]]) -> list[dict]:
    """Rebuild the sources list from report_citations rows (location_in_report, source id,
    document title, page), numbered as in the reply: by the ":S3" in the location. Rows
    without a number (written some other way) come after, numbered on."""
    numbered: dict[int, dict] = {}
    extra: list[dict] = []
    seen: set = set()
    keyed = []
    for where, key, title, page in rows:
        m = re.search(r":S(\d+)$", where or "")
        keyed.append((int(m.group(1)) if m else None, key, title, page))
    keyed.sort(key=lambda r: (r[0] is None, r[0] or 0))
    for n, key, title, page in keyed:
        if key in seen:
            continue
        seen.add(key)
        if n is not None:
            # Monthly reports / briefing notes number sources by document page, so several
            # facts can share one number: list it once.
            numbered.setdefault(n, {"id": f"S{n}", "document": title, "page": page})
        else:
            extra.append({"document": title, "page": page})
    top = max(numbered, default=0)
    for i, s in enumerate(extra, start=top + 1):
        s["id"] = f"S{i}"
    return [numbered[n] for n in sorted(numbered)] + extra


# --- 4. header and layout ----------------------------------------------------------------------


def format_date(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "__.__.____"


def build_header(
    *,
    house: House,
    q_type: QuestionType,
    q_no: str | None,
    answer_date: date | None,
    mp_name: str | None,
    subject: str | None,
    intro: str,
) -> dict:
    return {
        "ministry": MINISTRY,
        "house": house.value,
        "house_label": HOUSE_LABEL[house],
        "q_type": q_type.value,
        "q_no": q_no or "",
        "answer_date": answer_date.isoformat() if answer_date else None,
        "answer_date_text": format_date(answer_date),
        "mp_name": mp_name or "",
        "subject": subject or "",
        "intro": intro or DEFAULT_INTRO,
        "minister_line": MINISTER_LINE,
    }


def question_heading(header: dict) -> str:
    kind = "STARRED" if header["q_type"] == QuestionType.STARRED.value else "UNSTARRED"
    return f"{kind} QUESTION NO. {header['q_no'] or '____'}"


def header_lines(header: dict) -> list[str]:
    return [
        "GOVERNMENT OF INDIA",
        header["ministry"],
        header["house_label"],
        question_heading(header),
        f"TO BE ANSWERED ON {header['answer_date_text']}",
    ]


def asker_line(header: dict) -> str:
    return f"{header['q_no'] or '____'}. {header['mp_name'].upper() or 'SHRI/SMT. ____'}:"


def _question_ref(header: dict) -> str:
    house = header["house_label"].title()
    kind = header["q_type"].title()
    return f"{house} {kind} Question No. {header['q_no'] or '____'}"


def annexure_caption(header: dict, part: str) -> str:
    of_part = f"part ({part}) of " if part else ""
    return (
        f"Referred to in reply to {of_part}{_question_ref(header)} "
        f"for answer on {header['answer_date_text']}"
    )


def statement(header: dict, blocks: list[dict]) -> tuple[str, str] | None:
    """Starred questions are answered "(a) to (c): A Statement is laid on the Table of the
    House." followed by the Statement. Returns (lead line, Statement caption) or None."""
    if header["q_type"] != QuestionType.STARRED.value or not blocks:
        return None
    first, last = blocks[0]["part"], blocks[-1]["part"]
    if not first:
        parts, of_parts = "", ""
    elif first == last:
        parts, of_parts = f"({first}): ", f"part ({first}) of "
    else:
        parts, of_parts = f"({first}) to ({last}): ", f"parts ({first}) to ({last}) of "
    asked = f" asked by {header['mp_name']}" if header["mp_name"] else ""
    caption = (
        f"Statement referred to in reply to {of_parts}{_question_ref(header)} "
        f"for answer on {header['answer_date_text']}{asked}"
    )
    return f"{parts}A Statement is laid on the Table of the House.", caption


def part_prefix(label: str) -> str:
    return f"({label}) " if label else ""


def removed_note(figures: list[str]) -> str:
    return f"[figure(s) removed as unsupported: {', '.join(dict.fromkeys(figures))}]"


# Layout items: ("line", text, style) | ("table", table) | ("pagebreak",)
# Styles: title (centred bold), bold, normal, caption (centred small), note (red small, drafts
# only), small (sources list).


def layout(
    header: dict,
    blocks: list[dict],
    sources: list[dict],
    *,
    internal_notes: bool,
    warnings: list[str] | tuple[str, ...] = (),
) -> list[tuple]:
    """The official PQ-reply layout (guide 10.1). `internal_notes` adds the DRAFT line,
    warnings and removed-figure notes (unapproved exports only; never in the editor text)."""
    items: list[tuple] = []

    def line(text: str = "", style: str = "normal") -> None:
        items.append(("line", text, style))

    if internal_notes:
        line(DRAFT_LINE, "note")
        for w in warnings:
            line(w, "note")
    for h in header_lines(header):
        line(h, "title")
    line()
    line(header["subject"].upper(), "title")
    line()
    line(asker_line(header), "bold")
    line(header["intro"])
    for b in blocks:
        line(f"{part_prefix(b['part'])}{b['question']}")
    line()
    line(ANSWER_HEADING, "title")
    line(header["minister_line"], "title")
    line()
    st = statement(header, blocks)
    if st:
        line(st[0])
        line()
        line(STATEMENT_HEADING, "title")
        line(st[1], "caption")
        line()
    for b in blocks:
        line(f"({b['part']}): {b['text']}" if b["part"] else b["text"])
        if internal_notes and b.get("removed_numbers"):
            line(removed_note(b["removed_numbers"]), "note")
        if internal_notes and b.get("note"):
            line(b["note"], "note")
        if b.get("table") and not b.get("annexure"):
            items.append(("table", b["table"]))
        line()
    for b in blocks:
        if b.get("annexure"):
            items.append(("pagebreak",))
            line(b["annexure"].upper(), "title")
            line(annexure_caption(header, b["part"]), "caption")
            items.append(("table", b["table"]))
    if sources:
        line()
        line(SOURCES_HEADING, "bold")
        for s in sources:
            line(f"[{s['id']}] {s['document']}, page {s['page']}", "small")
    return items


def table_lines(table: dict) -> list[str]:
    return [" | ".join(map(str, table["columns"]))] + [
        " | ".join(map(str, r)) for r in table["rows"]
    ]


def items_to_text(items: list[tuple]) -> str:
    lines: list[str] = []
    for item in items:
        if item[0] == "line":
            lines.append(item[1])
        elif item[0] == "table":
            lines += table_lines(item[1]) + [""]
        else:
            lines.append("")
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return text.strip() + "\n"


def render_text(header: dict, blocks: list[dict], sources: list[dict]) -> str:
    """Plain rendering of the whole reply, for the plain-text report editor."""
    return items_to_text(layout(header, blocks, sources, internal_notes=False))


# --- 5. the whole draft ------------------------------------------------------------------------


@dataclass
class Draft:
    intro: str
    parts: list[Part]  # every part of the question, including any beyond MAX_PARTS
    split_method: str
    content: dict  # content_json of the report
    links: list[dict]  # report_citations rows


def too_many_parts_warning(total: int) -> str:
    return (
        f"The question has {total} parts; only the first {MAX_PARTS} were answered. "
        "Answer the remaining parts by hand."
    )


def build_content(
    header: dict,
    parts: list[Part],
    answers: list[object],
    hindi: bool,
    warnings: list[str] | None = None,
) -> Draft:
    """Pure: parts + their Q&A answers -> content_json and citation links."""
    registry = SourceRegistry()
    blocks: list[dict] = []
    annexures = 0
    for part, answer in zip(parts, answers, strict=True):
        block = build_block(part, answer, registry, annexure_no=annexures + 1, hindi=hindi)
        annexures += 1 if block["annexure"] else 0
        blocks.append(block)
    sources = registry.sources
    content = {
        "kind": "pq_reply",
        "header": header,
        "blocks": blocks,
        "sources": sources,
        "warnings": list(warnings or []),
        "text": render_text(header, blocks, sources),
    }
    return Draft(header["intro"], parts, "", content, citation_links(blocks, sources))


def draft_reply(
    db,
    user,
    *,
    house: House,
    q_type: QuestionType,
    q_no: str | None,
    answer_date: date | None,
    mp_name: str | None,
    subject: str | None,
    question_text: str,
    ask: Callable[..., object] | None = None,
    llm: Callable[..., str] | None = None,
    check_model: Callable[[], None] | None = None,
) -> Draft:
    """Split the PQ and answer every part through the Q&A service's public entry point, so the
    same retrieval, routing and grounding rules apply as on the Ask screen. Raises
    client.LlmUnavailable up front if the model server or model is not there, rather than
    saving a draft in which every part says "not found"."""
    (check_model or client.ensure_available)()
    ask = ask or qa.ask
    intro, parts, method = split_question(question_text, llm or client.chat)
    answered = parts[:MAX_PARTS]
    warnings = [too_many_parts_warning(len(parts))] if len(parts) > MAX_PARTS else []
    answers = [ask(db, user, part_query(subject, parts, i)) for i in range(len(answered))]
    header = build_header(
        house=house,
        q_type=q_type,
        q_no=q_no,
        answer_date=answer_date,
        mp_name=mp_name,
        subject=subject,
        intro=intro,
    )
    draft = build_content(header, answered, answers, qa.is_hindi(question_text), warnings)
    draft.parts = parts
    draft.split_method = method
    return draft
