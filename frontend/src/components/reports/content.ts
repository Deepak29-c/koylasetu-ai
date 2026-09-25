import type { ChipSource } from "@/components/Citation";
import type { DraftSection, PqBlock, ReportContent, ReportRow, ReportVersionRow } from "@/lib/api";
import { versionLine } from "@/lib/reportView";

/**
 * Reading and rebuilding a report's content_json for the editor. The server stores what it
 * is sent, so every save goes through mergeContent: the original object with only the
 * edited text swapped in, and `text` rendered again from the result.
 */

export type EditMode = "blocks" | "sections" | "text";

type Table = { columns: string[]; rows: string[][] };

export function editMode(c: ReportContent): EditMode {
  if (Array.isArray(c.blocks) && c.blocks.length > 0) return "blocks";
  if (Array.isArray(c.sections) && c.sections.length > 0) return "sections";
  return "text";
}

/** One editable string per block / section, or the whole text for a plain report. */
export function originalEdits(c: ReportContent, mode: EditMode): string[] {
  if (mode === "blocks") return (c.blocks ?? []).map((b) => b.text ?? "");
  if (mode === "sections") return (c.sections ?? []).map((s) => (s.lines ?? []).join("\n"));
  return [c.text ?? ""];
}

/** A section with no lines of its own (a table, say) has nothing to type into. */
export function sectionHasText(s: DraftSection | null | undefined): boolean {
  return (s?.lines ?? []).length > 0;
}

/**
 * The content as the generator made it: the lowest version, before anyone edited it. Falls back
 * to the current content while the versions are not loaded or have another shape.
 */
export function generatedContent(current: ReportContent, versions: ReportVersionRow[]): ReportContent {
  const first = versions.reduce<ReportVersionRow | null>((a, v) => (!a || v.version < a.version ? v : a), null);
  const c = first?.content_json;
  if (!c || editMode(c) !== editMode(current)) return current;
  return c;
}

/** The report's sources as chips, whichever generator made them. */
export function chipSources(c: ReportContent): Map<string, ChipSource> {
  const out = new Map<string, ChipSource>();
  if (!Array.isArray(c.sources)) return out;
  for (const raw of c.sources as Record<string, unknown>[]) {
    if (!raw || typeof raw.id !== "string" || typeof raw.document_id !== "string") continue;
    out.set(raw.id, {
      id: raw.id,
      document: String(raw.document ?? ""),
      document_id: raw.document_id,
      page: Number(raw.page ?? 1),
      chunk_id: typeof raw.chunk_id === "string" ? raw.chunk_id : null,
      bbox: Array.isArray(raw.bbox) ? (raw.bbox as number[]) : null,
    });
  }
  return out;
}

// --- numbers typed by hand ----------------------------------------------------------------------

const MARKER = /\[\s*[A-Z]\d+\s*\]/g;
/** A figure: digits with optional thousands separators and decimals (ASCII or Devanagari). */
export const NUMBER = /[0-9०-९]+(?:[,.][0-9०-९]+)*/g;

/** One spelling per figure: Devanagari digits to ASCII, thousands separators dropped. */
export function normaliseNumber(n: string): string {
  return n.replace(/[०-९]/g, (d) => String(d.charCodeAt(0) - 0x0966)).replace(/,/g, "");
}

export function numbersIn(text: string): string[] {
  return (text.replace(MARKER, " ").match(NUMBER) ?? []).map(normaliseNumber);
}

function tableNumbers(table: Table | null | undefined): string[] {
  if (!table) return [];
  return [...table.columns, ...table.rows.flat()].flatMap((cell) => numbersIn(String(cell)));
}

/** Figures the generator put in this block / section, from its text and its table. */
export function knownNumbers(c: ReportContent, mode: EditMode, index: number): Set<string> {
  if (mode === "blocks") {
    const b = c.blocks?.[index];
    return new Set(b ? [...numbersIn(b.text ?? ""), ...tableNumbers(b.table)] : []);
  }
  if (mode === "sections") {
    const s = c.sections?.[index];
    return new Set(s ? [...numbersIn((s.lines ?? []).join("\n")), ...tableNumbers(s.table), ...(s.notes ?? []).flatMap(numbersIn)] : []);
  }
  return new Set(numbersIn(c.text ?? ""));
}

/** Figures in the edited text that the original did not have: nothing links them to a source. */
export function unlinkedNumbers(edited: string, known: Set<string>): string[] {
  return [...new Set(numbersIn(edited).filter((n) => !known.has(n)))];
}

// --- merging edits back ----------------------------------------------------------------------------

function sectionLines(edited: string, bullets: boolean): string[] {
  return edited
    .split("\n")
    .map((l) => (bullets ? l.replace(/^\s*[•*-]\s+/, "") : l).trim())
    .filter(Boolean);
}

function tableLines(table: Table): string[] {
  return [table.columns.map(String).join(" | "), ...table.rows.map((r) => r.map(String).join(" | "))];
}

function finish(lines: string[]): string {
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

function pqLine(b: Pick<PqBlock, "part" | "text">): string {
  return b.part ? `(${b.part}): ${b.text}` : b.text;
}

/** The answer part of a PQ reply without its header, for when the saved text cannot be patched. */
function pqTextFallback(blocks: PqBlock[], c: ReportContent): string {
  const lines: string[] = [];
  for (const b of blocks) {
    lines.push(pqLine(b));
    if (b.table && !b.annexure) lines.push(...tableLines(b.table), "");
    lines.push("");
  }
  for (const b of blocks) {
    if (b.annexure && b.table) lines.push("", b.annexure.toUpperCase(), ...tableLines(b.table), "");
  }
  const sources = chipSources(c);
  if (sources.size > 0) {
    lines.push("", "SOURCES (internal, remove before sending)");
    for (const s of sources.values()) lines.push(`[${s.id}] ${s.document}, page ${s.page}`);
  }
  return finish(lines);
}

/**
 * The saved text with each edited answer line swapped in place, so the header, the question
 * and the sources list stay exactly as the generator wrote them. Answer lines are searched
 * for after the ANSWER heading and in order, so a question line is never mistaken for one.
 */
function pqText(c: ReportContent, blocks: PqBlock[]): string {
  const before = c.blocks ?? [];
  let text = c.text ?? "";
  if (!text) return pqTextFallback(blocks, c);
  const answerAt = text.search(/\nANSWER\n/);
  let cursor = answerAt >= 0 ? answerAt : 0;
  for (let i = 0; i < blocks.length; i++) {
    const oldLine = pqLine(before[i]);
    if (!before[i].text) return pqTextFallback(blocks, c);
    const at = text.indexOf(oldLine, cursor);
    if (at < 0) return pqTextFallback(blocks, c);
    const newLine = pqLine(blocks[i]);
    text = text.slice(0, at) + newLine + text.slice(at + oldLine.length);
    cursor = at + newLine.length;
  }
  return text;
}

/** The same plain rendering the server makes for a monthly report or briefing note. */
export function sectionsText(c: ReportContent, sections: DraftSection[]): string {
  const lines: string[] = [];
  if (c.title) lines.push(c.title);
  if (c.subtitle) lines.push(c.subtitle);
  lines.push("");
  for (const s of sections) {
    if (s.heading) lines.push(s.heading);
    for (const l of s.lines ?? []) lines.push(s.bullets ? `• ${l}` : l);
    if (s.table) lines.push(...tableLines(s.table), "");
    lines.push(...(s.notes ?? []));
    lines.push("");
  }
  const sources = chipSources(c);
  if (sources.size > 0) {
    lines.push("SOURCES (internal, remove before sending)");
    for (const s of sources.values()) lines.push(`[${s.id}] ${s.document}, page ${s.page}`);
  }
  return finish(lines);
}

/**
 * The full content_json to save: everything the report already holds, the edited blocks or
 * sections, and `text` rendered again. Unchanged blocks and sections are passed through
 * untouched, and when nothing changed the saved text is kept as it is.
 */
export function mergeContent(c: ReportContent, mode: EditMode, edits: string[]): ReportContent {
  const before = originalEdits(c, mode);
  const changed = edits.some((e, i) => e !== before[i]);
  if (mode === "text") return { ...c, text: edits[0] ?? "" };
  if (!changed) return { ...c };
  if (mode === "blocks") {
    const blocks = (c.blocks ?? []).map((b, i) => (edits[i] === before[i] ? b : { ...b, text: edits[i].trim() }));
    return { ...c, blocks, text: pqText(c, blocks) };
  }
  const sections = (c.sections ?? []).map((s, i) =>
    edits[i] === before[i] ? s : { ...s, lines: sectionLines(edits[i], s.bullets) },
  );
  return { ...c, sections, text: sectionsText(c, sections) };
}

// --- unsaved work kept in the tab --------------------------------------------------------------

export function stashKey(id: string): string {
  return `ks_draft_${id}`;
}

export function writeStash(id: string, mode: EditMode, edits: string[]): void {
  sessionStorage.setItem(stashKey(id), JSON.stringify({ mode, edits }));
}

/** Edits stashed for this report, if they still fit its shape. Older stashes held the plain text. */
export function readStash(id: string, mode: EditMode, count: number): string[] | null {
  const raw = sessionStorage.getItem(stashKey(id));
  if (raw === null) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    // not JSON: an older stash of the plain text
    return mode === "text" ? [raw] : null;
  }
  const stash = parsed as { mode?: unknown; edits?: unknown } | null;
  const isStash = !!stash && typeof stash === "object" && "mode" in stash && "edits" in stash;
  if (!isStash) return mode === "text" ? [raw] : null;
  if (
    stash.mode === mode &&
    Array.isArray(stash.edits) &&
    stash.edits.length === count &&
    stash.edits.every((e) => typeof e === "string")
  )
    return stash.edits as string[];
  return null;
}

// --- workflow history --------------------------------------------------------------------------

const kindOf = (v: ReportVersionRow) => versionLine(v).kind;

function isDecision(v: ReportVersionRow): boolean {
  const kind = kindOf(v);
  return kind === "approved" || kind === "returned";
}

/** Why the approver sent it back: the approver's comment on the latest "returned" version. */
export function latestReturn(versions: ReportVersionRow[]): { comment: string; by: string; at: string } | null {
  const v = [...versions].sort((a, b) => b.version - a.version).find((x) => kindOf(x) === "returned");
  return v ? { comment: versionLine(v).comment ?? "", by: v.editor.name, at: v.created_at } : null;
}

/** Who sent it for approval: the last person to save it before the approver's decision. */
export function lastEditor(versions: ReportVersionRow[]): ReportVersionRow | null {
  return [...versions].sort((a, b) => b.version - a.version).find((v) => !isDecision(v)) ?? null;
}

export type TimelineEvent = {
  kind: "created" | "submitted" | "returned" | "approved" | "exported";
  at: string | null;
  by?: string;
  note?: string;
};

/**
 * Milestones from the version history. A submit has no version of its own, so each one is
 * placed at the save just before it (the editor always saves on submit), and the current
 * one at the report's last change.
 */
export function timeline(report: ReportRow, versions: ReportVersionRow[]): TimelineEvent[] {
  const asc = [...versions].sort((a, b) => a.version - b.version);
  const events: TimelineEvent[] = [
    { kind: "created", at: report.created_at, by: asc[0]?.editor.name },
  ];
  let lastSave: ReportVersionRow | null = asc[0] ?? null;
  for (const v of asc.slice(1)) {
    if (!isDecision(v)) {
      lastSave = v;
      continue;
    }
    events.push({ kind: "submitted", at: lastSave?.created_at ?? null, by: lastSave?.editor.name });
    if (kindOf(v) === "approved") events.push({ kind: "approved", at: v.created_at, by: v.editor.name });
    else
      events.push({
        kind: "returned",
        at: v.created_at,
        by: v.editor.name,
        note: versionLine(v).comment ?? undefined,
      });
  }
  if (report.status === "IN_REVIEW") events.push({ kind: "submitted", at: report.updated_at, by: lastSave?.editor.name });
  if (report.status === "EXPORTED") events.push({ kind: "exported", at: report.updated_at });
  return events;
}
