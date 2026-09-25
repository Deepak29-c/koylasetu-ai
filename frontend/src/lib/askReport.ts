// An answer from Ask as plain report text: source markers become readable references and a
// short list of sources follows. Pure, so `npm test` can check it without a browser.
// Type-only imports: this file must not pull in runtime code.

import type { Citation } from "@/lib/api";

export type ReportTextLabels = {
  /** "p." */
  page: string;
  /** "Sources" */
  sources: string;
  /** "not yet verified" */
  unverified: string;
};

// One marker, or several side by side: "[C1]", "[F2] [C3]".
const MARKERS = /[ \t]*\[\s*[A-Z]\d+\s*\](?:[ \t]*\[\s*[A-Z]\d+\s*\])*/g;
const MARKER_ID = /\[\s*([A-Z]\d+)\s*\]/g;

function reference(c: Pick<Citation, "document" | "page">, labels: ReportTextLabels): string {
  return `${c.document}, ${labels.page} ${c.page}`;
}

/**
 * "NCL produced 12.70 MT [F1]." -> "NCL produced 12.70 MT (Coal Directory, p. 7)." Markers
 * with no citation behind them are dropped. The figures themselves are left as they are.
 */
export function answerWithReferences(
  answer: string,
  citations: Pick<Citation, "id" | "document" | "page">[],
  labels: ReportTextLabels,
): string {
  const byId = new Map(citations.map((c) => [c.id, c]));
  return answer
    .replace(MARKERS, (run) => {
      const refs = [...run.matchAll(MARKER_ID)]
        .map((m) => byId.get(m[1]))
        .filter((c) => c !== undefined)
        .map((c) => reference(c, labels));
      const unique = [...new Set(refs)];
      return unique.length ? ` (${unique.join("; ")})` : "";
    })
    .replace(/[ \t]+([.,;:।])/g, "$1")
    .trim();
}

/** One line per document page the answer cites, in the order they first appear. */
export function sourcesList(
  citations: Pick<Citation, "document" | "page" | "status">[],
  labels: ReportTextLabels,
): string {
  const lines: string[] = [];
  for (const c of citations) {
    const unverified = !!c.status && c.status !== "VERIFIED";
    const line = `- ${reference(c, labels)}${unverified ? ` (${labels.unverified})` : ""}`;
    if (!lines.includes(line)) lines.push(line);
  }
  return lines.length ? `${labels.sources}:\n${lines.join("\n")}` : "";
}

/** What is added to the report for one answer. */
export function answerForReport(
  answer: string,
  citations: Pick<Citation, "id" | "document" | "page" | "status">[],
  labels: ReportTextLabels,
): string {
  return [answerWithReferences(answer, citations, labels), sourcesList(citations, labels)]
    .filter(Boolean)
    .join("\n\n");
}

/** The report's text with `addition` after it, a blank line between the two. */
export function appendText(existing: string | null | undefined, addition: string): string {
  const before = (existing ?? "").trimEnd();
  return before ? `${before}\n\n${addition}` : addition;
}
