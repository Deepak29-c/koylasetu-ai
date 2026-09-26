"use client";

import { useEffect, useRef } from "react";

import Badge from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import type { ReviewItem } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

import { fill, useFigureText } from "./figureText";

/** The queue on the left: one compact card per flagged figure. */
export default function ReviewList({
  items,
  total,
  selectedId,
  onSelect,
  filters,
  footer,
}: {
  items: ReviewItem[];
  /** Items loaded before filtering, for "n of m". */
  total: number;
  selectedId: string | null;
  onSelect: (factId: string) => void;
  filters?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const { t } = useT();
  const fx = useFigureText();
  const listRef = useRef<HTMLUListElement>(null);

  // Keep the selected card in view when the selection moves by keyboard or after a decision.
  useEffect(() => {
    if (!selectedId) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-fact="${CSS.escape(selectedId)}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  return (
    <Card padded={false} className="flex flex-col xl:min-h-0 xl:flex-1">
      <div className="space-y-3 border-b border-line p-4">
        <CardHeader
          className="mb-0"
          title={t("review.listTitle")}
          actions={
            <span className="text-xs font-medium text-muted tabular-nums">
              {fill(t("review.countOf"), { n: items.length, m: total })}
            </span>
          }
        />
        {filters}
      </div>
      {items.length === 0 ? (
        <div className="p-4">
          <EmptyState compact title={t("review.noMatches")} />
        </div>
      ) : (
        <ul ref={listRef} aria-label={t("review.listTitle")} className="scroll-quiet max-h-[40vh] space-y-2 overflow-y-auto p-3 xl:max-h-none xl:min-h-0 xl:flex-1">
          {items.map((item) => {
            const f = item.fact;
            const active = f.id === selectedId;
            return (
              <li key={f.id} data-fact={f.id}>
                <button
                  type="button"
                  onClick={() => onSelect(f.id)}
                  aria-current={active ? "true" : undefined}
                  className={cn(
                    "block w-full rounded-panel border p-3 text-left transition-colors",
                    active
                      ? "border-brand bg-brand-tint ring-2 ring-brand/20"
                      : "border-line bg-surface hover:border-brand/40 hover:bg-brand-tint",
                  )}
                >
                  <span className="flex flex-wrap items-center gap-1.5">
                    <StatusBadge kind="severity" value={item.worst_severity} />
                    {item.issues.map((i) => (
                      <Badge key={i.id} tone="neutral" className="font-mono" title={fx.ruleLabel(i.rule_code)}>
                        {i.rule_code}
                      </Badge>
                    ))}
                  </span>
                  <span className="mt-2 block text-sm font-medium text-strong">
                    {f.label || fx.metricLabel(f.metric)}
                  </span>
                  <span className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-xs text-muted">
                    <span className="text-sm font-semibold text-strong tabular-nums">{fx.printed(f)}</span>
                    {f.label && <span>{fx.metricLabel(f.metric)}</span>}
                  </span>
                  <span className="mt-1 block truncate text-xs text-subtle">
                    {fx.pageRef(item.document_title, f.page_no)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {/* On a short wide screen the list needs the room more than the hint does */}
      {footer && <div className="border-t border-line px-4 py-3 xl:[@media(max-height:1000px)]:hidden">{footer}</div>}
    </Card>
  );
}

export function ReviewListSkeleton() {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="rounded-card border border-line bg-surface p-4 shadow-card">
      <Skeleton className="h-5 w-40" />
      <Skeleton className="mt-3 h-9 w-full rounded-full" />
      <div className="mt-4 space-y-2">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="space-y-2 rounded-panel border border-line p-3">
            <Skeleton className="h-5 w-24 rounded-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** A small legend of the queue's keyboard shortcuts. */
export function ShortcutsHint() {
  const { t } = useT();
  const kbd = "rounded border border-line-strong bg-surface-subtle px-1.5 font-mono text-[11px] text-strong";
  const rows: [string[], string][] = [
    [["j", "k"], t("review.keyMove")],
    [["a"], t("review.keyAccept")],
    [["e"], t("review.keyCorrect")],
    [["r"], t("review.keyReject")],
  ];
  return (
    <div className="text-xs text-muted">
      <p className="font-semibold text-strong">{t("review.shortcuts")}</p>
      <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
        {rows.map(([keys, label]) => (
          <li key={keys.join("")} className="flex items-center gap-1">
            {keys.map((k) => (
              <kbd key={k} className={kbd}>
                {k}
              </kbd>
            ))}
            <span>{label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
