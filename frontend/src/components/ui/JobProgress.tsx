"use client";

import { Check } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

import Spinner from "./Spinner";

/** Seconds since `since` (a Date.now() value), ticking every second while mounted. */
export function useElapsed(since: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (since === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [since]);
  return since === null ? 0 : Math.max(0, Math.floor((now - since) / 1000));
}

export function ElapsedTime({ seconds }: { seconds: number }) {
  const { t } = useT();
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return (
    <span className="tabular-nums">
      {m > 0 ? `${m} ${t("ui.minutes")} ` : ""}
      {s} {t("ui.seconds")}
    </span>
  );
}

type JobProgressProps = {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Steps shown in order. Steps before `current` are done; the job has no step events, so
   * `current` usually advances with time (see advanceByTime). */
  steps?: React.ReactNode[];
  current?: number;
  startedAt: number;
  className?: string;
};

/**
 * Progress for a job that takes minutes (drafting a reply, a report). Shows what is
 * happening, how long it has run, and that leaving is safe once the server has the job.
 */
export default function JobProgress({ title, description, steps, current = 0, startedAt, className }: JobProgressProps) {
  const { t } = useT();
  const elapsed = useElapsed(startedAt);
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("rounded-card border border-info-border bg-info-bg/60 p-5", className)}
    >
      <div className="flex items-start gap-3">
        <Spinner size={20} className="mt-0.5 text-brand" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-strong">{title}</p>
          {description && <p className="mt-1 text-sm text-muted">{description}</p>}
        </div>
        <span className="shrink-0 rounded-full bg-surface px-3 py-1 text-xs font-medium text-muted shadow-pill">
          {t("ui.elapsed")}: <ElapsedTime seconds={elapsed} />
        </span>
      </div>
      {steps && steps.length > 0 && (
        <ol className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => {
            const state = i < current ? "done" : i === current ? "active" : "todo";
            return (
              <li
                key={i}
                aria-current={state === "active" ? "step" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-control border bg-surface px-3 py-2 text-xs",
                  state === "active" ? "border-brand text-strong" : "border-line text-muted",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold",
                    state === "done" && "bg-success text-white",
                    state === "active" && "bg-brand text-white",
                    state === "todo" && "bg-surface-sunken text-muted",
                  )}
                >
                  {state === "done" ? <Check size={12} /> : i + 1}
                </span>
                <span className="min-w-0">{s}</span>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

/** Which step a time-based stepper is on: moves one step every `secondsPerStep`, never past the last. */
export function advanceByTime(elapsedSeconds: number, stepCount: number, secondsPerStep: number): number {
  return Math.min(stepCount - 1, Math.floor(elapsedSeconds / secondsPerStep));
}
