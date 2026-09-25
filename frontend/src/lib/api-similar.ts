import { api } from "@/lib/api";

/** A past Parliament question like the one being answered: a reply approved here (open it
 * at /reports/{report_id}) or an uploaded PQ answer (open the page and chunk that matched). */
export type SimilarPq = {
  kind: "approved_reply" | "pq_document";
  title: string;
  house: "LS" | "RS" | null;
  q_type: "starred" | "unstarred" | null;
  q_no: string | null;
  answer_date: string | null;
  /** Part of the question, or of the matching page, around the words searched for. */
  snippet: string;
  /** The start of the reply, when known. */
  answer: string | null;
  /** Only meaningful for ordering. */
  score: number;
  report_id: string | null;
  document_id: string | null;
  document_title: string | null;
  page: number | null;
  chunk_id: string | null;
};

/** What is searched: long questions are cut, since the start carries the subject. */
export const SIMILAR_MAX_TEXT = 2000;
export const SIMILAR_MIN_TEXT = 3;

export function similarPqs(
  text: string,
  opts: { limit?: number; exclude?: string | null } = {},
): Promise<SimilarPq[]> {
  const q = new URLSearchParams({ text: text.slice(0, SIMILAR_MAX_TEXT) });
  if (opts.limit) q.set("limit", String(opts.limit));
  if (opts.exclude) q.set("exclude", opts.exclude);
  return api<SimilarPq[]>(`/pq/similar?${q}`);
}
