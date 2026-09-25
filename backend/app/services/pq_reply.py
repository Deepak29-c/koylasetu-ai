"""Parliamentary Question reply builder (guide section 10.2).

pasted PQ -> split into parts (a), (b)… / (क), (ख)… -> each part answered by the Q&A service
(guide section 9: text passages, and verified facts once the NUMERIC route is in) -> one block
per part {part, text, table, citations} -> tables with more than ~6 rows become Annexures ->
content_json for the report editor, plus a plain-text rendering for the plain editor.

Core rule: numbers come only from the retrieved facts / passages. A sentence with a figure the
grounding check cannot find in the sources is dropped, and a part with no source at all says
"Information not found in available documents" instead of guessing. Nothing here sends the
draft anywhere: it is saved as a DRAFT report for an Analyst to edit and an Approver to approve.

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
from app.services import qa

NOT_FOUND_PART = "Information not found in available documents."
NOT_FOUND_PART_HI = "उपलब्ध दस्तावेज़ों में जानकारी नहीं मिली।"
MINISTRY = "MINISTRY OF COAL"
MINISTER_LINE = "THE MINISTER OF COAL AND MINES (SHRI ____________________)"  # filled by hand
DEFAULT_INTRO = "Will the Minister of COAL be pleased to state:"
ANNEXURE_ROWS = 6  # tables with more rows than this go to an Annexure (guide 10.2)
MAX_PARTS = 10  # each part is one model call; a PQ rarely has more than (a)-(f)
HOUSE_LABEL = {House.LOK_SABHA: "LOK SABHA", House.RAJYA_SABHA: "RAJYA SABHA"}

_EN_LABELS = [chr(c) for c in range(ord("a"), ord("z") + 1)]
_HI_LABELS = [chr(c) for c in range(0x0915, 0x093A)]  # क ख ग घ ङ च … ह, in Unicode order
_HI_SKIPPABLE = {"ङ", "ञ"}  # some Hindi PQs go (घ) -> (च)
# "(a)" / "( ख )" at the start of the text, a line, or after whitespace / punctuation.
_MARKER = re.compile(r"(?<![\w)])\(\s*([A-Za-z]|[क-ह])\s*\)")
# Parts that only make sense with the previous one: "(b) if so, the details thereof".
_DEPENDENT = re.compile(
    r"^\s*(?:if so|if not|if yes|if no|the details thereof|the reasons therefor|"
    r"यदि हाँ|यदि हां|यदि नहीं|तत्संबंधी|तत्सम्बन्धी)",
    re.IGNORECASE,
)
_WORD = re.compile(r"[0-9A-Za-zऀ-ॿ]+")
_LOCAL_REF = re.compile(r"\[\s*([CF]\d+)\s*\]")
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")
_ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


# --- 1. splitting the question ----------------------------------------------------------------


@dataclass
class Part:
    label: str  # "a", "b"… or "क", "ख"…; "" when the question has no parts
    text: str


def _next_labels(labels: list[str], i: int) -> set[str]:
    """Labels accepted after position i-1 in the sequence (Hindi may skip ङ / ञ)."""
    if i >= len(labels):
        return set()
    accepted = {labels[i]}
    if labels[i] in _HI_SKIPPABLE and i + 1 < len(labels):
        accepted.add(labels[i + 1])
    return accepted


def split_by_markers(question: str) -> tuple[str, list[Part]]:
    """Split on (a), (b)… or (क), (ख)… that appear in order. Markers out of sequence (a "(i)"
    inside part (b), a "(c)" quoted in the text) are left inside the part text.

    Returns (intro, parts); parts is empty when the question has no usable markers."""
    matches = list(_MARKER.finditer(question))
    for labels in (_EN_LABELS, _HI_LABELS):
        accepted: list[re.Match] = []
        pos = 0
        for m in matches:
            label = m.group(1).lower()
            if label in _next_labels(labels, pos):
                accepted.append(m)
                pos = labels.index(label) + 1
        if accepted and accepted[0].group(1).lower() == labels[0]:
            break
    else:
        return question.strip(), []

    intro = question[: accepted[0].start()].strip()
    parts: list[Part] = []
    for i, m in enumerate(accepted):
        end = accepted[i + 1].start() if i + 1 < len(accepted) else len(question)
        text = " ".join(question[m.end() : end].split())
        if text:
            parts.append(Part(m.group(1).lower(), text))
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


def _mostly_from(text: str, source: str, share: float = 0.8) -> bool:
    """True if at least `share` of the words in `text` occur in `source` (guards against the
    model inventing a part)."""
    words = [w.lower() for w in _WORD.findall(text)]
    known = {w.lower() for w in _WORD.findall(source)}
    return bool(words) and sum(w in known for w in words) / len(words) >= share


def split_with_llm(question: str, llm: Callable[..., str] = client.chat) -> list[Part]:
    """Fallback when there are no markers (guide 10.2). Returns [] when the model is down, gives
    bad JSON, or returns fewer than two parts that are copied from the question."""
    try:
        raw = llm(SPLIT_SYSTEM, f"QUESTION:\n{question}", json_schema=SPLIT_SCHEMA)
        items = json.loads(raw).get("parts", [])
    except (client.LlmUnavailable, ValueError, AttributeError):
        return []
    texts = [" ".join(str(it.get("text", "")).split()) for it in items if isinstance(it, dict)]
    texts = [t for t in texts if t and _mostly_from(t, question)]
    if len(texts) < 2:
        return []
    labels = _HI_LABELS if qa.is_hindi(question) else _EN_LABELS
    return [Part(labels[i], t) for i, t in enumerate(texts[:MAX_PARTS])]


def split_question(
    question: str, llm: Callable[..., str] = client.chat
) -> tuple[str, list[Part], str]:
    """Returns (intro, parts, method) with method "markers", "llm" or "single"."""
    intro, parts = split_by_markers(question)
    if parts:
        return intro, parts[:MAX_PARTS], "markers"
    parts = split_with_llm(question, llm)
    if parts:
        return "", parts, "llm"
    return "", [Part("", " ".join(question.split()))], "single"


def part_query(subject: str | None, parts: list[Part], i: int) -> str:
    """The question sent to Q&A for part i. "(b) if so, the details thereof" means nothing on
    its own, so short or dependent parts carry the previous part; the subject adds context."""
    text = parts[i].text
    if i > 0 and (_DEPENDENT.match(text) or len(_WORD.findall(text)) < 6):
        text = f"{parts[i - 1].text} {text}"
    return f"{subject.strip()}: {text}" if subject and subject.strip() else text


# --- 2. turning Q&A answers into blocks --------------------------------------------------------


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


def drop_unsupported(text: str, unmatched: list[str]) -> tuple[str, list[str]]:
    """Remove sentences that contain a figure the grounding check could not find in the
    sources. Returns (kept text, removed figures)."""
    if not unmatched:
        return text, []
    kept, removed = [], []
    for sentence in _SENTENCE.split(text):
        hits = [
            u for u in unmatched if u and re.search(rf"(?<![\d.,]){re.escape(u)}(?!\d)", sentence)
        ]
        if hits:
            removed.extend(hits)
        else:
            kept.append(sentence)
    return " ".join(kept).strip(), removed


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

    `answer` is a qa.Answer. `table` and `facts` come with the NUMERIC route and are read with
    getattr so this works with and without it."""
    label = part.label or "reply"
    block_id = f"part-{label}"
    not_found_text = NOT_FOUND_PART_HI if hindi else NOT_FOUND_PART
    local: dict[str, object] = {}
    for item in list(getattr(answer, "citations", [])) + list(getattr(answer, "facts", [])):
        local.setdefault(item.ref, item)

    text = answer.answer.strip()
    note = None
    no_facts_note = getattr(qa, "NO_FACTS_NOTE", None)
    if no_facts_note and text.startswith(no_facts_note):
        text = text[len(no_facts_note) :].strip()
        note = no_facts_note.rstrip(": ").strip() + "."
    text, removed = drop_unsupported(text, list(getattr(answer, "unmatched_numbers", [])))

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
    text = re.sub(r"\s+([.,;])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()

    annexure = None
    if table:
        table = {
            "columns": list(table.get("columns", [])),
            "rows": [[mapping.get(c, c) for c in row] for row in table.get("rows", [])],
        }
        if len(table["rows"]) > ANNEXURE_ROWS:
            annexure = f"Annexure-{roman(annexure_no)}"
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
    """One report_citations row per (block, source): which fact / chunk backs which part."""
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


# --- 3. header and plain-text rendering -------------------------------------------------------


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


def annexure_caption(header: dict, part: str) -> str:
    house = header["house_label"].title()
    kind = header["q_type"].title()
    of_part = f"part ({part}) of " if part else ""
    return (
        f"Referred to in reply to {of_part}{house} {kind} Question No. {header['q_no'] or '____'} "
        f"for answer on {header['answer_date_text']}"
    )


def part_prefix(label: str) -> str:
    return f"({label}) " if label else ""


def table_lines(table: dict) -> list[str]:
    return [" | ".join(table["columns"])] + [" | ".join(r) for r in table["rows"]]


def render_text(header: dict, blocks: list[dict], sources: list[dict]) -> str:
    """Plain rendering of the whole reply, for the plain-text report editor."""
    lines = [
        "GOVERNMENT OF INDIA",
        header["ministry"],
        header["house_label"],
        question_heading(header),
        f"TO BE ANSWERED ON {header['answer_date_text']}",
        "",
        header["subject"].upper(),
        "",
        f"{header['q_no'] or '____'}. {header['mp_name'].upper() or 'SHRI/SMT. ____'}:",
        header["intro"],
    ]
    lines += [f"{part_prefix(b['part'])}{b['question']}" for b in blocks]
    lines += ["", "ANSWER", header["minister_line"], ""]
    for b in blocks:
        prefix = f"({b['part']}): " if b["part"] else ""
        lines.append(f"{prefix}{b['text']}")
        if b["table"] and not b["annexure"]:
            lines += table_lines(b["table"])
        lines.append("")
    for b in blocks:
        if b["annexure"]:
            lines += [b["annexure"].upper(), annexure_caption(header, b["part"])]
            lines += table_lines(b["table"]) + [""]
    if sources:
        lines.append("SOURCES (internal, remove before sending)")
        lines += [f"[{s['id']}] {s['document']}, page {s['page']}" for s in sources]
    return "\n".join(lines).strip() + "\n"


# --- 4. the whole draft ------------------------------------------------------------------------


@dataclass
class Draft:
    intro: str
    parts: list[Part]
    split_method: str
    content: dict  # content_json of the report
    links: list[dict]  # report_citations rows


def build_content(header: dict, parts: list[Part], answers: list[object], hindi: bool) -> Draft:
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
) -> Draft:
    """Split the PQ and answer every part through the Q&A service's public entry point, so the
    same retrieval, routing and grounding rules apply as on the Ask screen. Raises
    client.LlmUnavailable if the model server is down."""
    ask = ask or qa.ask
    intro, parts, method = split_question(question_text, llm or client.chat)
    answers = [ask(db, user, part_query(subject, parts, i)) for i in range(len(parts))]
    header = build_header(
        house=house,
        q_type=q_type,
        q_no=q_no,
        answer_date=answer_date,
        mp_name=mp_name,
        subject=subject,
        intro=intro,
    )
    draft = build_content(header, parts, answers, qa.is_hindi(question_text))
    draft.split_method = method
    return draft
