"use client";

import { Activity, Files, HardDrive, Lock, RefreshCw, Settings2, Sparkles, Workflow } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { labelOr } from "@/components/admin/labels";
import { useMe } from "@/components/AppShell";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import RecordList, { MonoId } from "@/components/ui/RecordList";
import { Skeleton } from "@/components/ui/Skeleton";
import Stat from "@/components/ui/Stat";
import StatusBadge from "@/components/ui/StatusBadge";
import { TD, TH, THead, TR, Table, TableFrame } from "@/components/ui/Table";
import type { DocumentStatus } from "@/lib/api";
import { getSystemStatus, type HealthCheck, type SystemStatus } from "@/lib/api-admin";
import { errorText } from "@/lib/errors";
import { formatDateTime, formatNumber } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { DOCUMENT_STATUS } from "@/lib/status";

const REFRESH_MS = 30_000;
const DOCUMENT_ORDER: DocumentStatus[] = ["UPLOADED", "PROCESSING", "PROCESSED", "NEEDS_REVIEW", "FAILED"];
const ALERT_TONE = { ok: "success", warn: "warning", error: "danger" } as const;

function gigabytes(bytes: number, locale: string): string {
  return `${(bytes / 1024 ** 3).toLocaleString(locale, { maximumFractionDigits: 1 })} GB`;
}

export default function AdminStatusPage() {
  const me = useMe();
  const { t, locale } = useT();
  const allowed = can(me, "manage_admin");
  const [data, setData] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const busy = useRef(false);

  const load = useCallback(() => {
    if (busy.current) return Promise.resolve();
    busy.current = true;
    setLoading(true);
    return getSystemStatus()
      .then(
        (s) => {
          setData(s);
          setError(null);
        },
        (e: unknown) => setError(e),
      )
      .finally(() => {
        busy.current = false;
        setLoading(false);
      });
  }, []);

  // First load, then every 30 s while the tab is visible; coming back to the tab refreshes at once.
  useEffect(() => {
    if (!allowed) return;
    void load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, REFRESH_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [allowed, load]);

  if (!allowed)
    return (
      <>
        <PageHeader title={t("adminStatus.title")} breadcrumbs={[{ label: t("nav.admin") }]} />
        <EmptyState icon={<Lock />} title={t("noPermission")} />
      </>
    );

  return (
    <>
      <PageHeader
        title={t("adminStatus.title")}
        description={t("adminStatus.description")}
        breadcrumbs={[{ label: t("nav.admin") }]}
        meta={data && <StatusBadge kind="health" value={data.overall} size="md" />}
        actions={
          <Button variant="secondary" icon={<RefreshCw size={16} aria-hidden />} loading={loading} onClick={load}>
            {t("adminStatus.refresh")}
          </Button>
        }
      />
      <div className="space-y-6">
        {error !== null && (
          <Alert
            tone="danger"
            title={t("adminStatus.loadFailed")}
            action={
              <Button variant="danger-outline" size="sm" loading={loading} onClick={load}>
                {t("retry")}
              </Button>
            }
          >
            {errorText(error, t)}
          </Alert>
        )}

        {!data && error === null && <StatusSkeleton />}

        {data && (
          <>
            <Alert tone={ALERT_TONE[data.overall]} title={t(`adminStatus.overall.${data.overall}` as LabelKey)}>
              <span aria-live="polite">
                {t("adminStatus.lastChecked")}: {formatDateTime(data.checked_at, locale)} · {t("adminStatus.version")}{" "}
                {data.version}
              </span>
            </Alert>

            <section aria-labelledby="checks-heading" className="space-y-3">
              <h2 id="checks-heading" className="text-base font-semibold text-strong">
                {t("adminStatus.checks")}
              </h2>
              <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {data.checks.map((c) => (
                  <CheckTile key={c.key} check={c} />
                ))}
              </ul>
            </section>

            <div className="grid gap-6 lg:grid-cols-2">
              <QueuesCard data={data} />
              <Card>
                <CardHeader icon={<Sparkles />} title={t("adminStatus.models")} />
                <RecordList
                  items={data.models.map((m) => ({
                    label: t(`adminStatus.role.${m.role}` as LabelKey),
                    value: (
                      <span className="flex flex-wrap items-center gap-2">
                        <MonoId>{m.name}</MonoId>
                        <Badge tone={m.pulled === null ? "neutral" : m.pulled ? "success" : "warning"} dot>
                          {m.pulled === null
                            ? t("adminStatus.unknown")
                            : m.pulled
                              ? t("adminStatus.pulled")
                              : t("adminStatus.notPulled")}
                        </Badge>
                      </span>
                    ),
                  }))}
                />
              </Card>
              <Card>
                <CardHeader icon={<HardDrive />} title={t("adminStatus.storage")} />
                <RecordList
                  columns={2}
                  items={[
                    { label: t("adminStatus.free"), value: data.storage && gigabytes(data.storage.free_bytes, locale) },
                    { label: t("adminStatus.total"), value: data.storage && gigabytes(data.storage.total_bytes, locale) },
                    { label: t("adminStatus.folder"), value: data.storage?.path, mono: true, wide: true },
                  ]}
                />
              </Card>
              <Card>
                <CardHeader icon={<Settings2 />} title={t("adminStatus.settings")} />
                <RecordList
                  items={(["ingest_inline", "allow_external_calls"] as const).map((flag) => ({
                    label: t(`adminStatus.flag.${flag}`),
                    value: data.flags[flag] ? t("adminStatus.yes") : t("adminStatus.no"),
                  }))}
                />
              </Card>
            </div>

            {data.documents && (
              <section aria-labelledby="documents-heading" className="space-y-3">
                <h2 id="documents-heading" className="text-base font-semibold text-strong">
                  {t("adminStatus.documents")}
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                  {DOCUMENT_ORDER.map((s) => (
                    <Stat
                      key={s}
                      label={t(DOCUMENT_STATUS[s].label)}
                      value={formatNumber(data.documents?.[s] ?? 0, locale)}
                      tone={DOCUMENT_STATUS[s].tone}
                      icon={<Files />}
                      href={can(me, "view_processing") ? "/documents" : undefined}
                    />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </>
  );
}

function CheckTile({ check }: { check: HealthCheck }) {
  const { t } = useT();
  const outcome = labelOr(
    t,
    check.code === "check_failed" ? "adminStatus.code.check_failed" : `adminStatus.code.${check.key}.${check.code}`,
    check.code,
  );
  return (
    <li className="flex flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold text-strong">
          {labelOr(t, `adminStatus.check.${check.key}`, check.key)}
        </h3>
        <StatusBadge kind="health" value={check.status} />
      </div>
      <p className="text-sm text-foreground">{outcome}</p>
      <p className="text-xs break-words text-muted">
        <span className="sr-only">{t("adminStatus.detail")}: </span>
        {check.message}
      </p>
    </li>
  );
}

function QueuesCard({ data }: { data: SystemStatus }) {
  const { t, locale } = useT();
  return (
    <Card padded={false}>
      <div className="px-5 pt-5 sm:px-6 sm:pt-6">
        <CardHeader
          icon={<Workflow />}
          title={t("adminStatus.queues")}
          actions={
            data.workers !== null && (
              <Badge tone={data.workers ? "success" : "danger"} dot>
                {t("adminStatus.workers")}: {formatNumber(data.workers, locale)}
              </Badge>
            )
          }
        />
      </div>
      {data.queues ? (
        <TableFrame className="rounded-none border-0 shadow-none">
          <Table caption={t("adminStatus.queues")}>
            <THead>
              <TH>{t("adminStatus.colQueue")}</TH>
              <TH align="right">{t("adminStatus.colQueued")}</TH>
              <TH align="right">{t("adminStatus.colFailed")}</TH>
            </THead>
            <tbody>
              {data.queues.map((q) => (
                <TR key={q.name}>
                  <TD>
                    <span className="text-strong">{labelOr(t, `adminStatus.queue.${q.name}`, q.name)}</span>{" "}
                    <MonoId>{q.name}</MonoId>
                  </TD>
                  <TD align="right">{formatNumber(q.queued, locale)}</TD>
                  <TD align="right">
                    {q.failed ? (
                      <Badge tone="danger" dot>
                        {formatNumber(q.failed, locale)}
                      </Badge>
                    ) : (
                      formatNumber(q.failed, locale)
                    )}
                  </TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </TableFrame>
      ) : (
        <div className="px-5 pb-5 sm:px-6 sm:pb-6">
          <EmptyState compact icon={<Activity />} title={t("adminStatus.queuesOff")} />
        </div>
      )}
    </Card>
  );
}

function StatusSkeleton() {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="space-y-6">
      <Skeleton className="h-14 rounded-panel" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }, (_, i) => (
          <Skeleton key={i} className="h-28 rounded-card" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-48 rounded-card" />
        ))}
      </div>
    </div>
  );
}
