"use client";

import { CalendarDays, FilePlus, FileText, Landmark, NotebookPen } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { useMe } from "@/components/AppShell";
import DueBadge, { dueState } from "@/components/reports/DueBadge";
import NewReportDrawer, { REPORT_TYPES } from "@/components/reports/NewReportDrawer";
import Alert from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Checkbox, Select } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { TableSkeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  Pagination,
  SearchInput,
  Table,
  TableFrame,
  TableToolbar,
  TD,
  TH,
  THead,
  TR,
  usePaged,
  useSort,
} from "@/components/ui/Table";
import Tabs from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { exportReport, getReport, listReports, type ReportRow, type ReportStatus } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatDate, formatDateTime } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { can, canSeeReports } from "@/lib/permissions";

const STATUSES: ReportStatus[] = ["DRAFT", "IN_REVIEW", "RETURNED", "APPROVED", "EXPORTED"];
type DueFilter = "" | "soon" | "overdue";
type SortKey = "title" | "type" | "status" | "due" | "created";

function pick<T extends string>(value: string | null, allowed: readonly T[]): T | "" {
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : "";
}

export default function ReportsPage() {
  return (
    <Suspense fallback={<TableSkeleton />}>
      <ReportsList />
    </Suspense>
  );
}

function ReportsList() {
  const me = useMe();
  const { t, locale } = useT();
  const toast = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const canView = canSeeReports(me);
  const canCreate = can(me, "edit_reports");
  const canExport = can(me, "export_reports");

  // Filters live in the URL so Home can link straight to "overdue" or "returned to me".
  const status = pick(params.get("status"), STATUSES);
  const type = pick(params.get("type"), REPORT_TYPES);
  const due = pick(params.get("due"), ["soon", "overdue"] as const) as DueFilter;
  const mine = params.get("mine") === "1";
  const [query, setQuery] = useState("");

  const [reports, setReports] = useState<ReportRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(
    () =>
      listReports().then(
        (r) => {
          setReports(r);
          setError(null);
        },
        (e: unknown) => setError(errorText(e)),
      ),
    [],
  );

  useEffect(() => {
    if (canView) void load();
  }, [canView, load]);

  function setParam(key: string, value: string) {
    paged.setPage(1);
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  // Everything but the status tab, so each tab can show how many it would list.
  const base = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (reports ?? []).filter(
      (r) =>
        (!type || r.report_type === type) &&
        (!due || dueState(r) === due) &&
        (!mine || r.created_by === me.id) &&
        (!q || r.title.toLowerCase().includes(q)),
    );
  }, [reports, type, due, mine, query, me.id]);
  const rows = useMemo(() => (status ? base.filter((r) => r.status === status) : base), [base, status]);

  const { sorted, header } = useSort<ReportRow, SortKey>(
    rows,
    (r, key) =>
      key === "title"
        ? r.title.toLowerCase()
        : key === "type"
          ? t(`reportType.${r.report_type}` as LabelKey)
          : key === "status"
            ? STATUSES.indexOf(r.status)
            : key === "due"
              ? r.due_date
              : r.created_at,
    { key: "created", dir: "desc" },
  );
  const paged = usePaged(sorted, 20);

  // A Viewer holds only export_reports, so this is often the one thing they do here. Only the
  // exported row is fetched again (an approved report becomes Exported).
  const [exportingId, setExportingId] = useState<string | null>(null);
  async function doExport(r: ReportRow) {
    setExportingId(r.id);
    try {
      await exportReport(r.id, "docx");
      const fresh = await getReport(r.id);
      setReports((all) => all?.map((x) => (x.id === fresh.id ? fresh : x)) ?? all);
    } catch (err) {
      toast({ tone: "danger", title: t("reports.exportFailed"), body: errorText(err, t) });
    } finally {
      setExportingId(null);
    }
  }

  if (!canView)
    return (
      <>
        <PageHeader title={t("reports")} />
        <EmptyState title={t("noPermission")} />
      </>
    );

  const filtered = !!(status || type || due || mine || query.trim());
  const statusTabs = [
    { value: "", label: t("ui.all"), count: base.length },
    ...STATUSES.map((s) => ({
      value: s,
      label: t(`reportStatus.${s}` as LabelKey),
      count: base.filter((r) => r.status === s).length,
    })),
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("reports")}
        description={t("reports.listDescription")}
        actions={
          canCreate && (
            <>
              <ButtonLink href="/pq-replies/new" variant="primary" icon={<Landmark size={16} aria-hidden />}>
                {t("newPqReply")}
              </ButtonLink>
              <ButtonLink href="/monthly-reports/new" variant="secondary" icon={<CalendarDays size={16} aria-hidden />}>
                {t("newMonthlyReport")}
              </ButtonLink>
              <ButtonLink href="/briefing-notes/new" variant="secondary" icon={<NotebookPen size={16} aria-hidden />}>
                {t("newBriefingNote")}
              </ButtonLink>
              <Button variant="ghost" icon={<FilePlus size={16} aria-hidden />} onClick={() => setShowCreate(true)}>
                {t("reports.blankReport")}
              </Button>
            </>
          )
        }
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

      <TableFrame>
        <div className="px-5 pt-4">
          <Tabs label={t("status")} items={statusTabs} value={status} onChange={(v) => setParam("status", v)} />
        </div>
        <TableToolbar
          title={t("reports")}
          count={reports ? rows.length : undefined}
          total={reports ? reports.length : undefined}
          filters={
            <div className="flex flex-wrap items-center gap-3">
              <div className="w-44">
                <Select
                  aria-label={t("reportType")}
                  value={type}
                  onChange={(e) => setParam("type", e.target.value)}
                  className="h-9"
                >
                  <option value="">{t("reports.allTypes")}</option>
                  {REPORT_TYPES.map((rt) => (
                    <option key={rt} value={rt}>
                      {t(`reportType.${rt}` as LabelKey)}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="w-44">
                <Select
                  aria-label={t("reports.dueFilter")}
                  value={due}
                  onChange={(e) => setParam("due", e.target.value)}
                  className="h-9"
                >
                  <option value="">{t("reports.anyDue")}</option>
                  <option value="soon">{t("dash.dueSoon")}</option>
                  <option value="overdue">{t("dash.overdue")}</option>
                </Select>
              </div>
              <Checkbox
                label={t("reports.onlyMine")}
                checked={mine}
                onChange={(e) => setParam("mine", e.target.checked ? "1" : "")}
              />
            </div>
          }
          search={<SearchInput
              value={query}
              onChange={(v) => {
                setQuery(v);
                paged.setPage(1);
              }}
              placeholder={t("reports.searchTitle")} />}
        />

        {!reports && !error && <TableSkeleton columns={6} />}

        {reports && rows.length === 0 && (
          <div className="px-5 pb-5">
            <EmptyState
              compact
              icon={<FileText />}
              title={filtered ? t("reports.noMatches") : t("home.noReports")}
              action={
                filtered ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setQuery("");
                      router.replace(pathname, { scroll: false });
                    }}
                  >
                    {t("ui.clearFilters")}
                  </Button>
                ) : undefined
              }
            >
              {filtered ? t("reports.noMatchesBody") : t("home.noReportsBody")}
            </EmptyState>
          </div>
        )}

        {reports && rows.length > 0 && (
          <>
            {/* Stacked list on phones; the table below from the sm breakpoint. */}
            <ul className="divide-y divide-line border-t border-line sm:hidden">
              {paged.rows.map((r) => (
                <li key={r.id} className="space-y-2 px-5 py-3">
                  <Link href={`/reports/${r.id}`} className="block font-medium text-brand hover:underline">
                    {r.title}
                  </Link>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                    <StatusBadge kind="report" value={r.status} />
                    <span>{t(`reportType.${r.report_type}` as LabelKey)}</span>
                    {r.due_date && (
                      <span className="tabular-nums">
                        {t("home.due")}: {formatDate(r.due_date, locale)}
                      </span>
                    )}
                    <DueBadge report={r} />
                  </div>
                  {canExport && (
                    <Button
                      size="sm"
                      variant="outline"
                      loading={exportingId === r.id}
                      disabled={exportingId !== null && exportingId !== r.id}
                      onClick={() => void doExport(r)}
                    >
                      {exportingId === r.id ? t("report.exporting") : t("report.exportDocx")}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            <div className="hidden sm:block">
              <Table caption={t("reports")}>
                <THead>
                  <TH sort={header("title")}>{t("title")}</TH>
                  <TH sort={header("type")}>{t("reportType")}</TH>
                  <TH sort={header("status")}>{t("status")}</TH>
                  <TH sort={header("due")}>{t("reports.dueColumn")}</TH>
                  <TH sort={header("created")}>{t("reports.createdOn")}</TH>
                  <TH>{t("createdBy")}</TH>
                  {canExport && <TH align="right">{t("report.export")}</TH>}
                </THead>
                <tbody>
                  {paged.rows.map((r) => (
                    <TR key={r.id}>
                      <TD className="max-w-80">
                        <Link href={`/reports/${r.id}`} className="font-medium text-brand hover:underline">
                          {r.title}
                        </Link>
                      </TD>
                      <TD className="whitespace-nowrap">{t(`reportType.${r.report_type}` as LabelKey)}</TD>
                      <TD>
                        <StatusBadge kind="report" value={r.status} />
                      </TD>
                      <TD className="whitespace-nowrap">
                        <span className="flex items-center gap-2">
                          <span className="tabular-nums">{formatDate(r.due_date, locale)}</span>
                          <DueBadge report={r} />
                        </span>
                      </TD>
                      <TD className="whitespace-nowrap tabular-nums">{formatDateTime(r.created_at, locale)}</TD>
                      <TD className="whitespace-nowrap text-muted">
                        {r.created_by === me.id ? t("reports.you") : t("reports.colleague")}
                      </TD>
                      {canExport && (
                        <TD align="right">
                          <Button
                            size="sm"
                            variant="outline"
                            loading={exportingId === r.id}
                            disabled={exportingId !== null && exportingId !== r.id}
                            onClick={() => void doExport(r)}
                            aria-label={`${t("report.exportDocx")}: ${r.title}`}
                          >
                            {exportingId === r.id ? t("report.exporting") : t("report.exportDocx")}
                          </Button>
                        </TD>
                      )}
                    </TR>
                  ))}
                </tbody>
              </Table>
            </div>
            <Pagination
              page={paged.page}
              pageCount={paged.pageCount}
              onPage={paged.setPage}
              from={paged.from}
              to={paged.to}
              total={paged.total}
            />
          </>
        )}
      </TableFrame>

      {showCreate && <NewReportDrawer onClose={() => setShowCreate(false)} />}
    </div>
  );
}
