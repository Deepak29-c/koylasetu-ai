"use client";

import { ArrowRight, CalendarDays, Inbox, Send } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import { lastEditor } from "@/components/reports/content";
import DueBadge from "@/components/reports/DueBadge";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { listReports, listReportVersions, type ReportRow } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatDate, formatDateTime } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

type Waiting = { report: ReportRow; submittedBy: string | null };

/** Earliest due date first (undated last), then the one waiting longest. */
function byUrgency(a: Waiting, b: Waiting): number {
  const x = a.report.due_date;
  const y = b.report.due_date;
  if (x !== y) {
    if (!x) return 1;
    if (!y) return -1;
    return x.localeCompare(y);
  }
  return a.report.updated_at.localeCompare(b.report.updated_at);
}

export default function ApprovalsPage() {
  const me = useMe();
  const { t, locale } = useT();
  const allowed = can(me, "approve_reports");
  const [items, setItems] = useState<Waiting[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      listReports({ status: "IN_REVIEW" })
        .then(async (reports) => {
          // The list has no names; the last save before submitting says who sent it.
          const who = await Promise.allSettled(reports.map((r) => listReportVersions(r.id)));
          return reports.map((report, i): Waiting => {
            const v = who[i];
            return { report, submittedBy: v.status === "fulfilled" ? (lastEditor(v.value)?.editor.name ?? null) : null };
          });
        })
        .then(
          (rows) => {
            setItems(rows.sort(byUrgency));
            setError(null);
          },
          (e: unknown) => setError(errorText(e)),
        ),
    [],
  );

  useEffect(() => {
    if (allowed) void load();
  }, [allowed, load]);

  if (!allowed)
    return (
      <>
        <PageHeader title={t("nav.approvals")} />
        <EmptyState title={t("noPermission")} />
      </>
    );

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("nav.approvals")}
        description={t("approvals.description")}
        meta={items && items.length > 0 ? <Badge tone="info">{items.length}</Badge> : undefined}
      />

      {error && (
        <Alert
          tone="danger"
          action={
            <Button size="sm" variant="danger-outline" onClick={() => void load()}>
              {t("retry")}
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {!items && !error && (
        <div role="status" aria-label={t("loading")} className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-40 rounded-card" />
          ))}
        </div>
      )}

      {items && items.length === 0 && (
        <EmptyState icon={<Inbox />} title={t("approvals.empty")}>
          {t("approvals.emptyBody")}
        </EmptyState>
      )}

      {items && items.length > 0 && (
        <ul className="grid max-h-[70vh] gap-4 overflow-y-auto scroll-quiet p-0.5 md:grid-cols-2">
          {items.map(({ report: r, submittedBy }) => (
            <li key={r.id}>
              <Card as="article" className="flex h-full flex-col gap-4">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="brand">{t(`reportType.${r.report_type}` as LabelKey)}</Badge>
                    <DueBadge report={r} />
                  </div>
                  <h2 className="text-base leading-6 font-semibold break-words text-strong">{r.title}</h2>
                </div>
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <div className="flex items-start gap-2">
                    <Send size={16} aria-hidden className="mt-0.5 shrink-0 text-subtle" />
                    <div className="min-w-0">
                      <dt className="text-xs text-muted">{t("approvals.submitted")}</dt>
                      <dd className="text-strong">
                        {submittedBy ?? "–"}
                        <span className="block text-xs text-muted tabular-nums">{formatDateTime(r.updated_at, locale)}</span>
                      </dd>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <CalendarDays size={16} aria-hidden className="mt-0.5 shrink-0 text-subtle" />
                    <div className="min-w-0">
                      <dt className="text-xs text-muted">{t("reports.dueColumn")}</dt>
                      <dd className="text-strong tabular-nums">
                        {r.due_date ? formatDate(r.due_date, locale) : t("home.noDue")}
                      </dd>
                    </div>
                  </div>
                </dl>
                <div className="mt-auto flex justify-end">
                  <ButtonLink href={`/reports/${r.id}`} variant="primary" aria-label={`${t("review")}: ${r.title}`}>
                    {t("review")}
                    <ArrowRight size={16} aria-hidden />
                  </ButtonLink>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
