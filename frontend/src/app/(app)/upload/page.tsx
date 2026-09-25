"use client";

import { ArrowRight, Building2, CircleAlert, UploadCloud, X } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { useMe } from "@/components/AppShell";
import { ACCEPT, fileIssue, fileKey, FileTypeIcon, formatSize } from "@/components/docs/files";
import ProgressBar from "@/components/docs/ProgressBar";
import Alert from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Checkbox, Field, Input, Select } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { type DocType, type UploadResult, uploadDocuments } from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { type LabelKey, useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { sourceHref } from "@/lib/sources";

const DOC_TYPES: DocType[] = ["annual_report", "coal_inventory", "monthly_stats", "pq_answer", "other"];
const LANGUAGES = ["en", "hi", "mixed"] as const;

export default function UploadPage() {
  const me = useMe();
  const { t, locale } = useT();
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [docType, setDocType] = useState<DocType>("annual_report");
  const [fy, setFy] = useState("");
  const [language, setLanguage] = useState<(typeof LANGUAGES)[number]>("en");
  const [isPublic, setIsPublic] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  // The URL is checked once the person leaves the field or tries to upload, not on every key.
  const [sourceUrlChecked, setSourceUrlChecked] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  if (!can(me, "upload_documents")) {
    return (
      <div className="max-w-3xl">
        <PageHeader title={t("uploadTitle")} />
        <Alert tone="warning">{t("noPermission")}</Alert>
      </div>
    );
  }
  const canMarkPublic = ["CIL_HQ", "MINISTRY"].includes(me.org_unit.code) || me.roles.includes("admin");
  const uploading = progress !== null;
  const hasInvalid = files.some((f) => fileIssue(f) !== null);
  const sourceUrlInvalid = sourceUrl.trim() !== "" && !/^https?:\/\//i.test(sourceUrl.trim());
  const units = { kb: t("docs.unitKB"), mb: t("docs.unitMB") };

  function addFiles(list: File[]) {
    setFiles((prev) => {
      const seen = new Set(prev.map(fileKey));
      return [...prev, ...list.filter((f) => !seen.has(fileKey(f)))];
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSourceUrlChecked(true);
    if (files.length === 0 || hasInvalid || sourceUrlInvalid || uploading) return;
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("doc_type", docType);
    if (fy.trim()) form.append("fy", fy.trim());
    form.append("language", language);
    form.append("is_public", String(canMarkPublic && isPublic));
    if (sourceUrl.trim()) form.append("source_url", sourceUrl.trim());

    setError(null);
    setResults([]);
    setProgress(0);
    try {
      const out = await uploadDocuments(form, setProgress);
      setResults(out);
      setFiles([]);
      const count = (r: UploadResult["result"]) => out.filter((x) => x.result === r).length;
      toast({
        tone: count("created") > 0 ? "success" : "info",
        title: t("docs.uploadDone"),
        body: `${t("created")}: ${count("created")} · ${t("duplicate")}: ${count("duplicate")} · ${t("rejected")}: ${count("rejected")}`,
      });
    } catch (err) {
      setError(errorText(err, t));
    } finally {
      setProgress(null);
    }
  }

  const pct = Math.round((progress ?? 0) * 100);

  return (
    <div>
      <PageHeader title={t("uploadTitle")} description={t("uploadHelp")} />

      <form onSubmit={onSubmit} className="space-y-6" noValidate>
        <div className="grid gap-6 xl:grid-cols-2">
        <Card className="flex flex-col">
          <div
            className="flex flex-1 flex-col"
            onDragOver={(e) => {
              e.preventDefault();
              if (!uploading) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (!uploading) addFiles(Array.from(e.dataTransfer.files));
            }}
          >
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              aria-describedby="upload-accepted"
              className={cn(
                "flex w-full flex-1 flex-col items-center justify-center gap-3 rounded-panel border-2 border-dashed px-6 py-10 text-center transition-colors",
                "focus-visible:border-brand focus-visible:ring-[3px] focus-visible:ring-brand/25 focus-visible:outline-none",
                "disabled:cursor-not-allowed disabled:opacity-60",
                dragging
                  ? "border-brand bg-brand-tint"
                  : "border-line-strong bg-surface-subtle hover:border-brand hover:bg-brand-tint",
              )}
            >
              <span aria-hidden className="grid size-14 place-items-center rounded-full bg-brand-soft text-brand">
                <UploadCloud size={28} />
              </span>
              <span className="text-base font-semibold text-strong">
                {dragging ? t("docs.dropNow") : t("dropHere")}
              </span>
              <span id="upload-accepted" className="text-xs text-muted">
                {t("docs.acceptedTypes")}
              </span>
              <span className="mt-1 inline-flex h-9 items-center rounded-full bg-brand px-4 text-sm font-semibold text-white">
                {t("docs.chooseFiles")}
              </span>
            </button>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept={ACCEPT}
              className="hidden"
              tabIndex={-1}
              onChange={(e) => {
                // Read the list before clearing the input: clearing empties e.target.files,
                // and it is needed so picking the same file again still fires a change event.
                const chosen = Array.from(e.target.files ?? []);
                e.target.value = "";
                addFiles(chosen);
              }}
            />
          </div>

          {files.length > 0 && (
            <div className="mt-5">
              <div className="mb-2 flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-strong">
                  {t("docs.selectedFiles")}{" "}
                  <span className="font-normal text-subtle tabular-nums">({files.length})</span>
                </h2>
                <Button variant="ghost" size="sm" onClick={() => setFiles([])} disabled={uploading}>
                  {t("docs.removeAll")}
                </Button>
              </div>
              <ul className="divide-y divide-line rounded-panel border border-line">
                {files.map((f) => {
                  const issue = fileIssue(f);
                  return (
                    <li key={fileKey(f)} className="flex items-start gap-3 px-4 py-3">
                      <FileTypeIcon
                        name={f.name}
                        className={cn("mt-0.5 shrink-0", issue ? "text-danger-fg" : "text-brand")}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-strong" title={f.name}>
                          {f.name}
                        </p>
                        <p className="text-xs text-muted tabular-nums">{formatSize(f.size, locale, units)}</p>
                        {issue && (
                          <p className="mt-1 flex items-center gap-1 text-xs font-medium text-danger-fg">
                            <CircleAlert size={14} aria-hidden className="shrink-0" />
                            {t(issue === "tooLarge" ? "docs.tooLarge" : "docs.unsupported")}
                          </p>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`${t("upload.remove")}: ${f.name}`}
                        title={t("upload.remove")}
                        disabled={uploading}
                        onClick={() => setFiles((prev) => prev.filter((x) => x !== f))}
                      >
                        <X size={16} aria-hidden />
                      </Button>
                    </li>
                  );
                })}
              </ul>
              {hasInvalid && (
                <Alert tone="danger" className="mt-3">
                  {t("docs.fixFiles")}
                </Alert>
              )}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title={t("docs.details")} subtitle={t("docs.detailsHelp")} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("docType")} required>
              <Select value={docType} onChange={(e) => setDocType(e.target.value as DocType)} disabled={uploading}>
                {DOC_TYPES.map((d) => (
                  <option key={d} value={d}>
                    {t(`doc.${d}` as LabelKey)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("docs.fy")} hint={t("docs.fyHint")} optional>
              <Input value={fy} onChange={(e) => setFy(e.target.value)} disabled={uploading} />
            </Field>
            <Field label={t("language")} required>
              <Select
                value={language}
                onChange={(e) => setLanguage(e.target.value as (typeof LANGUAGES)[number])}
                disabled={uploading}
              >
                {LANGUAGES.map((l) => (
                  <option key={l} value={l}>
                    {t(`lang.${l}` as LabelKey)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field
              label={t("docs.sourceUrl")}
              hint={t("docs.sourceUrlHint")}
              error={sourceUrlChecked && sourceUrlInvalid ? t("docs.sourceUrlInvalid") : undefined}
              optional
            >
              <Input
                type="url"
                inputMode="url"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                onBlur={() => setSourceUrlChecked(true)}
                disabled={uploading}
              />
            </Field>
          </div>

          {canMarkPublic && (
            <Checkbox
              className="mt-5"
              label={t("markPublic")}
              description={t("docs.publicHelp")}
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
              disabled={uploading}
            />
          )}

          <p className="mt-5 flex items-start gap-2 rounded-panel bg-surface-subtle px-3 py-2.5 text-xs text-muted">
            <Building2 size={16} aria-hidden className="mt-px shrink-0 text-brand" />
            <span>
              {t("docs.savedToUnit")} <strong className="font-semibold text-strong">{me.org_unit.name}</strong>
              {canMarkPublic && isPublic ? ` ${t("docs.savedPublic")}` : ""}
            </span>
          </p>
        </Card>
        </div>

        {error && <Alert tone="danger" title={t("ui.error")}>{error}</Alert>}

        {uploading && (
          <div className="space-y-2" aria-live="polite">
            <div className="flex items-center justify-between text-xs text-muted">
              <span>{progress >= 1 ? t("docs.finishing") : t("uploading")}</span>
              <span className="font-semibold text-strong tabular-nums">{pct}%</span>
            </div>
            <ProgressBar value={progress} label={t("docs.uploadProgress")} />
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="submit"
            variant="primary"
            size="lg"
            loading={uploading}
            disabled={files.length === 0 || hasInvalid}
            icon={<UploadCloud size={18} aria-hidden />}
          >
            {uploading ? t("uploading") : t("uploadButton")}
          </Button>
          {files.length > 0 && !uploading && (
            <span className="text-xs text-muted tabular-nums">
              {files.length} {t("filesChosen")}
            </span>
          )}
        </div>
      </form>

      {results.length > 0 && (
        <Card className="mt-6">
          <CardHeader
            title={t("docs.results")}
            actions={
              <ButtonLink href="/documents" variant="outline" size="sm" icon={<ArrowRight size={14} aria-hidden />}>
                {t("docs.goToDocuments")}
              </ButtonLink>
            }
          />
          <ul className="divide-y divide-line rounded-panel border border-line">
            {results.map((r, i) => (
              <li key={`${r.filename}-${i}`} className="flex flex-wrap items-start gap-3 px-4 py-3">
                <FileTypeIcon name={r.filename} className="mt-0.5 shrink-0 text-brand" />
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="min-w-0 truncate text-sm font-medium text-strong" title={r.filename}>
                      {r.filename}
                    </span>
                    <StatusBadge kind="upload" value={r.result} />
                  </div>
                  <p className={cn("text-xs", r.result === "rejected" ? "text-danger-fg" : "text-muted")}>
                    <ResultMessage r={r} />
                  </p>
                </div>
                <ResultLink r={r} />
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ResultMessage({ r }: { r: UploadResult }) {
  const { t } = useT();
  if (r.result === "created") return <>{r.queued ? t("docs.resultQueued") : t("notQueued")}</>;
  if (r.result === "duplicate")
    return (
      <>
        {t("docs.resultDuplicate")} {r.document ? <strong className="font-medium">{r.document.title}</strong> : null}
      </>
    );
  return <>{r.error ?? t("docs.resultRejected")}</>;
}

/**
 * New documents are still being read, so the viewer cannot open them yet: link to the list
 * where progress shows. A duplicate opens in the viewer only once it has been processed.
 */
function ResultLink({ r }: { r: UploadResult }) {
  const { t } = useT();
  if (r.result === "created")
    return (
      <Link href="/documents" className="text-sm font-medium text-brand hover:underline">
        {t("docs.watchProcessing")}
      </Link>
    );
  if (r.result === "duplicate" && r.document) {
    const ready =
      (r.document.status === "PROCESSED" || r.document.status === "NEEDS_REVIEW") && !!r.document.page_count;
    return (
      <Link
        href={ready ? sourceHref({ document_id: r.document.id, page: 1 }, "/upload") : "/documents"}
        className="text-sm font-medium text-brand hover:underline"
      >
        {ready ? t("docs.openDocument") : t("docs.watchProcessing")}
      </Link>
    );
  }
  return null;
}
