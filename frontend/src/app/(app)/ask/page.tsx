"use client";

import { Copy, MessageSquareText, RotateCcw, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";

import AnswerText from "@/components/ask/AnswerText";
import AskProgress from "@/components/ask/AskProgress";
import FiguresTable from "@/components/ask/FiguresTable";
import RecentQuestions from "@/components/ask/RecentQuestions";
import { chipSources, plainAnswer } from "@/components/ask/sources";
import { SourcesList } from "@/components/Citation";
import EmptyState from "@/components/ui/EmptyState";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Textarea } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { api, type AskResult, getQaAnswer, listQaHistory, type QaHistoryRow } from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { useT } from "@/lib/i18n";

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
  const toast = useToast();
  // The home page's quick-ask box hands the question over as ?q=…
  const params = useSearchParams();
  const prefill = params.get("q")?.trim() ?? "";
  // An answer already given: reopened from a source page, the browser's Back button,
  // or the recent list. It is read back, not asked again.
  const reopen = params.get("qa");
  const [restored, setRestored] = useState(false);
  const [historyRows, setHistoryRows] = useState<QaHistoryRow[] | null>(null);
  const [question, setQuestion] = useState(prefill);
  // "ask" while a new answer is written (started at `askedAt`), "open" while a saved one is read.
  const [busy, setBusy] = useState<"ask" | "open" | null>(null);
  const [askedAt, setAskedAt] = useState(0);
  const [result, setResult] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  // What failed, so "Retry" repeats it: asking again, or opening the same saved answer.
  const [retryAction, setRetryAction] = useState<(() => void) | null>(null);
  const [feedback, setFeedback] = useState<1 | -1 | null>(null);
  // Each ask or open takes the next number; a reply that is no longer the latest is dropped.
  const requestSeq = useRef(0);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    await runAsk(question);
  }

  const refreshHistory = () => listQaHistory().then(setHistoryRows, () => setHistoryRows([]));

  async function runAsk(asked: string) {
    setRestored(false);
    if (asked.trim().length < 3) return;
    const seq = ++requestSeq.current;
    setBusy("ask");
    setAskedAt(Date.now());
    setError(null);
    setResult(null);
    setFeedback(null);
    try {
      const answer = await api<AskResult>("/qa/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: asked }),
      });
      if (seq !== requestSeq.current) return;
      setResult(answer);
      // Put the answer in the address bar, so Back from a source page returns to it
      // instead of an empty form.
      window.history.replaceState(null, "", `/ask?qa=${answer.qa_id}`);
      void refreshHistory();
    } catch (err) {
      if (seq !== requestSeq.current) return;
      setError(errorText(err, t));
      setRetryAction(() => () => void runAsk(asked));
    } finally {
      if (seq === requestSeq.current) setBusy(null);
    }
  }

  async function showSaved(id: string) {
    const seq = ++requestSeq.current;
    setBusy("open");
    setError(null);
    setFeedback(null);
    try {
      const answer = await getQaAnswer(id);
      if (seq !== requestSeq.current) return;
      setResult(answer);
      setQuestion(answer.question ?? "");
      setRestored(true);
    } catch (err) {
      if (seq !== requestSeq.current) return;
      setError(errorText(err, t));
      setRetryAction(() => () => void showSaved(id));
    } finally {
      if (seq === requestSeq.current) setBusy(null);
    }
  }

  function openSaved(id: string) {
    if (busy) return;
    window.history.replaceState(null, "", `/ask?qa=${id}`);
    void showSaved(id);
  }

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    // Both of these set state as they start; kicked off after the effect rather than
    // during it, so the first render is not interrupted by a cascading update.
    const begin = reopen
      ? () => showSaved(reopen)
      : prefill.length >= 3
        ? () => runAsk(prefill)
        : null;
    void refreshHistory();
    if (begin) void Promise.resolve().then(begin);
    // showSaved and runAsk are new on every render; the ref above is what stops this
    // running twice, not the dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill, reopen]);

  async function sendFeedback(score: 1 | -1) {
    if (!result) return;
    const before = feedback;
    setFeedback(score);
    try {
      await fetchFeedback(result.qa_id, score);
      toast({ title: t("thanks") });
    } catch (err) {
      setFeedback(before);
      toast({ tone: "danger", title: t("ask.feedbackFailed"), body: errorText(err, t) });
    }
  }

  async function copyAnswer() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(plainAnswer(result.answer));
      toast({ title: t("ui.copied") });
    } catch (err) {
      toast({ tone: "danger", title: t("ask.copyFailed"), body: errorText(err, t) });
    }
  }

  const sources = useMemo(() => (result ? chipSources(result) : new Map()), [result]);
  // Source links come back to this saved answer, which is what the address bar shows once it is given.
  const from = result ? `/ask?qa=${result.qa_id}` : undefined;
  const tooShort = question.trim().length < 3;

  return (
    <div>
      <PageHeader title={t("askTitle")} description={t("askHelp")} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] 2xl:grid-cols-[minmax(0,1fr)_26rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card>
            <form onSubmit={onSubmit} className="space-y-4">
              <Field label={t("ask.questionLabel")} hint={t("ask.shortcutHint")}>
                <Textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void onSubmit(e);
                  }}
                  rows={3}
                  placeholder={t("askPlaceholder")}
                />
              </Field>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  loading={busy === "ask"}
                  disabled={busy !== null || tooShort}
                  icon={<Send size={16} aria-hidden />}
                >
                  {t("askButton")}
                </Button>
              </div>
            </form>
          </Card>

          {error && (
            <Alert
              tone="danger"
              title={t("ui.somethingWrong")}
              action={
                retryAction && (
                  <Button variant="danger-outline" size="sm" disabled={busy !== null} onClick={retryAction}>
                    {t("retry")}
                  </Button>
                )
              }
            >
              {error}
            </Alert>
          )}

          {busy === "ask" && <AskProgress startedAt={askedAt} />}

          {busy === "open" && !result && (
            <Card aria-busy="true">
              <div role="status" aria-label={t("loading")} className="space-y-3">
                <Skeleton className="h-6 w-48 rounded-full" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-11/12" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            </Card>
          )}

          {restored && result && (
            <Alert
              tone="info"
              action={
                <Button
                  variant="outline"
                  size="sm"
                  icon={<RotateCcw size={14} aria-hidden />}
                  onClick={() => void runAsk(question)}
                  disabled={busy !== null || tooShort}
                >
                  {t("qa.askAgain")}
                </Button>
              }
            >
              {t("qa.restored")}
            </Alert>
          )}

          {result && (
            <Card aria-labelledby="answer-title" className="space-y-5">
              <CardHeader
                id="answer-title"
                className="mb-0"
                icon={<MessageSquareText />}
                title={t("ask.answerTitle")}
                subtitle={
                  <>
                    {t("ask.answeredIn")}{" "}
                    <span className="tabular-nums">
                      {(result.latency_ms / 1000).toFixed(1)} {t("ui.seconds")}
                    </span>
                  </>
                }
                actions={
                  <>
                    <StatusBadge kind="confidence" value={result.confidence} />
                    <Button variant="outline" size="sm" icon={<Copy size={14} aria-hidden />} onClick={copyAnswer}>
                      {t("ask.copyAnswer")}
                    </Button>
                  </>
                }
              />

              <AnswerText result={result} sources={sources} from={from} />

              {result.unmatched_numbers.length > 0 && (
                <Alert tone="danger" title={`${t("unmatched")}: ${result.unmatched_numbers.join(", ")}`}>
                  {t("ask.unmatchedLegend")}
                </Alert>
              )}

              {result.table && (
                <section className="space-y-2">
                  <h3 className="text-sm font-semibold text-strong">{t("ask.figuresTitle")}</h3>
                  <FiguresTable table={result.table} sources={sources} from={from} />
                </section>
              )}

              <SourcesList sources={[...sources.values()]} from={from} />

              <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4 text-sm text-muted">
                <span id="feedback-question">{t("ask.feedbackQuestion")}</span>
                <div role="group" aria-labelledby="feedback-question" className="flex items-center gap-1">
                  <FeedbackButton
                    label={t("helpful")}
                    pressed={feedback === 1}
                    onClick={() => void sendFeedback(1)}
                    icon={<ThumbsUp size={16} aria-hidden />}
                  />
                  <FeedbackButton
                    label={t("notHelpful")}
                    pressed={feedback === -1}
                    onClick={() => void sendFeedback(-1)}
                    icon={<ThumbsDown size={16} aria-hidden />}
                  />
                </div>
              </div>
            </Card>
          )}

          {!result && busy === null && !error && (
            <EmptyState className="flex-1" icon={<MessageSquareText />} title={t("ask.answerHere")}>
              {t("ask.answerHereBody")}
            </EmptyState>
          )}
        </div>

        <RecentQuestions rows={historyRows} currentId={result?.qa_id} onOpen={openSaved} disabled={busy !== null} />
      </div>
    </div>
  );
}

function FeedbackButton({
  label,
  pressed,
  onClick,
  icon,
}: {
  label: string;
  pressed: boolean;
  onClick: () => void;
  icon: React.ReactNode;
}) {
  return (
    <Button
      variant={pressed ? "primary" : "ghost"}
      size="icon"
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      onClick={pressed ? undefined : onClick}
      className={cn(!pressed && "border border-line-strong")}
    >
      {icon}
    </Button>
  );
}

function fetchFeedback(qaId: string, score: 1 | -1) {
  return api<void>(`/qa/${qaId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score }),
  });
}
