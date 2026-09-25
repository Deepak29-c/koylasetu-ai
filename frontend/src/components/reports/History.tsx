"use client";

import { CircleCheck, CornerUpLeft, Download, FilePlus, Send } from "lucide-react";

import { cn } from "@/lib/cn";
import type { ReportRow, ReportVersionRow } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";

import { timeline, type TimelineEvent } from "./content";
import { versionLine } from "@/lib/reportView";

const ICONS: Record<TimelineEvent["kind"], typeof Send> = {
  created: FilePlus,
  submitted: Send,
  returned: CornerUpLeft,
  approved: CircleCheck,
  exported: Download,
};

const TONES: Record<TimelineEvent["kind"], string> = {
  created: "bg-neutral-bg text-neutral-fg",
  submitted: "bg-info-bg text-info-fg",
  returned: "bg-warning-bg text-warning-fg",
  approved: "bg-success-bg text-success-fg",
  exported: "bg-brand-soft text-brand",
};

/** Where the report has been: created, sent for approval, returned or approved, downloaded. */
export function StatusTimeline({ report, versions }: { report: ReportRow; versions: ReportVersionRow[] }) {
  const { t, locale } = useT();
  const events = timeline(report, versions);
  const next: LabelKey | null =
    report.status === "DRAFT" || report.status === "RETURNED"
      ? "reports.nextSubmit"
      : report.status === "IN_REVIEW"
        ? "reports.nextApproval"
        : null;
  return (
    <ol className="space-y-0">
      {events.map((e, i) => {
        const Icon = ICONS[e.kind];
        return (
          <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
            {(i < events.length - 1 || next) && (
              <span aria-hidden className="absolute top-8 bottom-0 left-[15px] w-px bg-line" />
            )}
            <span aria-hidden className={cn("grid size-8 shrink-0 place-items-center rounded-full", TONES[e.kind])}>
              <Icon size={16} />
            </span>
            <div className="min-w-0 flex-1 pt-1">
              <p className="text-sm font-medium text-strong">{t(`reports.event.${e.kind}` as LabelKey)}</p>
              <p className="text-xs text-muted">
                {e.by && (
                  <>
                    {e.by}
                    <span aria-hidden> · </span>
                  </>
                )}
                <span className="tabular-nums">{formatDateTime(e.at, locale)}</span>
              </p>
              {e.note && <p className="mt-1 rounded-control bg-surface-subtle px-2.5 py-1.5 text-xs break-words text-foreground">{e.note}</p>}
            </div>
          </li>
        );
      })}
      {next && (
        <li className="flex gap-3">
          <span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-full border border-dashed border-line-strong" />
          <p className="pt-1.5 text-sm text-muted">
            <span className="sr-only">{t("reports.nextStep")}: </span>
            {t(next)}
          </p>
        </li>
      )}
    </ol>
  );
}

/** Every saved version, newest first. */
export function VersionList({ versions }: { versions: ReportVersionRow[] }) {
  const { t, locale } = useT();
  const sorted = [...versions].sort((a, b) => b.version - a.version);
  if (!sorted.length) return <p className="text-sm text-muted">{t("reports.noVersions")}</p>;
  return (
    <ol className="divide-y divide-line">
      {sorted.map((v) => (
        <li key={v.version} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
          <span className="mt-0.5 shrink-0 rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-[12px] text-muted">
            v{v.version}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm break-words text-strong">
              {/* System words in the reader's language; a person's comment exactly as typed. */}
              {(() => {
                const line = versionLine(v);
                const what = line.kind ? t(`versionKind.${line.kind}` as LabelKey) : (line.fallback ?? t("reports.edited"));
                return line.comment ? (
                  <>
                    {what}: <q className="whitespace-pre-wrap">{line.comment}</q>
                  </>
                ) : (
                  what
                );
              })()}
            </p>
            <p className="text-xs text-muted">
              {v.editor.name}
              <span aria-hidden> · </span>
              <span className="tabular-nums">{formatDateTime(v.created_at, locale)}</span>
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
