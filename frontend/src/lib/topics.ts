// Topic explorer API (guide section 11). Kept out of api.ts so it stays a small, separate file.

import { api } from "@/lib/api";

export type WordCloudWord = { text: string; weight: number };
export type WordCloud = { source: string; texts: number; words: WordCloudWord[] };

export type PeriodCounts = {
  year?: Record<string, number>;
  session?: Record<string, number>;
  undated?: number;
};

export type TopicRow = {
  id: string;
  topic_no: number;
  label: string;
  keywords: string[];
  size: number;
  period_counts: PeriodCounts;
};

export type TopicRun = {
  run_id: string | null;
  built_at: string | null;
  total_questions: number;
  topics: TopicRow[];
};

export type TopicQuestion = {
  id: string;
  house: "LS" | "RS";
  q_type: "starred" | "unstarred";
  q_no: string | null;
  answer_date: string | null;
  subject: string | null;
  question_text: string;
  document_id: string | null;
  weight: number;
  keywords: string[];
};

export type WordCloudFilters = {
  house?: string;
  from?: string;
  to?: string;
  session?: string;
  subsidiary?: string;
  source?: string;
};

function query(params: Record<string, string | undefined>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) qs.set(key, value);
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export function getWordCloud(filters: WordCloudFilters, signal?: AbortSignal): Promise<WordCloud> {
  return api<WordCloud>(`/topics/wordcloud${query(filters)}`, { signal });
}

export function listTopics(signal?: AbortSignal): Promise<TopicRun> {
  return api<TopicRun>("/topics", { signal });
}

export function listTopicQuestions(topicId: string, year?: string, signal?: AbortSignal): Promise<TopicQuestion[]> {
  return api<TopicQuestion[]>(`/topics/${topicId}/questions${query({ year })}`, { signal });
}

export function rerunTopics(): Promise<{ queued: boolean }> {
  return api<{ queued: boolean }>("/topics/refresh", { method: "POST" });
}

/** Words of a keyword or text, lower-cased, for matching a word picked in the cloud. */
function words(text: string): string[] {
  return text.toLowerCase().split(/[^\p{L}\p{M}\p{N}]+/u).filter(Boolean);
}

/** True when any keyword is the word or contains it as a whole word. */
export function keywordsInclude(keywords: string[], word: string): boolean {
  const w = word.toLowerCase();
  return keywords.some((k) => k.toLowerCase() === w || words(k).includes(w));
}

/** True when the question's keywords, subject or text use the word. */
export function questionUses(q: TopicQuestion, word: string): boolean {
  const w = word.toLowerCase();
  return keywordsInclude(q.keywords, w) || words(`${q.subject ?? ""} ${q.question_text}`).includes(w);
}
