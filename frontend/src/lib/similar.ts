// Pure helpers for the similar-questions panel, kept out of the component so they can be
// tested without a browser (`npm test`). Type-only imports: no runtime code is pulled in.

import type { ReportRow } from "@/lib/api";

/** The question a PQ reply answers: the subject line and each part's question, read from
 * content_json. Replies without that structure fall back to their title. */
export function pqQuestionText(report: Pick<ReportRow, "title" | "content_json">): string {
  const content = report.content_json ?? {};
  const parts = [content.header?.subject ?? "", ...(content.blocks ?? []).map((b) => b.question ?? "")];
  const text = parts.join(" ").replace(/\s+/g, " ").trim();
  return text || report.title;
}
