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
  const q = new URLSearchParams({ page: String(c.page) });
  if (c.kind === "fact" && c.bbox) q.set("box", c.bbox.join(","));  // highlight the table cell
  else if (c.chunk_id) q.set("chunk", c.chunk_id);
  return `/documents/${c.document_id}?${q}`;
}

function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Answer text with [C1] markers as source chips and unsupported numbers in red. */
function AnswerText({ result }: { result: AskResult }) {
  const { t } = useT();
  const byId = new Map(result.citations.map((c) => [c.id, c]));
  const unmatched = result.unmatched_numbers.filter(Boolean);
  const redRe = unmatched.length
    ? new RegExp(`(?<![\\d.,])(${unmatched.map(escapeRegex).join("|")})(?![\\d])`, "g")
    : null;

  const parts = result.answer.split(/(\[\s*[CF]\d+\s*\])/g);
  return (
    <p className="leading-7 whitespace-pre-wrap">
      {parts.map((part, i) => {
        const ref = part.match(/^\[\s*([CF]\d+)\s*\]$/)?.[1];
        if (ref) {
          const c = byId.get(ref);
          return c ? (
            <Link
              key={i}
              href={sourceHref(c)}
              title={c.text.slice(0, 200)}
              className="mx-0.5 inline-block rounded bg-brand-soft px-1.5 text-xs font-medium text-brand hover:underline"
            >
              {c.kind === "fact" ? `${c.id} · ` : ""}
              {c.document.slice(0, 28)}, p.{c.page}
              {c.status && c.status !== "VERIFIED" ? ` · ${t("unverified")}` : ""}
            </Link>
          ) : null;
        }
        if (!redRe) return <span key={i}>{part}</span>;
        return (
          <span key={i}>
            {part.split(redRe).map((piece, j) =>
              unmatched.includes(piece) ? (
                <mark key={j} className="rounded bg-red-100 px-0.5 text-red-800" title={t("unmatched")}>
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
            {result.table && <FiguresTable result={result} />}
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

/** Figures behind a NUMERIC answer, each row linked to the cell it was read from. */
function FiguresTable({ result }: { result: AskResult }) {
  const { t } = useT();
  const byId = new Map(result.citations.map((c) => [c.id, c]));
  const table = result.table!;
  return (
    <div className="overflow-x-auto rounded border">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50 text-gray-600">
          <tr>
            {table.columns.map((c) => (
              <th key={c} className="px-3 py-1.5 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => {
            const ref = row[row.length - 1];
            const c = byId.get(ref);
            return (
              <tr key={i} className="border-t">
                {row.slice(0, -1).map((cell, j) => (
                  <td key={j} className={`px-3 py-1.5 ${j === 3 ? "font-semibold" : ""}`}>
                    {j === 4 && cell !== "Verified" ? <span className="text-amber-800">{t("unverified")}</span> : cell}
                  </td>
                ))}
                <td className="px-3 py-1.5">
                  {c ? (
                    <Link href={sourceHref(c)} className="text-brand underline">
                      {c.document.slice(0, 24)}, p.{c.page}
                    </Link>
                  ) : (
                    ref
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
