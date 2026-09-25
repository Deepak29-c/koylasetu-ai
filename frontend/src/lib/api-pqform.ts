// Calls for the New PQ reply form (parts preview, question from a file) and for adding an
// answer from Ask to a report.

import { editMode } from "@/components/reports/content";
import {
  api,
  createReport,
  getReport,
  listReports,
  type ReportRow,
  type ReportType,
  updateReport,
} from "@/lib/api";
import { appendText } from "@/lib/askReport";
import { EDITABLE_STATUSES } from "@/lib/reportView";

export type PqPartsOut = {
  /** "single": the question has no (a), (b)… markers of its own. */
  method: "markers" | "single";
  intro: string;
  parts: { part: string; text: string }[];
  /** Parts after this many are not answered. */
  max_parts: number;
};

/** The parts the server splits the question into on its markers; the model is not asked. */
export function previewPqParts(questionText: string, signal?: AbortSignal): Promise<PqPartsOut> {
  return api<PqPartsOut>("/pq-replies/parts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_text: questionText }),
    signal,
  });
}

export type PqQuestionTextOut = { filename: string; text: string; truncated: boolean };

/** The plain text of a PDF, Word or .txt file. The server does not keep the file. */
export function importQuestionText(file: File): Promise<PqQuestionTextOut> {
  const body = new FormData();
  body.append("file", file);
  return api<PqQuestionTextOut>("/pq-replies/question-text", { method: "POST", body });
}

/** A report kept as one plain text. Generated replies and reports are edited part by part and
 * their text is rendered again from the parts on every save, so text added at its end would
 * be lost. */
export function isPlainTextReport(r: ReportRow): boolean {
  return editMode(r.content_json ?? {}) === "text";
}

/** Plain-text reports that can still be edited, newest change first. */
export async function listEditableReports(): Promise<ReportRow[]> {
  const rows = await listReports();
  return rows
    .filter((r) => EDITABLE_STATUSES.includes(r.status) && isPlainTextReport(r))
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

/** The report became a part-by-part report since the list was loaded. */
export class NotPlainText extends Error {
  constructor() {
    super("not_plain_text");
  }
}

/**
 * Add text to the end of a report. The report is read again first so nothing saved since the
 * list was loaded is lost, and the whole content_json goes back: the server replaces it.
 */
export async function appendToReport(id: string, addition: string): Promise<ReportRow> {
  const current = await getReport(id);
  if (!isPlainTextReport(current)) throw new NotPlainText();
  const content = current.content_json ?? {};
  return updateReport(id, { content_json: { ...content, text: appendText(content.text, addition) } });
}

export function newReportWithText(title: string, reportType: ReportType, text: string): Promise<ReportRow> {
  return createReport({ report_type: reportType, title, content_json: { text } });
}
