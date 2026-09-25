"use client";

import { History, MessageSquareText } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import type { QaHistoryRow } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import { useT } from "@/lib/i18n";

/** The person's own past questions; choosing one reopens the saved answer. */
export default function RecentQuestions({
  rows,
  currentId,
  onOpen,
  disabled = false,
}: {
  rows: QaHistoryRow[] | null;
  currentId?: string;
  onOpen: (id: string) => void;
  /** True while an answer is being written or read, so a second one cannot race it. */
  disabled?: boolean;
}) {
  const { t, locale } = useT();
  return (
    <Card as="aside" aria-labelledby="recent-questions" className="lg:sticky lg:top-4">
      <CardHeader id="recent-questions" icon={<History />} title={t("qa.recent")} subtitle={t("ask.recentHelp")} />
      {rows === null ? (
        <div role="status" aria-label={t("loading")} className="space-y-3">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState compact icon={<MessageSquareText />} title={t("qa.noHistory")} />
      ) : (
        <ul className="-mx-2 max-h-[60vh] overflow-y-auto scroll-quiet space-y-1">
          {rows.map((h) => {
            const current = h.id === currentId;
            return (
              <li key={h.id}>
                <button
                  type="button"
                  onClick={() => onOpen(h.id)}
                  disabled={disabled}
                  aria-current={current ? "true" : undefined}
                  className={cn(
                    "block w-full rounded-panel px-3 py-2.5 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-60",
                    current ? "bg-brand-soft" : "enabled:hover:bg-surface-hover",
                  )}
                >
                  <span className={cn("line-clamp-2 text-sm font-medium", current ? "text-brand" : "text-strong")}>
                    {h.question}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <time dateTime={h.created_at}>{formatDateTime(h.created_at, locale)}</time>
                    {h.grounded === false && <StatusBadge kind="confidence" value="low" />}
                    {current && <span className="sr-only">({t("ask.openedNow")})</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
