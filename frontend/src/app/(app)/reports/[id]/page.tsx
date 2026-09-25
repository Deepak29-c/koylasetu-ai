"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  ApiError,
  approveReport,
  getReport,
  listReportVersions,
  rejectReport,
  type ReportRow,
  type ReportStatus,
  type ReportVersionRow,
  submitReport,
  updateReport,
} from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

const STATUS_STYLE: Record<ReportStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-800",
  IN_REVIEW: "bg-blue-100 text-blue-800",
  RETURNED: "bg-amber-100 text-amber-900",
  APPROVED: "bg-green-100 text-green-800",
  EXPORTED: "bg-purple-100 text-purple-800",
};

const EDITABLE_STATUSES: ReportStatus[] = ["DRAFT", "RETURNED"];

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useMe();
  const { t } = useT();
  const canView =
    me.permissions.includes("edit_reports") ||
    me.permissions.includes("approve_reports") ||
    me.permissions.includes("export_reports");
  const canEdit = me.permissions.includes("edit_reports");
  const canApprove = me.permissions.includes("approve_reports");

  const [report, setReport] = useState<ReportRow | null>(null);
  const [versions, setVersions] = useState<ReportVersionRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  // What the server currently holds. Anything else in the textarea is unsaved.
  const [savedText, setSavedText] = useState("");
  const [restoredDraft, setRestoredDraft] = useState(false);
  // Unsaved text survives an expired session, a closed tab or a crash (#45).
  const stashKey = `ks_draft_${id}`;

  const load = useCallback(
    () =>
      Promise.all([getReport(id), listReportVersions(id)]).then(
        ([r, v]) => {
          setReport(r);
          setVersions(v);
          const onServer = r.content_json.text ?? "";
          setSavedText(onServer);
          let stashed: string | null = null;
          try {
            stashed = sessionStorage.getItem(stashKey);
          } catch {
            // storage blocked: nothing to restore, carry on with the server's copy
          }
          setText(stashed !== null && stashed !== onServer ? stashed : onServer);
          setRestoredDraft(stashed !== null && stashed !== onServer);
          setError(null);
        },
        (e: unknown) => setError(e instanceof ApiError ? e.message : String(e)),
      ),
    [id, stashKey],
  );

  useEffect(() => {
    if (canView) load();
  }, [canView, load]);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function saveDraft() {
    setSaving(true);
    setSaved(false);
    setActionError(null);
    try {
      await updateReport(id, { content_json: { text } });
      setSavedText(text);
      setSaved(true);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  const [submitting, setSubmitting] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [confirmLeave, setConfirmLeave] = useState(false);
  async function doSubmit() {
    setConfirmSubmit(false);
    setSubmitting(true);
    setActionError(null);
    try {
      await updateReport(id, { content_json: { text } });
      await submitReport(id);
      setSavedText(text);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const [approving, setApproving] = useState(false);
  async function doApprove() {
    setApproving(true);
    setActionError(null);
    try {
      await approveReport(id);
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setApproving(false);
    }
  }

  const [showReject, setShowReject] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [rejecting, setRejecting] = useState(false);
  async function doReject() {
    setRejecting(true);
    setActionError(null);
    try {
      await rejectReport(id, rejectComment);
      setShowReject(false);
      setRejectComment("");
      await load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setRejecting(false);
    }
  }

  const dirty = text !== savedText;

  useEffect(() => {
    try {
      if (dirty) sessionStorage.setItem(stashKey, text);
      else sessionStorage.removeItem(stashKey);
    } catch {
      // storage blocked: the beforeunload warning below is the remaining safety net
    }
  }, [dirty, text, stashKey]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  if (!canView) return <p className="text-gray-600">{t("noPermission")}</p>;
  if (error) return <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>;
  if (!report) return <p className="text-gray-500">{t("loading")}</p>;

  const editable = canEdit && EDITABLE_STATUSES.includes(report.status);

  return (
    <div className="space-y-4">
      <Link
        href="/reports"
        onClick={(e) => {
          if (dirty) {
            e.preventDefault();
            setConfirmLeave(true);
          }
        }}
        className="text-sm text-brand underline"
      >
        ← {t("backToReports")}
      </Link>

      <div className="rounded border bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold">{report.title}</h1>
            <p className="text-sm text-gray-500">
              {t(`reportType.${report.report_type}` as LabelKey)}
              {report.due_date && ` · ${t("dueDate")}: ${report.due_date}`}
            </p>
          </div>
          <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[report.status]}`}>
            {t(`reportStatus.${report.status}` as LabelKey)}
          </span>
        </div>
      </div>

      <div className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">{t("reportContent")}</h2>
        {!editable && (
          <p className="mb-2 text-sm text-gray-600">
            {t("cannotEditNow")} {t(`reportStatus.${report.status}` as LabelKey)}
          </p>
        )}
        <p className="mb-2 text-xs text-gray-500">{t("reportContentHelp")}</p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={!editable}
          rows={12}
          className="w-full rounded border px-3 py-2 font-mono text-sm disabled:bg-gray-50 disabled:text-gray-600"
        />
        {actionError && <p className="mt-2 text-sm text-red-700">{actionError}</p>}
        {editable && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              onClick={saveDraft}
              disabled={saving}
              className="rounded border border-brand px-4 py-2 text-sm font-medium text-brand disabled:opacity-60"
            >
              {saving ? t("saving") : t("saveDraft")}
            </button>
            <button
              onClick={() => setConfirmSubmit(true)}
              disabled={submitting}
              className="rounded bg-brand px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {submitting ? t("submitting") : t("submitForApproval")}
            </button>
            {dirty ? (
              <span className="text-sm text-amber-700">
                {t("editor.unsavedChanges")}
                {restoredDraft && ` — ${t("editor.draftRestored")}`}
              </span>
            ) : (
              saved && <span className="text-sm text-green-700">{t("savedDraft")}</span>
            )}
          </div>
        )}

        {canApprove && report.status === "IN_REVIEW" && (
          <div className="mt-4 space-y-3 border-t pt-4">
            <div className="flex flex-wrap gap-3">
              <button
                onClick={doApprove}
                disabled={approving}
                className="rounded bg-green-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {approving ? t("approving") : t("approve")}
              </button>
              <button
                onClick={() => setShowReject((v) => !v)}
                className="rounded border border-red-600 px-4 py-2 text-sm font-medium text-red-700"
              >
                {t("reject")}
              </button>
            </div>
            {showReject && (
              <div className="space-y-2">
                <label className="block text-sm font-medium">{t("rejectReasonLabel")}</label>
                <textarea
                  value={rejectComment}
                  onChange={(e) => setRejectComment(e.target.value)}
                  placeholder={t("rejectReasonPlaceholder")}
                  rows={3}
                  className="w-full rounded border px-3 py-2 text-sm"
                />
                <button
                  onClick={doReject}
                  disabled={rejecting || rejectComment.trim().length === 0}
                  className="rounded bg-red-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                >
                  {rejecting ? t("rejecting") : t("confirmReject")}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded border bg-white p-4">
        <h2 className="mb-2 font-medium">{t("versionHistory")}</h2>
        <ul className="space-y-2 text-sm">
          {versions.map((v) => (
            <li key={v.version} className="border-b pb-2 last:border-0">
              <span className="font-medium">v{v.version}</span> — {v.change_note ?? "—"} ({t("by")}{" "}
              {v.editor.name}, {new Date(v.created_at).toLocaleString("en-IN")})
            </li>
          ))}
        </ul>
      </div>

      {confirmSubmit && (
        <ConfirmDialog
          title={t("editor.submitConfirm")}
          body={t("editor.submitConfirmBody")}
          confirmLabel={t("submitForApproval")}
          busy={submitting}
          onConfirm={doSubmit}
          onCancel={() => setConfirmSubmit(false)}
        />
      )}

      {confirmLeave && (
        <ConfirmDialog
          title={t("editor.leaveWithoutSaving")}
          body={t("editor.leaveWithoutSavingBody")}
          confirmLabel={t("editor.leaveAnyway")}
          danger
          onConfirm={() => router.push("/reports")}
          onCancel={() => setConfirmLeave(false)}
        />
      )}
    </div>
  );
}
