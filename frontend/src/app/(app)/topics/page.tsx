"use client";

// Topic explorer (guide section 11): word cloud, top topics, per-topic trend by year, and a
// topic's questions. The server returns weighted words as JSON; the cloud is drawn here.

import { Cloud, ListTree, MessagesSquare, RefreshCw, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useMe } from "@/components/AppShell";
import TopicFilters, { DEFAULT_FILTERS, yearErrors } from "@/components/topics/TopicFilters";
import TopicList from "@/components/topics/TopicList";
import TopicQuestions from "@/components/topics/TopicQuestions";
import WordChip from "@/components/topics/WordChip";
import WordCloudView from "@/components/topics/WordCloudView";
import YearChart from "@/components/topics/YearChart";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import Spinner from "@/components/ui/Spinner";
import { useToast } from "@/components/ui/Toast";
import { errorText } from "@/lib/errors";
import { formatDateTime, formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import {
  getWordCloud,
  keywordsInclude,
  listTopicQuestions,
  listTopics,
  questionUses,
  rerunTopics,
  type TopicQuestion,
  type TopicRow,
  type TopicRun,
  type WordCloud,
  type WordCloudFilters,
} from "@/lib/topics";

const DEBOUNCE_MS = 300;

/** A response or error tagged with the request it answers, so a stale one is never shown. */
type Tagged<T> = { key: string; value: T };

export default function TopicsPage() {
  const me = useMe();
  const { t, locale } = useT();
  const toast = useToast();
  const isAdmin = can(me, "manage_admin");

  // Word cloud: filters are applied after a short pause in typing.
  const [filters, setFilters] = useState<WordCloudFilters>(DEFAULT_FILTERS);
  const [cloudNonce, setCloudNonce] = useState(0);
  const [cloud, setCloud] = useState<Tagged<WordCloud> | null>(null);
  const [cloudError, setCloudError] = useState<Tagged<string> | null>(null);
  const firstCloud = useRef(true);

  // Topics of the latest run.
  const [topicsNonce, setTopicsNonce] = useState(0);
  const [run, setRun] = useState<TopicRun | null>(null);
  const [topicsError, setTopicsError] = useState<string | null>(null);

  // Drill-down: a word from the cloud, a topic, and a year from its chart.
  const [word, setWord] = useState<string | undefined>(undefined);
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const [year, setYear] = useState<string | undefined>(undefined);
  const [questionsNonce, setQuestionsNonce] = useState(0);
  const [questions, setQuestions] = useState<Tagged<TopicQuestion[]> | null>(null);
  const [questionsError, setQuestionsError] = useState<Tagged<string> | null>(null);

  const [rerunning, setRerunning] = useState(false);

  const years = yearErrors(filters);
  const cloudQuery = years.from || years.to ? null : filters;
  const cloudKey = cloudQuery ? `${JSON.stringify(cloudQuery)}#${cloudNonce}` : null;

  useEffect(() => {
    if (!cloudQuery || !cloudKey) return;
    const ctrl = new AbortController();
    const delay = firstCloud.current ? 0 : DEBOUNCE_MS;
    firstCloud.current = false;
    const timer = window.setTimeout(() => {
      getWordCloud(cloudQuery, ctrl.signal).then(
        (value) => !ctrl.signal.aborted && setCloud({ key: cloudKey, value }),
        (e: unknown) => !ctrl.signal.aborted && setCloudError({ key: cloudKey, value: errorText(e, t) }),
      );
    }, delay);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
    // cloudKey captures every field of cloudQuery.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cloudKey]);

  useEffect(() => {
    const ctrl = new AbortController();
    listTopics(ctrl.signal).then(
      (r) => !ctrl.signal.aborted && setRun(r),
      (e: unknown) => !ctrl.signal.aborted && setTopicsError(errorText(e)),
    );
    return () => ctrl.abort();
  }, [topicsNonce]);

  const visibleTopics = useMemo(() => {
    const all = run?.topics ?? [];
    return word ? all.filter((x) => keywordsInclude(x.keywords, word)) : all;
  }, [run, word]);
  const selected: TopicRow | null = visibleTopics.find((x) => x.id === selectedId) ?? visibleTopics[0] ?? null;

  const questionsKey = selected ? `${selected.id}|${year ?? ""}#${questionsNonce}` : null;

  useEffect(() => {
    if (!selected || !questionsKey) return;
    const ctrl = new AbortController();
    listTopicQuestions(selected.id, year, ctrl.signal).then(
      (value) => !ctrl.signal.aborted && setQuestions({ key: questionsKey, value }),
      (e: unknown) => !ctrl.signal.aborted && setQuestionsError({ key: questionsKey, value: errorText(e, t) }),
    );
    return () => ctrl.abort();
    // questionsKey captures the topic id and year.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questionsKey]);

  // One shared year axis for every topic, so trends are comparable.
  const yearAxis = useMemo(() => {
    const all = new Set<string>();
    for (const topic of run?.topics ?? []) {
      for (const y of Object.keys(topic.period_counts.year ?? {})) all.add(y);
    }
    const sorted = [...all].sort();
    if (sorted.length === 0) return [];
    const out: string[] = [];
    for (let y = Number(sorted[0]); y <= Number(sorted[sorted.length - 1]); y++) out.push(String(y));
    return out;
  }, [run]);

  function pickWord(w: string) {
    setWord(w === word ? undefined : w);
    setYear(undefined);
  }

  function selectTopic(topic: TopicRow) {
    setSelectedId(topic.id);
    setYear(undefined);
  }

  function retryTopics() {
    setTopicsError(null);
    setTopicsNonce((n) => n + 1);
  }

  async function rerun() {
    setRerunning(true);
    try {
      const res = await rerunTopics();
      if (res.queued) toast({ tone: "success", title: t("rerunQueued") });
      else toast({ tone: "danger", title: t("topics.rerunFailed"), body: t("rerunOffline") });
    } catch (e) {
      toast({ tone: "danger", title: t("topics.rerunFailed"), body: errorText(e, t) });
    } finally {
      setRerunning(false);
    }
  }

  // Panel states, in order: error, first load, empty, content.
  const cloudErr = cloudError && cloudError.key === cloudKey ? cloudError.value : null;
  const cloudLoading = !!cloudKey && cloud?.key !== cloudKey && !cloudErr;
  const questionsErr = questionsError && questionsError.key === questionsKey ? questionsError.value : null;
  const questionsReady = questions && questions.key === questionsKey ? questions.value : null;
  const shownQuestions = questionsReady && word ? questionsReady.filter((q) => questionUses(q, word)) : questionsReady;

  const wordChip = word ? <WordChip word={word} onRemove={() => pickWord(word)} /> : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("topicsTitle")}
        description={t("topicsHelp")}
        meta={
          run &&
          (run.built_at ? (
            <Badge tone="neutral" dot>
              {t("builtAt")} {formatDateTime(run.built_at, locale)} · {formatNumber(run.total_questions, locale)}{" "}
              {t("questionsWord")}
            </Badge>
          ) : (
            <Badge tone="warning" dot>
              {t("topics.notBuilt")}
            </Badge>
          ))
        }
        actions={
          isAdmin && (
            <Button variant="secondary" icon={<RefreshCw size={16} aria-hidden />} loading={rerunning} onClick={rerun}>
              {t("rerunTopics")}
            </Button>
          )
        }
      />

      <TopicFilters value={filters} onChange={setFilters} />

      <Card>
        <CardHeader
          title={t("wordCloud")}
          subtitle={
            cloud
              ? `${formatNumber(cloud.value.texts, locale)} ${t("textsCounted")} · ${t("topics.wordCloudHint")}`
              : t("topics.wordCloudHint")
          }
          icon={<Cloud />}
          actions={
            <>
              {cloudLoading && cloud && (
                <span role="status" className="inline-flex items-center gap-1.5 text-xs text-muted">
                  <Spinner size={14} /> {t("topics.updating")}
                </span>
              )}
              {wordChip}
            </>
          }
        />
        {cloudErr ? (
          <Alert
            tone="danger"
            title={t("topics.cloudFailed")}
            action={
              <Button variant="outline" size="sm" onClick={() => setCloudNonce((n) => n + 1)}>
                {t("retry")}
              </Button>
            }
          >
            {cloudErr}
          </Alert>
        ) : !cloud ? (
          <CloudSkeleton />
        ) : cloud.value.words.length === 0 ? (
          <EmptyState compact icon={<Cloud />} title={t("noWords")} />
        ) : (
          <WordCloudView words={cloud.value.words} active={word} onPick={pickWord} />
        )}
      </Card>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:items-stretch">
        {/* On wide screens the topic list takes exactly the height of the right column and
            scrolls inside, instead of ending early and leaving a blank area. */}
        <div className="min-w-0 lg:relative">
          <Card className="lg:absolute lg:inset-0">
            <CardHeader
              title={t("topTopics")}
              subtitle={
                run && run.topics.length > 0
                  ? `${formatNumber(visibleTopics.length, locale)} / ${formatNumber(run.topics.length, locale)} ${t("topics.topicCount")}`
                  : undefined
              }
              icon={<ListTree />}
              actions={wordChip}
            />
            {topicsError ? (
              <Alert
                tone="danger"
                title={t("topics.topicsFailed")}
                action={
                  <Button variant="outline" size="sm" onClick={retryTopics}>
                    {t("retry")}
                  </Button>
                }
              >
                {topicsError}
              </Alert>
            ) : !run ? (
              <ListSkeleton rows={5} className="h-20" />
            ) : run.topics.length === 0 ? (
              <EmptyState compact icon={<ListTree />} title={t("noTopicsYet")}>
                {isAdmin ? t("topics.noTopicsAdminHint") : undefined}
              </EmptyState>
            ) : visibleTopics.length === 0 ? (
              <EmptyState
                compact
                icon={<ListTree />}
                title={t("topics.noTopicsForWord")}
                action={
                  <Button variant="outline" size="sm" onClick={() => pickWord(word ?? "")}>
                    {t("topics.removeWordFilter")}
                  </Button>
                }
              >
                {t("topics.noTopicsForWordHint")}
              </EmptyState>
            ) : (
              <TopicList topics={visibleTopics} selectedId={selected?.id} word={word} onSelect={selectTopic} />
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader
              title={selected ? `${t("questionsPerYear")}: ${selected.label}` : t("questionsPerYear")}
              subtitle={selected ? t("clickBarHint") : undefined}
              icon={<TrendingUp />}
              actions={
                year && (
                  <Button variant="ghost" size="sm" onClick={() => setYear(undefined)}>
                    {t("allYears")}
                  </Button>
                )
              }
            />
            {!run && !topicsError ? (
              <Skeleton className="h-52 rounded-panel" />
            ) : !selected ? (
              <EmptyState compact icon={<TrendingUp />} title={t("topics.selectTopic")} />
            ) : yearAxis.length === 0 || Object.keys(selected.period_counts.year ?? {}).length === 0 ? (
              <EmptyState compact icon={<TrendingUp />} title={t("topics.noYearData")} />
            ) : (
              <YearChart
                years={yearAxis}
                counts={selected.period_counts.year ?? {}}
                active={year}
                onPick={(y) => setYear(y === year ? undefined : y)}
              />
            )}
          </Card>

          {(selected || !run) && !topicsError && (
            <Card>
              <CardHeader
                title={year ? `${t("questionsInTopic")} (${year})` : t("questionsInTopic")}
                subtitle={
                  shownQuestions ? `${formatNumber(shownQuestions.length, locale)} ${t("questionsWord")}` : undefined
                }
                icon={<MessagesSquare />}
                actions={wordChip}
              />
              {questionsErr ? (
                <Alert
                  tone="danger"
                  title={t("topics.questionsFailed")}
                  action={
                    <Button variant="outline" size="sm" onClick={() => setQuestionsNonce((n) => n + 1)}>
                      {t("retry")}
                    </Button>
                  }
                >
                  {questionsErr}
                </Alert>
              ) : !shownQuestions ? (
                <ListSkeleton rows={4} className="h-16" />
              ) : shownQuestions.length === 0 ? (
                <EmptyState
                  compact
                  icon={<MessagesSquare />}
                  title={
                    word && questionsReady && questionsReady.length > 0
                      ? t("topics.noQuestionsWord")
                      : year
                        ? t("topics.noQuestionsYear")
                        : t("topics.noQuestions")
                  }
                />
              ) : (
                <TopicQuestions key={questionsKey} questions={shownQuestions} word={word} />
              )}
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function CloudSkeleton() {
  const { t } = useT();
  const widths = ["w-16", "w-24", "w-12", "w-32", "w-20", "w-14", "w-28", "w-16", "w-20", "w-10", "w-24", "w-16"];
  const heights = ["h-5", "h-8", "h-4", "h-10", "h-6", "h-5", "h-7", "h-4", "h-9", "h-5", "h-6", "h-4"];
  return (
    <div
      role="status"
      aria-label={t("loading")}
      className="flex flex-wrap items-center justify-center gap-3 rounded-panel bg-surface-subtle p-6"
    >
      {widths.map((w, i) => (
        <Skeleton key={i} className={`${w} ${heights[i]} rounded-full`} />
      ))}
    </div>
  );
}

function ListSkeleton({ rows, className }: { rows: number; className: string }) {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="space-y-2">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className={`${className} rounded-panel`} />
      ))}
    </div>
  );
}
