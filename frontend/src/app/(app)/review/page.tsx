"use client";

import { BadgeCheck, Bot, CircleCheckBig, Database, Flag, History, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useMe } from "@/components/AppShell";
import DecidedList from "@/components/review/DecidedList";
import ReviewDetail, {
  type ReviewAction,
  type ReviewDetailHandle,
  ReviewDetailSkeleton,
} from "@/components/review/ReviewDetail";
import ReviewFilters, { applyFilters, NO_FILTERS, type ReviewFilterState } from "@/components/review/ReviewFilters";
import ReviewList, { ReviewListSkeleton, ShortcutsHint } from "@/components/review/ReviewList";
import { fill, useFigureText } from "@/components/review/figureText";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import Stat from "@/components/ui/Stat";
import Tabs from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { api, type DecidedItem, type Fact, type ReviewItem, type ReviewSummary } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatNumber } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

const DONE_TOAST: Record<ReviewAction, LabelKey> = {
  ACCEPT: "reviewDoneAccepted",
  EDIT: "reviewDoneCorrected",
  REJECT: "reviewDoneRejected",
};

type View = "waiting" | "decided";

/** Keys typed into a field are text, not shortcuts. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export default function ReviewPage() {
  const me = useMe();
  const { t, locale } = useT();
  const fx = useFigureText();
  const toast = useToast();
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState<ReviewFilterState>(NO_FILTERS);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("waiting");
  const [decided, setDecided] = useState<DecidedItem[] | null>(null);
  const [decidedId, setDecidedId] = useState<string | null>(null);
  const [decidedError, setDecidedError] = useState<string | null>(null);
  const detailRef = useRef<ReviewDetailHandle>(null);
  const allowed = can(me, "review_facts");

  const load = useCallback(
    () =>
      Promise.all([api<ReviewItem[]>("/review/issues"), api<ReviewSummary>("/review/summary")]).then(
        ([queue, s]) => {
          setError(null);
          setItems(queue);
          setSummary(s);
        },
        (e: unknown) => setError(errorText(e)),
      ),
    [],
  );

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  // Refetched each time the tab opens, so figures decided in the queue show up; the old list stays meanwhile.
  const loadDecided = useCallback(
    () =>
      api<DecidedItem[]>("/review/decided").then(
        (list) => {
          setDecidedError(null);
          setDecided(list);
        },
        (e: unknown) => setDecidedError(errorText(e)),
      ),
    [],
  );

  useEffect(() => {
    if (allowed && view === "decided") loadDecided();
  }, [allowed, view, loadDecided]);

  const visible = useMemo(() => (items ? applyFilters(items, filters) : []), [items, filters]);
  // The selection falls back to the first visible figure when it is filtered out or decided.
  const selected = visible.find((i) => i.fact.id === selectedId) ?? visible[0] ?? null;
  const decidedList = useMemo(() => decided ?? [], [decided]);
  const selectedDecided = decidedList.find((d) => d.fact.id === decidedId) ?? decidedList[0] ?? null;

  const move = useCallback(
    (step: 1 | -1) => {
      const ids = view === "waiting" ? visible.map((i) => i.fact.id) : decidedList.map((d) => d.fact.id);
      if (!ids.length) return;
      const current = view === "waiting" ? selected : selectedDecided;
      const at = current ? ids.indexOf(current.fact.id) : -1;
      const next = ids[Math.min(Math.max(at + step, 0), ids.length - 1)];
      (view === "waiting" ? setSelectedId : setDecidedId)(next);
    },
    [view, visible, selected, decidedList, selectedDecided],
  );

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.ctrlKey || e.metaKey || e.altKey || isTyping(e.target)) return;
      if (document.querySelector('[role="dialog"]')) return;
      const key = e.key;
      if (key === "j" || key === "ArrowDown") move(1);
      else if (key === "k" || key === "ArrowUp") move(-1);
      else if (key === "a") detailRef.current?.accept();
      else if (key === "e") detailRef.current?.startCorrect();
      else if (key === "r") detailRef.current?.startReject();
      else return;
      e.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move]);

  /** "12.5 MT", or "12.5 → 12.8 MT" for a correction. */
  function figure(before: Fact, action: ReviewAction, saved: Fact) {
    return action === "EDIT"
      ? [`${before.value_raw} → ${saved.value_raw}`, before.unit].filter(Boolean).join(" ")
      : fx.printed(before);
  }

  function done(fact: Fact, action: ReviewAction, saved: Fact) {
    const factId = fact.id;
    const all = items ?? [];
    // Next figure: the one after the decided one in the visible list, else the one before.
    const at = visible.findIndex((i) => i.fact.id === factId);
    const rest = visible.filter((i) => i.fact.id !== factId);
    const next = rest[Math.min(Math.max(at, 0), rest.length - 1)] ?? null;
    setItems(all.filter((i) => i.fact.id !== factId));
    setSelectedId(next?.fact.id ?? null);
    toast({
      tone: action === "REJECT" ? "info" : "success",
      title: t(DONE_TOAST[action]),
      body: [
        `${fact.label || fx.metricLabel(fact.metric)}: ${figure(fact, action, saved)}`,
        t(rest.length ? "reviewDoneNext" : "reviewDoneLast"),
      ].join(" · "),
    });
    api<ReviewSummary>("/review/summary").then(setSummary, () => {});
  }

  /** A changed decision: the figure stays in the decided list, now with its new decision first. */
  function changed(fact: Fact, action: ReviewAction, saved: Fact) {
    toast({
      tone: action === "REJECT" ? "info" : "success",
      title: t(DONE_TOAST[action]),
      body: `${fact.label || fx.metricLabel(fact.metric)}: ${figure(fact, action, saved)}`,
    });
    setDecidedId(fact.id);
    loadDecided();
    api<ReviewSummary>("/review/summary").then(setSummary, () => {});
  }

  if (!allowed) {
    return (
      <>
        <PageHeader title={t("reviewTitle")} />
        <EmptyState icon={<ShieldAlert />} title={t("noPermission")} />
      </>
    );
  }

  const left = items?.length ?? 0;
  const decidedCount = summary ? summary.reviewed_verified + summary.rejected : 0;
  const progressTotal = summary ? decidedCount + summary.flagged : 0;
  const progressPct = progressTotal ? Math.round((100 * decidedCount) / progressTotal) : 0;
  const num = (n: number) => formatNumber(n, locale);

  const description = (
    <>
      <span className="block">{t("reviewHelp")}</span>
      {items && summary && (
        <span className="mt-3 flex max-w-md flex-col gap-1.5">
          <span className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
            <span className="font-semibold text-strong">{fill(t("review.leftToReview"), { n: num(left) })}</span>
            <span className="text-muted tabular-nums">
              {fill(t("review.progress"), { done: num(decidedCount), total: num(progressTotal) })}
            </span>
          </span>
          <span
            role="progressbar"
            aria-label={t("review.progressLabel")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progressPct}
            className="block h-1.5 overflow-hidden rounded-full bg-surface-sunken"
          >
            <span className="block h-full rounded-full bg-brand" style={{ width: `${progressPct}%` }} />
          </span>
        </span>
      )}
    </>
  );

  const stats = summary && [
    { id: "total", label: t("totalFacts"), value: num(summary.total_facts), icon: <Database />, tone: "brand" as const },
    {
      id: "auto",
      label: t("autoVerified"),
      value: num(summary.auto_verified),
      icon: <Bot />,
      tone: "info" as const,
      note:
        summary.automation_percent != null
          ? `${t("automation")}: ${fill(t("review.automationNote"), { p: formatNumber(summary.automation_percent, locale, 1) })}`
          : undefined,
    },
    {
      id: "flagged",
      label: t("flaggedFacts"),
      value: num(summary.flagged),
      icon: <Flag />,
      tone: "warning" as const,
      note: t("review.flaggedNote"),
    },
    {
      id: "reviewed",
      label: t("review.reviewed"),
      value: num(decidedCount),
      icon: <BadgeCheck />,
      tone: "success" as const,
      note: fill(t("review.rejectedNote"), { n: num(summary.rejected) }),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("reviewTitle")} description={description} />

      {error && (
        <Alert
          tone="danger"
          title={t("review.loadFailed")}
          action={
            <Button variant="outline" size="sm" onClick={() => load()}>
              {t("retry")}
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {stats ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {stats.map(({ id, ...s }) => (
            <Stat key={id} {...s} />
          ))}
        </div>
      ) : (
        !error && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-hidden>
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-[74px] rounded-card" />
            ))}
          </div>
        )
      )}

      <Tabs<View>
        label={t("reviewTitle")}
        value={view}
        onChange={setView}
        items={[
          { value: "waiting", label: t("reviewTabWaiting"), icon: <Flag size={14} aria-hidden />, count: items?.length },
          { value: "decided", label: t("reviewTabDecided"), icon: <History size={14} aria-hidden /> },
        ]}
      />

      {view === "decided" && (
        <>
          {decidedError && (
            <Alert
              tone="danger"
              title={t("review.loadFailed")}
              action={
                <Button variant="outline" size="sm" onClick={() => loadDecided()}>
                  {t("retry")}
                </Button>
              }
            >
              {decidedError}
            </Alert>
          )}
          {decided === null && !decidedError && (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
              <ReviewListSkeleton />
              <ReviewDetailSkeleton />
            </div>
          )}
          {decided?.length === 0 && <EmptyState icon={<History />} title={t("reviewNothingDecided")} />}
          {selectedDecided && (
            <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
              <div className="space-y-4 xl:sticky xl:top-4">
                <DecidedList
                  items={decidedList}
                  selectedId={selectedDecided.fact.id}
                  onSelect={setDecidedId}
                  footer={<ShortcutsHint />}
                />
              </div>
              <ReviewDetail
                ref={detailRef}
                key={`${selectedDecided.fact.id}-${selectedDecided.decided_at}`}
                item={selectedDecided}
                earlier={selectedDecided}
                onDone={changed}
              />
            </div>
          )}
        </>
      )}

      {view === "waiting" && items === null && !error && (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <ReviewListSkeleton />
          <ReviewDetailSkeleton />
        </div>
      )}

      {view === "waiting" && items?.length === 0 && (
        <EmptyState icon={<CircleCheckBig />} title={t("nothingToReview")}>
          {decidedCount > 0 ? t("review.allDone") : null}
        </EmptyState>
      )}

      {view === "waiting" && items && items.length > 0 && (
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <div className="space-y-4 xl:sticky xl:top-4">
            <ReviewList
              items={visible}
              total={items.length}
              selectedId={selected?.fact.id ?? null}
              onSelect={setSelectedId}
              filters={<ReviewFilters items={items} value={filters} onChange={setFilters} />}
              footer={<ShortcutsHint />}
            />
          </div>
          {selected ? (
            <ReviewDetail ref={detailRef} key={selected.fact.id} item={selected} onDone={done} />
          ) : (
            <EmptyState title={t("review.noMatches")} />
          )}
        </div>
      )}
    </div>
  );
}
