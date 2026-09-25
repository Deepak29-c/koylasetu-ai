"use client";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

/** A shimmering placeholder in the shape of the content it replaces. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-shimmer rounded-control bg-[linear-gradient(90deg,var(--surface-sunken)_0%,var(--surface-subtle)_50%,var(--surface-sunken)_100%)] bg-[length:200%_100%]",
        className,
      )}
    />
  );
}

/** Rows of a table while it loads. */
export function TableSkeleton({ rows = 6, columns = 5 }: { rows?: number; columns?: number }) {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="space-y-2 p-4">
      <Skeleton className="h-9 w-full rounded-full" />
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex gap-4 px-3 py-2.5">
          {Array.from({ length: columns }, (_, c) => (
            <Skeleton key={c} className={cn("h-4", c === 0 ? "w-2/5" : "flex-1")} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** A block of cards or text lines while a page loads. */
export function PageSkeleton({ cards = 3 }: { cards?: number }) {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96 max-w-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: cards }, (_, i) => (
          <Skeleton key={i} className="h-28 rounded-card" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-card" />
    </div>
  );
}
