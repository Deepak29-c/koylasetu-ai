"use client";

import { ChevronLeft, ChevronRight, Download, FileSearch, ScrollText } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import AuditDetailsDrawer from "@/components/admin/AuditDetailsDrawer";
import {
  actionLabel,
  actionTone,
  buildAuditCsv,
  downloadCsv,
  entityHref,
  entityLabel,
  todayStamp,
} from "@/components/admin/audit";
import { useMe } from "@/components/AppShell";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Field, Input, Select } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { MonoId } from "@/components/ui/RecordList";
import { TableSkeleton } from "@/components/ui/Skeleton";
import { TD, TH, THead, TR, Table, TableFrame, TableToolbar } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import {
  AUDIT_PAGE_SIZE,
  type AuditFilters,
  type AuditLogRow,
  listAuditActions,
  listAuditLog,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { useT } from "@/lib/i18n";

const EMAIL_DEBOUNCE_MS = 400;

export default function AuditLogPage() {
  const me = useMe();
  const { t, locale } = useT();
  const toast = useToast();
  const allowed = me.permissions.includes("view_audit");

  const [rows, setRows] = useState<AuditLogRow[] | null>(null);
  const [actions, setActions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<AuditFilters>({});
  const [emailInput, setEmailInput] = useState("");
  const [open, setOpen] = useState<AuditLogRow | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Each request gets a number; a response that is not the latest one is dropped, so a
  // slow earlier search cannot overwrite the results of a later one.
  const requestSeq = useRef(0);

  const load = useCallback((f: AuditFilters, from: number) => {
    const seq = ++requestSeq.current;
    return listAuditLog(f, from).then(
      (page) => {
        if (seq !== requestSeq.current) return;
        setRows(page.rows);
        setHasMore(page.hasMore);
        setOffset(from);
        setError(null);
        setRefreshing(false);
      },
      (e: unknown) => {
        if (seq !== requestSeq.current) return;
        setError(errorText(e));
        setRefreshing(false);
      },
    );
  }, []);

  useEffect(() => {
    if (!allowed) return;
    listAuditActions().then(setActions, () => {});
    load({}, 0);
  }, [allowed, load]);

  /** Loads again while the rows already on screen stay visible (dimmed). */
  const reload = useCallback(
    (f: AuditFilters, from: number) => {
      setRefreshing(true);
      return load(f, from);
    },
    [load],
  );

  const applyFilters = useCallback(
    (next: AuditFilters) => {
      setFilters(next);
      // A new filter starts a new list; page 3 of the old one is meaningless.
      reload(next, 0);
    },
    [reload],
  );

  // The email box searches as the person types, once they pause.
  useEffect(() => {
    const value = emailInput.trim() || undefined;
    if (value === filters.user_email) return;
    const id = window.setTimeout(() => applyFilters({ ...filters, user_email: value }), EMAIL_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [emailInput, filters, applyFilters]);

  if (!allowed) {
    return (
      <>
        <PageHeader title={t("auditLog")} />
        <Alert tone="warning">{t("noPermission")}</Alert>
      </>
    );
  }

  function goTo(from: number) {
    setOpen(null);
    reload(filters, from);
    window.scrollTo({ top: 0 });
  }

  function clearFilters() {
    setEmailInput("");
    applyFilters({});
  }

  function exportCsv() {
    if (!rows?.length) return;
    downloadCsv(buildAuditCsv(rows, t), `audit-log-${todayStamp()}.csv`);
    toast({ title: t("audit.exportedToast"), body: t("audit.exportedBody") });
  }

  const hasFilters = Object.values(filters).some(Boolean) || emailInput.trim() !== "";
  const dateRangeInvalid = !!(filters.from_date && filters.to_date && filters.from_date > filters.to_date);
  const page = Math.floor(offset / AUDIT_PAGE_SIZE) + 1;

  const clearButton = (
    <Button variant="outline" size="sm" onClick={clearFilters}>
      {t("auditClearFilters")}
    </Button>
  );

  return (
    <div className="space-y-6">
      <PageHeader title={t("auditLog")} description={t("audit.description")} />

      <Card>
        <CardHeader
          title={t("audit.filtersTitle")}
          actions={hasFilters ? clearButton : undefined}
          className="mb-3"
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label={t("auditFilterAction")}>
            <Select
              value={filters.action ?? ""}
              onChange={(e) => applyFilters({ ...filters, action: e.target.value || undefined })}
            >
              <option value="">{t("auditAllActions")}</option>
              {actions.map((a) => (
                <option key={a} value={a}>
                  {actionLabel(t, a)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("auditFilterUser")}>
            <Input
              type="search"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder={t("audit.userPlaceholder")}
              autoComplete="off"
            />
          </Field>
          <Field label={t("auditFilterFrom")}>
            <Input
              type="date"
              value={filters.from_date ?? ""}
              max={filters.to_date}
              onChange={(e) => applyFilters({ ...filters, from_date: e.target.value || undefined })}
            />
          </Field>
          <Field label={t("auditFilterTo")} error={dateRangeInvalid ? t("audit.dateRangeInvalid") : undefined}>
            <Input
              type="date"
              value={filters.to_date ?? ""}
              min={filters.from_date}
              onChange={(e) => applyFilters({ ...filters, to_date: e.target.value || undefined })}
            />
          </Field>
        </div>
      </Card>

      {error && (
        <Alert
          tone="danger"
          action={
            <Button variant="outline" size="sm" onClick={() => reload(filters, offset)}>
              {t("retry")}
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      <TableFrame>
        <TableToolbar
          title={t("audit.entriesTitle")}
          count={rows?.length}
          actions={
            <Button
              variant="outline"
              size="sm"
              icon={<Download size={16} aria-hidden />}
              onClick={exportCsv}
              disabled={!rows?.length}
            >
              {t("audit.exportCsv")}
            </Button>
          }
        />

        {rows === null ? (
          error ? null : (
            <TableSkeleton rows={8} columns={6} />
          )
        ) : rows.length === 0 ? (
          <div className="px-5 pb-5">
            <EmptyState
              compact
              icon={hasFilters ? <FileSearch /> : <ScrollText />}
              title={hasFilters ? t("auditNoResults") : t("audit.noEntriesYet")}
              action={hasFilters ? clearButton : undefined}
            >
              {hasFilters ? t("audit.noResultsBody") : undefined}
            </EmptyState>
          </div>
        ) : (
          <div aria-busy={refreshing || undefined} className={refreshing ? "opacity-60 transition-opacity" : undefined}>
            <div className="hidden sm:block">
              <Table caption={t("auditLog")} maxHeight="none">
                <THead>
                  <TH>{t("auditWhen")}</TH>
                  <TH>{t("auditWho")}</TH>
                  <TH>{t("auditAction")}</TH>
                  <TH>{t("auditWhat")}</TH>
                  <TH>{t("auditIp")}</TH>
                  <TH align="right">
                    <span className="sr-only">{t("auditDetails")}</span>
                  </TH>
                </THead>
                <tbody>
                  {rows.map((r) => {
                    const href = entityHref(r);
                    const entityText = r.entity ? entityLabel(t, r.entity) : null;
                    return (
                      <TR key={r.id} selected={open?.id === r.id}>
                        <TD className="whitespace-nowrap tabular-nums text-muted">
                          {formatDateTime(r.created_at, locale)}
                        </TD>
                        <TD>
                          {r.user ? (
                            <>
                              <span className="block font-medium text-strong">{r.user.name}</span>
                              <span className="block text-xs text-subtle">{r.user.email}</span>
                            </>
                          ) : (
                            <span className="text-subtle">{t("auditSystem")}</span>
                          )}
                        </TD>
                        <TD>
                          <Badge tone={actionTone(r.action)} dot title={r.action}>
                            {actionLabel(t, r.action)}
                          </Badge>
                        </TD>
                        <TD>
                          {entityText ? (
                            <span className="inline-flex flex-wrap items-center gap-2">
                              {href ? (
                                <Link href={href} className="font-medium text-brand hover:underline">
                                  {entityText}
                                </Link>
                              ) : (
                                <span>{entityText}</span>
                              )}
                              {r.entity_id && <MonoId>{r.entity_id.slice(0, 8)}</MonoId>}
                            </span>
                          ) : (
                            <span className="text-subtle">–</span>
                          )}
                        </TD>
                        <TD>{r.ip ? <MonoId>{r.ip}</MonoId> : <span className="text-subtle">–</span>}</TD>
                        <TD align="right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setOpen(r)}
                            aria-label={`${t("audit.viewDetails")}: ${actionLabel(t, r.action)}, ${formatDateTime(r.created_at, locale)}`}
                          >
                            {t("auditDetails")}
                          </Button>
                        </TD>
                      </TR>
                    );
                  })}
                </tbody>
              </Table>
            </div>

            <ul className="divide-y divide-line border-t border-line sm:hidden">
              {rows.map((r) => {
                const href = entityHref(r);
                const entityText = r.entity ? entityLabel(t, r.entity) : null;
                return (
                  <li key={r.id} className={cn("space-y-2 px-5 py-4", open?.id === r.id && "bg-brand-tint")}>
                    <div className="flex items-start justify-between gap-3">
                      <Badge tone={actionTone(r.action)} dot title={r.action}>
                        {actionLabel(t, r.action)}
                      </Badge>
                      <span className="text-xs whitespace-nowrap text-muted tabular-nums">
                        {formatDateTime(r.created_at, locale)}
                      </span>
                    </div>
                    <div className="min-w-0 text-sm">
                      {r.user ? (
                        <>
                          <span className="block font-medium text-strong">{r.user.name}</span>
                          <span className="block truncate text-xs text-subtle">{r.user.email}</span>
                        </>
                      ) : (
                        <span className="text-subtle">{t("auditSystem")}</span>
                      )}
                    </div>
                    {entityText && (
                      <div className="flex flex-wrap items-center gap-2 text-sm">
                        {href ? (
                          <Link href={href} className="font-medium text-brand hover:underline">
                            {entityText}
                          </Link>
                        ) : (
                          <span>{entityText}</span>
                        )}
                        {r.entity_id && <MonoId>{r.entity_id.slice(0, 8)}</MonoId>}
                      </div>
                    )}
                    <div className="flex items-center justify-between gap-3">
                      {r.ip ? <MonoId>{r.ip}</MonoId> : <span />}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setOpen(r)}
                        aria-label={`${t("audit.viewDetails")}: ${actionLabel(t, r.action)}, ${formatDateTime(r.created_at, locale)}`}
                      >
                        {t("auditDetails")}
                      </Button>
                    </div>
                  </li>
                );
              })}
            </ul>
            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-line px-5 py-3 text-xs text-muted">
              {hasMore && <span className="mr-auto text-subtle">{t("audit.moreAvailable")}</span>}
              <span aria-live="polite" className="tabular-nums">
                {t("audit.showing")} {offset + 1}–{offset + rows.length}
              </span>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="icon-sm"
                  onClick={() => goTo(Math.max(0, offset - AUDIT_PAGE_SIZE))}
                  disabled={offset === 0 || refreshing}
                  aria-label={t("ui.previousPage")}
                  icon={<ChevronLeft size={16} aria-hidden />}
                />
                <span className="min-w-16 text-center tabular-nums">
                  {t("audit.page")} {page}
                </span>
                <Button
                  variant="outline"
                  size="icon-sm"
                  onClick={() => goTo(offset + AUDIT_PAGE_SIZE)}
                  disabled={!hasMore || refreshing}
                  aria-label={t("ui.nextPage")}
                  icon={<ChevronRight size={16} aria-hidden />}
                />
              </div>
            </div>
          </div>
        )}
      </TableFrame>

      {open && <AuditDetailsDrawer row={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
