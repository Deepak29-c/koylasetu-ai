"use client";

import Link from "next/link";

import { useRef, useState } from "react";

import { useMe } from "@/components/AppShell";
import { type DocType, type UploadResult, uploadDocuments } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

const DOC_TYPES: DocType[] = ["annual_report", "coal_inventory", "monthly_stats", "pq_answer", "other"];
const LANGUAGES = ["en", "hi", "mixed"] as const;
const ACCEPT = ".pdf,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.tif,.tiff,.docx";

export default function UploadPage() {
  const me = useMe();
  const { t } = useT();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [docType, setDocType] = useState<DocType>("annual_report");
  const [fy, setFy] = useState("");
  const [language, setLanguage] = useState<(typeof LANGUAGES)[number]>("en");
  const [isPublic, setIsPublic] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  if (!me.permissions.includes("upload_documents")) {
    return <p className="text-gray-600">{t("noPermission")}</p>;
  }
  const canMarkPublic = ["CIL_HQ", "MINISTRY"].includes(me.org_unit.code) || me.roles.includes("admin");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("doc_type", docType);
    if (fy.trim()) form.append("fy", fy.trim());
    form.append("language", language);
    form.append("is_public", String(isPublic));
    if (sourceUrl.trim()) form.append("source_url", sourceUrl.trim());

    setError(null);
    setResults([]);
    setProgress(0);
    try {
      setResults(await uploadDocuments(form, setProgress));
      setFiles([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setProgress(null);
    }
  }

  const resultStyle: Record<UploadResult["result"], string> = {
    created: "border-green-300 bg-green-50 text-green-900",
    duplicate: "border-amber-300 bg-amber-50 text-amber-900",
    rejected: "border-red-300 bg-red-50 text-red-900",
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("uploadTitle")}</h1>
        <p className="text-sm text-gray-600">{t("uploadHelp")}</p>
      </div>

      <form onSubmit={onSubmit} className="space-y-5 rounded border bg-white p-6">
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            setFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)]);
          }}
          className={`cursor-pointer rounded border-2 border-dashed p-8 text-center ${
            dragging ? "border-brand bg-brand-soft" : "border-gray-300 hover:border-brand"
          }`}
        >
          <p className="font-medium">{t("dropHere")}</p>
          {files.length > 0 && (
            <div className="mt-3 space-y-1 text-sm text-gray-700">
              <p className="text-gray-600">
                {files.length} {t("filesChosen")}
              </p>
              <ul className="flex flex-wrap justify-center gap-2">
                {files.map((f, i) => (
                  <li key={`${f.name}-${i}`} className="flex items-center gap-1 rounded border bg-white px-2 py-1">
                    <span>{f.name}</span>
                    <button
                      type="button"
                      aria-label={`${t("upload.remove")}: ${f.name}`}
                      // The dropzone around this opens the file picker on click.
                      onClick={(e) => {
                        e.stopPropagation();
                        setFiles((prev) => prev.filter((_, j) => j !== i));
                      }}
                      className="px-1 text-gray-500 hover:text-red-700"
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => {
              setFiles((prev) => [...prev, ...Array.from(e.target.files ?? [])]);
              e.target.value = "";
            }}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium">{t("docType")}</span>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocType)}
              className="mt-1 w-full rounded border px-3 py-2"
            >
              {DOC_TYPES.map((d) => (
                <option key={d} value={d}>
                  {t(`doc.${d}` as LabelKey)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("fy")}</span>
            <input
              value={fy}
              onChange={(e) => setFy(e.target.value)}
              placeholder="FY 2024-25"
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("language")}</span>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as (typeof LANGUAGES)[number])}
              className="mt-1 w-full rounded border px-3 py-2"
            >
              {LANGUAGES.map((l) => (
                <option key={l} value={l}>
                  {t(`lang.${l}` as LabelKey)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("sourceUrl")}</span>
            <input
              type="url"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://coal.gov.in/…"
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
        </div>

        {canMarkPublic && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isPublic} onChange={(e) => setIsPublic(e.target.checked)} />
            {t("markPublic")}
          </label>
        )}

        {progress !== null && (
          <div className="h-2 w-full overflow-hidden rounded bg-gray-200">
            <div className="h-full bg-brand transition-all" style={{ width: `${progress * 100}%` }} />
          </div>
        )}
        {error && <p className="text-sm text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={files.length === 0 || progress !== null}
          className="rounded bg-brand px-6 py-2.5 font-medium text-white disabled:opacity-50"
        >
          {progress !== null ? t("uploading") : t("uploadButton")}
        </button>
      </form>

      {results.length > 0 && (
        <ul className="space-y-2">
          {results.map((r, i) => (
            <li key={i} className={`rounded border p-3 text-sm ${resultStyle[r.result]}`}>
              <span className="font-medium">{r.filename}</span> — {t(r.result)}
              {r.error && <span>: {r.error}</span>}
              {r.document && (
                <Link href={`/documents/${r.document.id}`} className="ml-2 underline">
                  {t("upload.openExisting")}
                </Link>
              )}
              {r.result === "created" && !r.queued && <p className="mt-1">{t("notQueued")}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
