"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import { ApiError, createReport, exportReport, listReports, type ReportRow, type ReportStatus, type ReportType } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

const REPORT_TYPES: ReportType[] = ["pq_reply", "monthly", "briefing"];

const STATUS_STYLE: Record<ReportStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  IN_REVIEW: "bg-blue-100 text-blue-800",
  RETURNED: "bg-amber-100 text-amber-900",
  APPROVED: "bg-green-100 text-green-800",
  EXPORTED: "bg-purple-100 text-purple-800",
};

export default function ReportsPage() {
  const me = useMe();
  const { t } = useT();
  const canView =
    me.permissions.includes("edit_reports") ||
    me.permissions.includes("approve_reports") ||
    me.permissions.includes("export_reports");
  const canCreate = me.permissions.includes("edit_reports");
  const canExport = me.permissions.includes("export_reports");

  const [reports, setReports] = useState<ReportRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      listReports().then(
        (r) => {
          setReports(r);
          setError(null);
        },
        (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  );

  useEffect(() => {
    if (canView) load();
  }, [canView, load]);

  // A Viewer holds only export_reports, so without this the list is read-only for them.
  const [exportingId, setExportingId] = useState<string | null>(null);
  async function doExport(id: string) {
    setExportingId(id);
    setError(null);
    try {
      await exportReport(id, "docx");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setExportingId(null);
    }
  }

  const [showCreate, setShowCreate] = useState(false);
  const [newType, setNewType] = useState<ReportType>("briefing");
  const [newTitle, setNewTitle] = useState("");
  const [newDueDate, setNewDueDate] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await createReport({
        report_type: newType,
        title: newTitle,
        due_date: newDueDate || null,
      });
      setNewTitle("");
      setNewDueDate("");
      setShowCreate(false);
      await load();
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCreating(false);
    }
  }

  if (!canView) return <p className="text-gray-600">{t("noPermission")}</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t("reports")}</h1>
        {canCreate && (
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="rounded bg-brand px-4 py-2 text-sm font-medium text-white"
          >
            {showCreate ? t("cancel") : t("newReport")}
          </button>
        )}
      </div>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}

      {showCreate && (
        <form onSubmit={submitCreate} className="space-y-4 rounded border bg-white p-4">
          <h2 className="font-medium">{t("createReportTitle")}</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block">
              <span className="text-sm font-medium">{t("reportType")}</span>
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value as ReportType)}
                className="mt-1 w-full rounded border px-3 py-2"
              >
                {REPORT_TYPES.map((rt) => (
                  <option key={rt} value={rt}>
                    {t(`reportType.${rt}` as LabelKey)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium">{t("title")}</span>
              <input
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="mt-1 w-full rounded border px-3 py-2"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">{t("dueDate")}</span>
              <input
                type="date"
                value={newDueDate}
                onChange={(e) => setNewDueDate(e.target.value)}
                className="mt-1 w-full rounded border px-3 py-2"
              />
            </label>
          </div>
          {createError && <p className="text-sm text-red-700">{createError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="rounded bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {creating ? t("creating") : t("createReportButton")}
          </button>
        </form>
      )}

      {reports === null && !error && <p className="text-gray-500">{t("loading")}</p>}
      {reports?.length === 0 && <p className="text-gray-600">{t("noReports")}</p>}
      {reports && reports.length > 0 && (
        <div className="overflow-x-auto rounded border bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2 font-medium">{t("title")}</th>
                <th className="px-4 py-2 font-medium">{t("reportType")}</th>
                <th className="px-4 py-2 font-medium">{t("status")}</th>
                <th className="px-4 py-2 font-medium">{t("dueDate")}</th>
                <th className="px-4 py-2 font-medium">{t("uploadedOn")}</th>
                {canExport && <th className="px-4 py-2 font-medium">{t("report.export")}</th>}
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id} className="border-t align-top">
                  <td className="px-4 py-2">
                    <Link href={`/reports/${r.id}`} className="font-medium text-brand hover:underline">
                      {r.title}
                    </Link>
                  </td>
                  <td className="px-4 py-2">{t(`reportType.${r.report_type}` as LabelKey)}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[r.status]}`}>
                      {t(`reportStatus.${r.status}` as LabelKey)}
                    </span>
                  </td>
                  <td className="px-4 py-2">{r.due_date ?? "—"}</td>
                  <td className="px-4 py-2 whitespace-nowrap">
                    {new Date(r.created_at).toLocaleString("en-IN")}
                  </td>
                  {canExport && (
                    <td className="px-4 py-2 whitespace-nowrap">
                      <button
                        onClick={() => doExport(r.id)}
                        disabled={exportingId !== null}
                        className="text-xs text-brand underline disabled:text-gray-400 disabled:no-underline"
                      >
                        {exportingId === r.id ? t("report.exporting") : t("report.exportDocx")}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
