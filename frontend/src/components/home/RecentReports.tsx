"use client";

import { ArrowRight, FileText } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import { listReports, type ReportRow } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";

const SHOWN = 5;

/** The five most recently changed reports the person can see. */
export default function RecentReports() {
  const { t, locale } = useT();
  const [rows, setRows] = useState<ReportRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      listReports().then(
        (all) => {
          const latest = [...all].sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, SHOWN);
          setRows(latest);
          setError(null);
        },
        (e: unknown) => setError(errorText(e)),
      ),
    [],
  );

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card className="flex h-full flex-col">
      <CardHeader
        icon={<FileText />}
        title={t("home.recentReports")}
        subtitle={t("home.recentReportsSub")}
        actions={
          <ButtonLink href="/reports" variant="ghost" size="sm">
            {t("home.viewAll")}
            <ArrowRight size={14} aria-hidden />
          </ButtonLink>
        }
      />
      {error && (
        <Alert
          tone="danger"
          className="mb-3"
          action={
            <Button size="sm" variant="danger-outline" onClick={() => void load()}>
              {t("dash.tryAgain")}
            </Button>
          }
        >
          {t("home.recentLoadFailed")} {error}
        </Alert>
      )}
      {!rows && !error && (
        <div role="status" aria-label={t("loading")} className="divide-y divide-line">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="flex items-center gap-4 py-3">
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/5" />
                <Skeleton className="h-3 w-2/5" />
              </div>
              <Skeleton className="h-5 w-20 rounded-full" />
            </div>
          ))}
        </div>
      )}
      {rows && rows.length === 0 && (
        <EmptyState compact className="flex-1" icon={<FileText />} title={t("home.noReports")}>
          {t("home.noReportsBody")}
        </EmptyState>
      )}
      {rows && rows.length > 0 && (
        <ul className="divide-y divide-line">
          {rows.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0 flex-1">
                <Link
                  href={`/reports/${r.id}`}
                  className="block truncate font-medium text-strong hover:text-brand hover:underline"
                >
                  {r.title}
                </Link>
                <p className="mt-0.5 text-xs text-muted">
                  {t(`reportType.${r.report_type}` as LabelKey)}
                  <span aria-hidden> · </span>
                  {r.due_date ? (
                    <>
                      {t("home.due")}: <span className="tabular-nums">{formatDate(r.due_date, locale)}</span>
                    </>
                  ) : (
                    t("home.noDue")
                  )}
                </p>
              </div>
              <StatusBadge kind="report" value={r.status} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
