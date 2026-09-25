"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { api, type AskResult, type Citation } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

const CONF_STYLE: Record<AskResult["confidence"], string> = {
  high: "border-green-300 bg-green-50 text-green-900",
  medium: "border-amber-300 bg-amber-50 text-amber-900",
  low: "border-red-300 bg-red-50 text-red-900",
};

function sourceHref(c: Citation) {
  return `/documents/${c.document_id}?page=${c.page}&chunk=${c.chunk_id}`;
}

function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Answer text with [C1] markers as source chips and unsupported numbers in red. */
function AnswerText({ result }: { result: AskResult }) {
  const byId = new Map(result.citations.map((c) => [c.id, c]));
  const unmatched = result.unmatched_numbers.filter(Boolean);
  const redRe = unmatched.length
    ? new RegExp(`(?<![\\d.,])(${unmatched.map(escapeRegex).join("|")})(?![\\d])`, "g")
    : null;

  const parts = result.answer.split(/(\[\s*C\d+\s*\])/g);
  return (
    <p className="leading-7 whitespace-pre-wrap">
      {parts.map((part, i) => {
        const ref = part.match(/^\[\s*(C\d+)\s*\]$/)?.[1];
        if (ref) {
          const c = byId.get(ref);
          return c ? (
            <Link
              key={i}
              href={sourceHref(c)}
              title={c.text.slice(0, 200)}
              className="mx-0.5 inline-block rounded bg-brand-soft px-1.5 text-xs font-medium text-brand hover:underline"
            >
              {c.document.slice(0, 28)}, p.{c.page}
            </Link>
          ) : null;
        }
        if (!redRe) return <span key={i}>{part}</span>;
        return (
          <span key={i}>
            {part.split(redRe).map((piece, j) =>
              unmatched.includes(piece) ? (
                <mark key={j} className="rounded bg-red-100 px-0.5 text-red-800" title="Not found in sources">
                  {piece}
                </mark>
              ) : (
                piece
              ),
            )}
          </span>
        );
      })}
    </p>
  );
}

export default function AskPage() {
  // useSearchParams needs a Suspense boundary for Next's static render pass.
  return (
    <Suspense fallback={null}>
      <AskPageInner />
    </Suspense>
  );
}

function AskPageInner() {
  const { t } = useT();
  // The home page's quick-ask box hands the question over as ?q=…
  const prefill = useSearchParams().get("q")?.trim() ?? "";
  const [question, setQuestion] = useState(prefill);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<1 | -1 | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    await runAsk(question);
  }

  async function runAsk(asked: string) {
    if (asked.trim().length < 3) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setFeedback(null);
    try {
      setResult(
        await api<AskResult>("/qa/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: asked }),
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const askedPrefill = useRef(false);
  useEffect(() => {
    if (prefill.length >= 3 && !askedPrefill.current) {
      askedPrefill.current = true;
      void runAsk(prefill);
    }
  }, [prefill]);

  async function sendFeedback(score: 1 | -1) {
    if (!result) return;
    setFeedback(score);
    try {
      await fetchFeedback(result.qa_id, score);
    } catch {
      setFeedback(null);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("askTitle")}</h1>
        <p className="text-sm text-gray-600">{t("askHelp")}</p>
      </div>

      <form onSubmit={onSubmit} className="space-y-3 rounded border bg-white p-4">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) onSubmit(e);
          }}
          rows={3}
          placeholder={t("askPlaceholder")}
          className="w-full rounded border px-3 py-2"
        />
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy || question.trim().length < 3}
            className="rounded bg-brand px-6 py-2.5 font-medium text-white disabled:opacity-50"
          >
            {t("askButton")}
          </button>
          {busy && <span className="text-sm text-gray-600">{t("thinking")}</span>}
        </div>
      </form>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}

      {result && (
        <div className="space-y-4">
          <div className="space-y-3 rounded border bg-white p-5">
            <div className={`inline-block rounded border px-2.5 py-1 text-xs font-medium ${CONF_STYLE[result.confidence]}`}>
              {t(`conf.${result.confidence}` as LabelKey)}
            </div>
            <AnswerText result={result} />
            {result.unmatched_numbers.length > 0 && (
              <p className="text-sm text-red-800">
                {t("unmatched")}: {result.unmatched_numbers.join(", ")}
              </p>
            )}
            <div className="flex items-center gap-3 border-t pt-3 text-sm text-gray-600">
              <span>{(result.latency_ms / 1000).toFixed(1)} s</span>
              {feedback === null ? (
                <>
                  <button onClick={() => sendFeedback(1)} className="rounded border px-2 py-0.5 hover:bg-gray-50">
                    👍 {t("helpful")}
                  </button>
                  <button onClick={() => sendFeedback(-1)} className="rounded border px-2 py-0.5 hover:bg-gray-50">
                    👎 {t("notHelpful")}
                  </button>
                </>
              ) : (
                <span>{t("thanks")}</span>
              )}
            </div>
          </div>

          {result.citations.length > 0 && (
            <div className="space-y-2">
              <h2 className="font-semibold">{t("sources")}</h2>
              {result.citations.map((c) => (
                <div key={c.id} className="rounded border bg-white p-3 text-sm">
                  <div className="mb-1 flex items-center justify-between gap-3">
                    <span className="font-medium">
                      [{c.id}] {c.document} · {t("page")} {c.page}
                    </span>
                    <Link href={sourceHref(c)} className="shrink-0 text-brand underline">
                      {t("openPage")}
                    </Link>
                  </div>
                  <p className="line-clamp-3 text-gray-700">{c.text}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function fetchFeedback(qaId: string, score: 1 | -1) {
  return api<void>(`/qa/${qaId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score }),
  });
}
