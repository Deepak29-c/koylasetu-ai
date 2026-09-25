"use client";

import { useState } from "react";

import { useMe } from "@/components/AppShell";
import ReportDraftView, { newKey } from "@/components/ReportDraftView";
import { draftMonthlyReport, type ReportDraftOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

/** Last month as "YYYY-MM": the usual month to report on. */
function lastMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function NewMonthlyReportPage() {
  const me = useMe();
  const { t } = useT();
  const [month, setMonth] = useState(lastMonth);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<ReportDraftOut | null>(null);
  // Same key while the month is unchanged, so a retry returns the draft already made.
  const [requestKey, setRequestKey] = useState<string | null>(null);

  if (!me.permissions.includes("edit_reports")) return <p className="text-gray-600">{t("noPermission")}</p>;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !month) return;
    const key = requestKey ?? newKey();
    setRequestKey(key);
    setBusy(true);
    setError(null);
    setDraft(null);
    try {
      setDraft(await draftMonthlyReport(month, key));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("monthlyTitle")}</h1>
        <p className="text-sm text-gray-600">{t("monthlyHelp")}</p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-4 rounded border bg-white p-4">
        <label className="block">
          <span className="text-sm font-medium">{t("reportMonth")}</span>
          <input
            type="month"
            required
            value={month}
            onChange={(e) => {
              setMonth(e.target.value);
              setRequestKey(null);
            }}
            className="mt-1 block rounded border px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !month}
          className="rounded bg-brand px-6 py-2.5 font-medium text-white disabled:opacity-50"
        >
          {t("generateDraft")}
        </button>
        {busy && <span className="text-sm text-gray-600">{t("generatingMonthly")}</span>}
      </form>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {draft?.report.content_json.remarks_by === "rule" && (
        <p className="text-sm text-gray-600">{t("remarksByRule")}</p>
      )}
      {draft && <ReportDraftView draft={draft} filePrefix="monthly-report" />}
    </div>
  );
}
