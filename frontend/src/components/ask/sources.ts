import type { ChipSource } from "@/components/Citation";
import type { AskResult, Citation } from "@/lib/api";

/** A citation from an answer as a source chip: figures link to their table cell, passages to their text block. */
export function toChipSource(c: Citation): ChipSource {
  return {
    id: c.id,
    document: c.document,
    document_id: c.document_id,
    page: c.page,
    bbox: c.kind === "fact" ? c.bbox : null,
    chunk_id: c.kind === "passage" ? c.chunk_id : null,
    excerpt: c.text,
    unverified: !!c.status && c.status !== "VERIFIED",
  };
}

export function chipSources(result: AskResult): Map<string, ChipSource> {
  return new Map(result.citations.map((c) => [c.id, toChipSource(c)]));
}

/** The answer as plain text, without the [C1] / [F2] markers. */
export function plainAnswer(answer: string): string {
  return answer
    .replace(/[ \t]*\[\s*[A-Z]\d+\s*\]/g, "")
    .replace(/[ \t]+([.,;:])/g, "$1")
    .trim();
}
