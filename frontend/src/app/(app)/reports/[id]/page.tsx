"use client";

import { CircleCheck, CornerUpLeft, Download, FileText, History, ListChecks, Save, Send } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useMe } from "@/components/AppShell";
import ConfirmDialog from "@/components/ConfirmDialog";
import {
  editMode,
  generatedContent,
  latestReturn,
  mergeContent,
  originalEdits,
  readStash,
  stashKey,
  writeStash,
  chipSources,
} from "@/components/reports/content";
import DueBadge from "@/components/reports/DueBadge";
import { StatusTimeline, VersionList } from "@/components/reports/History";
import ReportEditor, { unlinkedByItem } from "@/components/reports/ReportEditor";
import SimilarQuestions from "@/components/similar/SimilarQuestions";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Field, Textarea } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import RecordList from "@/components/ui/RecordList";
import { PageSkeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import {
  ApiError,
  approveReport,
  exportReport,
  getReport,
  listReportVersions,
  rejectReport,
  type ReportRow,
  type ReportVersionRow,
  submitReport,
  updateReport,
} from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatDate, formatDateTime } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { can, canSeeReports } from "@/lib/permissions";
import { contentMode, EDITABLE_STATUSES } from "@/lib/reportView";
import { pqQuestionText } from "@/lib/similar";


export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const me = useMe();
  const toast = useToast();
  const { t, locale } = useT();
  const canView = canSeeReports(me);
  const canEdit = can(me, "edit_reports");
  const canApprove = can(me, "approve_reports");
  const canExport = can(me, "export_reports");
  // Source links from this page bring the viewer's Back button here.
  const from = `/reports/${id}`;

  const [report, setReport] = useState<ReportRow | null>(null);
  const [versions, setVersions] = useState<ReportVersionRow[]>([]);
  const [error, setError] = useState<{ message: string; notFound: boolean } | null>(null);
  // One string per PQ part / report section (or the whole text), as typed.
  const [edits, setEdits] = useState<string[]>([]);
  // What the server holds. Anything else in `edits` is unsaved.
  const [saved, setSaved] = useState<string[]>([]);
  const [restoredDraft, setRestoredDraft] = useState(false);

  const mode = report ? editMode(report.content_json) : "text";

  /** Fetches the report and its versions. `restoreStash: false` refreshes them and keeps what is typed. */
  const load = useCallback(
    ({ restoreStash = true }: { restoreStash?: boolean } = {}) =>
      Promise.all([getReport(id), listReportVersions(id)]).then(
        ([r, v]) => {
          const m = editMode(r.content_json);
          const onServer = originalEdits(r.content_json, m);
          const editableNow = canEdit && EDITABLE_STATUSES.includes(r.status);
          // Unsaved edits survive an expired session, a closed tab or a crash (#45), but only
          // while the report can still be edited: otherwise they could never be saved.
          let stashed: string[] | null = null;
          try {
            if (!editableNow) sessionStorage.removeItem(stashKey(id));
            else if (restoreStash) stashed = readStash(id, m, onServer.length);
          } catch {
            // storage blocked: nothing to restore, carry on with the server's copy
          }
          const restore = !!stashed && stashed.some((e, i) => e !== onServer[i]);
          setReport(r);
          setVersions(v);
          setSaved(onServer);
          if (restoreStash || !editableNow) {
            setEdits(restore ? stashed! : onServer);
            setRestoredDraft(restore);
          }
          setError(null);
        },
        (e: unknown) => setError({ message: errorText(e), notFound: e instanceof ApiError && e.status === 404 }),
      ),
    [id, canEdit],
  );

  useEffect(() => {
    if (canView) void load();
  }, [canView, load]);

  const dirty = edits.some((e, i) => e !== saved[i]);

  useEffect(() => {
    // Wait for the report: before it loads both lists are empty, which looks clean and
    // would delete the stash before load() has had a chance to read it.
    if (!report) return;
    try {
      if (dirty) writeStash(id, mode, edits);
      else sessionStorage.removeItem(stashKey(id));
    } catch {
      // storage blocked: the leave warnings below are the remaining safety net
    }
  }, [report, dirty, edits, id, mode]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  // Any in-app link (sidebar, breadcrumbs, a source chip) asks first while there are unsaved
  // edits. Capture phase, so the link's own navigation sees the click as already handled.
  const [leaveTo, setLeaveTo] = useState<string | null>(null);
  useEffect(() => {
    if (!dirty) return;
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
      const url = new URL(a.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search) return;
      e.preventDefault();
      e.stopPropagation();
      setLeaveTo(url.pathname + url.search + url.hash);
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [dirty]);

  const content = report?.content_json;
  const sources = useMemo(() => (content ? chipSources(content) : new Map()), [content]);
  // Hand-typed figures are judged against the generated draft, so saving does not hide them.
  const generated = useMemo(() => (content ? generatedContent(content, versions) : null), [content, versions]);
  const unlinked = useMemo(
    () => (generated ? unlinkedByItem(generated, mode, edits) : []),
    [generated, mode, edits],
  );
  const unlinkedTotal = unlinked.reduce((n, xs) => n + xs.length, 0);

  const [actionError, setActionError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  function change(index: number, value: string) {
    setJustSaved(false);
    setEdits((xs) => xs.map((x, i) => (i === index ? value : x)));
  }

  /** The whole content_json with the edits merged in; the server replaces what it holds. */
  async function persist() {
    if (!report) return;
    await updateReport(id, { content_json: mergeContent(report.content_json, mode, edits) });
  }

  async function saveDraft() {
    setSaving(true);
    setJustSaved(false);
    setActionError(null);
    try {
      await persist();
      setSaved(edits);
      await load();
      setJustSaved(true);
    } catch (err) {
      setActionError(errorText(err, t));
    } finally {
      setSaving(false);
    }
  }

  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  async function doSubmit() {
    setSubmitting(true);
    setActionError(null);
    try {
      await persist();
      await submitReport(id);
      setSaved(edits);
      setConfirmSubmit(false);
      toast({ title: t("reports.submitted"), body: report?.title });
      await load();
    } catch (err) {
      setConfirmSubmit(false);
      setActionError(errorText(err, t));
    } finally {
      setSubmitting(false);
    }
  }

  const [confirmApprove, setConfirmApprove] = useState(false);
  const [approving, setApproving] = useState(false);
  async function doApprove() {
    setApproving(true);
    setActionError(null);
    try {
      await approveReport(id);
      setConfirmApprove(false);
      toast({ title: t("reports.approved"), body: report?.title });
      await load();
    } catch (err) {
      setConfirmApprove(false);
      setActionError(errorText(err, t));
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
      await rejectReport(id, rejectComment.trim());
      setShowReject(false);
      setRejectComment("");
      toast({ title: t("reports.returned"), body: report?.title });
      await load();
    } catch (err) {
      setShowReject(false);
      setActionError(errorText(err, t));
    } finally {
      setRejecting(false);
    }
  }

  // Downloading is the last step of the workflow and the only thing a Viewer can do here.
  const [exporting, setExporting] = useState<"docx" | "pdf" | null>(null);
  async function doExport(format: "docx" | "pdf") {
    setExporting(format);
    setActionError(null);
    try {
      await exportReport(id, format);
      await load({ restoreStash: false });
    } catch (err) {
      setActionError(errorText(err, t));
    } finally {
      setExporting(null);
    }
  }

  if (!canView)
    return (
      <>
        <PageHeader title={t("reports")} breadcrumbs={[{ label: t("reports"), href: "/reports" }]} />
        <EmptyState title={t("noPermission")} />
      </>
    );
  if (error && !report)
    return (
      <>
        <PageHeader
          title={error.notFound ? t("reportNotFound") : t("ui.somethingWrong")}
          breadcrumbs={[{ label: t("reports"), href: "/reports" }]}
          back={{ href: "/reports", label: t("backToReports") }}
        />
        <Alert
          tone="danger"
          action={
            !error.notFound && (
              <Button size="sm" variant="danger-outline" onClick={() => void load()}>
                {t("retry")}
              </Button>
            )
          }
        >
          {error.message}
        </Alert>
      </>
    );
  if (!report || !content || !generated) return <PageSkeleton cards={2} />;

  // Can't edit reports at all -> read-only view with no status excuse; blocked only by the
  // status -> say so, because for them that is the reason.
  const access = contentMode(canEdit, report.status);
  const editable = access === "edit";
  const returned = report.status === "RETURNED" ? latestReturn(versions) : null;
  const warnings = content.warnings ?? [];
  const statusLabel = t(`reportStatus.${report.status}` as LabelKey);

  return (
    <div className="space-y-6">
      <PageHeader
        title={report.title}
        breadcrumbs={[{ label: t("reports"), href: "/reports" }]}
        back={{ href: "/reports", label: t("backToReports") }}
        meta={
          <>
            <StatusBadge kind="report" value={report.status} size="md" />
            <Badge tone="brand" size="md">
              {t(`reportType.${report.report_type}` as LabelKey)}
            </Badge>
            <DueBadge report={report} />
          </>
        }
      />

      {returned && (
        <Alert tone="warning" title={t("reports.returnedTitle")}>
          <p className="whitespace-pre-line">{returned.comment}</p>
          <p className="mt-1 text-xs opacity-80">
            {returned.by} · {formatDateTime(returned.at, locale)}
          </p>
        </Alert>
      )}
      {restoredDraft && dirty && (
        <Alert tone="info" onDismiss={() => setRestoredDraft(false)}>
          {t("editor.draftRestored")}
        </Alert>
      )}
      {actionError && (
        <Alert tone="danger" onDismiss={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}
      {error && (
        <Alert
          tone="danger"
          title={t("reports.reloadFailed")}
          onDismiss={() => setError(null)}
          action={
            <Button size="sm" variant="danger-outline" onClick={() => void load({ restoreStash: false })}>
              {t("retry")}
            </Button>
          }
        >
          {error.message}
        </Alert>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            icon={<FileText />}
            title={t("reportContent")}
            subtitle={editable ? t(`reports.editHelp.${mode}` as LabelKey) : undefined}
          />
          <div className="space-y-4">
            {access === "status_blocked" && (
              <Alert tone="info">
                {t("cannotEditNow")} {statusLabel}
              </Alert>
            )}
            {warnings.length > 0 && (
              <Alert tone="warning" title={t("reports.generatorWarnings")}>
                <ul className="list-disc space-y-1 pl-4">
                  {warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </Alert>
            )}
            {unlinkedTotal > 0 && (
              <Alert tone="danger" title={`${unlinkedTotal} ${t("reports.unlinkedCount")}`}>
                {t("reports.unlinkedHelp")}
              </Alert>
            )}
            <ReportEditor
              content={content}
              generated={generated}
              mode={mode}
              edits={edits}
              unlinked={unlinked}
              editable={editable}
              onChange={change}
              sources={sources}
              from={from}
            />
          </div>
          {editable && (
            <div className="sticky bottom-0 -mx-5 mt-5 flex flex-wrap items-center gap-3 rounded-b-card border-t border-line bg-surface px-5 pt-4 pb-1 sm:-mx-6 sm:px-6">
              <Button
                variant="primary"
                icon={<Send size={16} aria-hidden />}
                onClick={() => setConfirmSubmit(true)}
                disabled={saving || submitting}
              >
                {t("submitForApproval")}
              </Button>
              <Button
                variant="outline"
                icon={<Save size={16} aria-hidden />}
                onClick={() => void saveDraft()}
                loading={saving}
                disabled={!dirty || submitting}
              >
                {saving ? t("saving") : t("saveDraft")}
              </Button>
              <span role="status" className="text-sm">
                {dirty ? (
                  <span className="font-medium text-warning-fg">{t("editor.unsavedChanges")}</span>
                ) : (
                  justSaved && <span className="font-medium text-success-fg">{t("savedDraft")}</span>
                )}
              </span>
            </div>
          )}
        </Card>

        <div className="space-y-6">
          {canApprove && report.status === "IN_REVIEW" && (
            <Card>
              <CardHeader icon={<ListChecks />} title={t("reports.decision")} subtitle={t("reports.decisionHelp")} />
              <div className="flex flex-wrap gap-2">
                <Button variant="success" icon={<CircleCheck size={16} aria-hidden />} onClick={() => setConfirmApprove(true)}>
                  {t("approve")}
                </Button>
                <Button variant="danger-outline" icon={<CornerUpLeft size={16} aria-hidden />} onClick={() => setShowReject(true)}>
                  {t("reject")}
                </Button>
              </div>
            </Card>
          )}

          <Card>
            <CardHeader title={t("reports.details")} />
            <RecordList
              items={[
                { label: t("reportType"), value: t(`reportType.${report.report_type}` as LabelKey) },
                { label: t("status"), value: statusLabel },
                { label: t("reports.dueColumn"), value: report.due_date ? formatDate(report.due_date, locale) : null },
                { label: t("reports.createdOn"), value: formatDateTime(report.created_at, locale) },
                { label: t("reports.lastChanged"), value: formatDateTime(report.updated_at, locale) },
              ]}
            />
          </Card>

          {report.report_type === "pq_reply" && (
            <SimilarQuestions text={pqQuestionText(report)} exclude={report.id} limit={3} />
          )}

          {canExport && (
            <Card>
              <CardHeader icon={<Download />} title={t("report.export")} subtitle={t("report.exportHelp")} />
              {dirty && <p className="mb-3 text-xs text-warning-fg">{t("reports.exportUnsaved")}</p>}
              <div className="flex flex-wrap gap-2">
                {(["docx", "pdf"] as const).map((format) => (
                  <Button
                    key={format}
                    variant="outline"
                    loading={exporting === format}
                    disabled={exporting !== null && exporting !== format}
                    onClick={() => void doExport(format)}
                  >
                    {exporting === format
                      ? t("report.exporting")
                      : t(format === "docx" ? "report.exportDocx" : "report.exportPdf")}
                  </Button>
                ))}
              </div>
            </Card>
          )}

          <Card>
            <CardHeader icon={<Send />} title={t("reports.timeline")} />
            <StatusTimeline report={report} versions={versions} />
          </Card>

          <Card>
            <CardHeader icon={<History />} title={t("versionHistory")} />
            <VersionList versions={versions} />
          </Card>
        </div>
      </div>

      {confirmSubmit && (
        <ConfirmDialog
          title={t("editor.submitConfirm")}
          body={t("editor.submitConfirmBody")}
          confirmLabel={t("submitForApproval")}
          busy={submitting}
          onConfirm={() => void doSubmit()}
          onCancel={() => setConfirmSubmit(false)}
        >
          {unlinkedTotal > 0 && (
            <Alert tone="danger">
              {unlinkedTotal} {t("reports.unlinkedCount")}. {t("reports.unlinkedHelp")}
            </Alert>
          )}
        </ConfirmDialog>
      )}

      {confirmApprove && (
        <ConfirmDialog
          title={t("reports.approveConfirm")}
          body={t("reports.approveConfirmBody")}
          confirmLabel={t("approve")}
          positive
          busy={approving}
          onConfirm={() => void doApprove()}
          onCancel={() => setConfirmApprove(false)}
        />
      )}

      {showReject && (
        <ConfirmDialog
          title={t("reports.rejectConfirm")}
          body={t("reports.rejectConfirmBody")}
          confirmLabel={t("confirmReject")}
          danger
          busy={rejecting}
          confirmDisabled={rejectComment.trim().length === 0}
          onConfirm={() => void doReject()}
          onCancel={() => setShowReject(false)}
        >
          <Field label={t("rejectReasonLabel")} required>
            <Textarea
              value={rejectComment}
              onChange={(e) => setRejectComment(e.target.value)}
              placeholder={t("rejectReasonPlaceholder")}
              rows={4}
              maxLength={2000}
            />
          </Field>
        </ConfirmDialog>
      )}

      {leaveTo && (
        <ConfirmDialog
          title={t("editor.leaveWithoutSaving")}
          body={t("editor.leaveWithoutSavingBody")}
          confirmLabel={t("editor.leaveAnyway")}
          danger
          onConfirm={() => {
            // The stash stays, so coming back to this report offers the edits again.
            const to = leaveTo;
            setLeaveTo(null);
            router.push(to);
          }}
          onCancel={() => setLeaveTo(null)}
        />
      )}
    </div>
  );
}
