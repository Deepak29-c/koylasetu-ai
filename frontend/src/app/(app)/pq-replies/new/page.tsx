"use client";

import Link from "next/link";
import { useState } from "react";

import { useMe } from "@/components/AppShell";
import { draftPqReply, exportReport, type PqBlock, type PqDraftIn, type PqDraftOut, type PqSource } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

function sourceHref(s: PqSource) {
  const chunk = s.chunk_id ? `&chunk=${s.chunk_id}` : "";
  return `/documents/${s.document_id}?page=${s.page}${chunk}`;
}

/** Block text with [S1] markers shown as source chips (document, page). */
function BlockText({ block, sources }: { block: PqBlock; sources: Map<string, PqSource> }) {
  return (
    <p className="leading-7 whitespace-pre-wrap">
      {block.text.split(/(\[S\d+\])/g).map((piece, i) => {
        const s = sources.get(piece.slice(1, -1));
        if (!/^\[S\d+\]$/.test(piece) || !s) return <span key={i}>{piece}</span>;
        return (
          <Link
            key={i}
            href={sourceHref(s)}
            className="mx-0.5 inline-block rounded bg-brand-soft px-1.5 text-xs font-medium text-brand hover:underline"
          >
            {s.id} · {s.document.slice(0, 28)}, p.{s.page}
          </Link>
        );
      })}
    </p>
  );
}

function Table({ table }: { table: NonNullable<PqBlock["table"]> }) {
  return (
    <div className="overflow-x-auto">
      <table className="text-left text-sm">
        <thead className="bg-gray-50 text-gray-600">
          <tr>
            {table.columns.map((c) => (
              <th key={c} className="border px-2 py-1 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="border px-2 py-1">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A random key per question (crypto.randomUUID needs https, so build one from random bytes). */
function newKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

const EMPTY: PqDraftIn = {
  house: "LS",
  q_type: "unstarred",
  q_no: "",
  answer_date: "",
  mp_name: "",
  subject: "",
  question_text: "",
};

export default function NewPqReplyPage() {
  const me = useMe();
  const { t } = useT();
  const [form, setForm] = useState<PqDraftIn>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<PqDraftOut | null>(null);
  // Same key while the question is unchanged, so pressing Generate again after a timeout
  // returns the draft the server already made instead of creating a duplicate.
  const [requestKey, setRequestKey] = useState<string | null>(null);

  if (!me.permissions.includes("edit_reports")) return <p className="text-gray-600">{t("noPermission")}</p>;
  const canExport = me.permissions.includes("export_reports");

  function set<K extends keyof PqDraftIn>(key: K, value: PqDraftIn[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setRequestKey(null);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const key = requestKey ?? newKey();
    setRequestKey(key);
    setBusy(true);
    setError(null);
    setDraft(null);
    try {
      setDraft(
        await draftPqReply({
          ...form,
          q_no: form.q_no || null,
          answer_date: form.answer_date || null,
          mp_name: form.mp_name || null,
          subject: form.subject || null,
          },
          key,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function download(format: "docx" | "pdf") {
    if (!draft) return;
    try {
      await exportReport(draft.report.id, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const blocks = draft?.report.content_json.blocks ?? [];
  const sources = new Map((draft?.report.content_json.sources ?? []).map((s) => [s.id, s]));
  const input = "mt-1 w-full rounded border px-3 py-2";

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("pqTitle")}</h1>
        <p className="text-sm text-gray-600">{t("pqHelp")}</p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
        <div className="grid gap-4 sm:grid-cols-4">
          <label className="block">
            <span className="text-sm font-medium">{t("house")}</span>
            <select value={form.house} onChange={(e) => set("house", e.target.value as "LS" | "RS")} className={input}>
              <option value="LS">{t("house.LS")}</option>
              <option value="RS">{t("house.RS")}</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("questionType")}</span>
            <select
              value={form.q_type}
              onChange={(e) => set("q_type", e.target.value as PqDraftIn["q_type"])}
              className={input}
            >
              <option value="unstarred">{t("qtype.unstarred")}</option>
              <option value="starred">{t("qtype.starred")}</option>
            </select>
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("questionNo")}</span>
            <input value={form.q_no ?? ""} maxLength={16} onChange={(e) => set("q_no", e.target.value)} className={input} />
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("answerDate")}</span>
            <input
              type="date"
              value={form.answer_date ?? ""}
              onChange={(e) => set("answer_date", e.target.value)}
              className={input}
            />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium">{t("mpName")}</span>
            <input value={form.mp_name ?? ""} onChange={(e) => set("mp_name", e.target.value)} className={input} />
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("subject")}</span>
            <input value={form.subject ?? ""} onChange={(e) => set("subject", e.target.value)} className={input} />
          </label>
        </div>
        <label className="block">
          <span className="text-sm font-medium">{t("questionText")}</span>
          <textarea
            required
            minLength={10}
            rows={7}
            value={form.question_text}
            placeholder={t("questionTextPlaceholder")}
            onChange={(e) => set("question_text", e.target.value)}
            className={input}
          />
        </label>
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy || form.question_text.trim().length < 10}
            className="rounded bg-brand px-6 py-2.5 font-medium text-white disabled:opacity-50"
          >
            {t("generateDraft")}
          </button>
          {busy && <span className="text-sm text-gray-600">{t("generating")}</span>}
        </div>
      </form>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}

      {draft && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 rounded border border-green-300 bg-green-50 p-3 text-sm text-green-900">
            <span className="flex-1">{t("draftReady")}</span>
            <Link href={`/reports/${draft.report.id}`} className="font-medium text-brand underline">
              {t("openReport")}
            </Link>
            {canExport && (
              <>
                <button onClick={() => download("docx")} className="rounded border border-brand bg-white px-3 py-1 text-brand">
                  {t("downloadDocx")}
                </button>
                <button onClick={() => download("pdf")} className="rounded border border-brand bg-white px-3 py-1 text-brand">
                  {t("downloadPdf")}
                </button>
              </>
            )}
          </div>
          <p className="text-sm text-gray-600">
            {t("splitBy")}: {t(`split.${draft.split_method}` as LabelKey)}
          </p>
          {(draft.report.content_json.warnings ?? []).map((w) => (
            <p key={w} className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              {w}
            </p>
          ))}

          {blocks.map((b) => (
            <div key={b.id} className="space-y-2 rounded border bg-white p-4">
              <p className="text-sm text-gray-600">
                {b.part && <span className="font-medium">({b.part}) </span>}
                {b.question}
              </p>
              <div className={b.not_found ? "text-amber-900" : ""}>
                <BlockText block={b} sources={sources} />
              </div>
              {b.not_found && <p className="text-xs text-amber-800">{t("partNotFound")}</p>}
              {b.note && <p className="text-xs text-amber-800">{b.note}</p>}
              {b.removed_numbers.length > 0 && (
                <p className="text-xs text-red-800">
                  {t("removedFigures")}: {b.removed_numbers.join(", ")}
                </p>
              )}
              {b.table && (
                <div className="space-y-1">
                  {b.annexure && (
                    <p className="text-xs font-medium text-gray-600">
                      {t("inAnnexure")} {b.annexure}
                    </p>
                  )}
                  <Table table={b.table} />
                </div>
              )}
            </div>
          ))}

          {sources.size > 0 && (
            <div className="space-y-1 rounded border bg-white p-4 text-sm">
              <h2 className="font-semibold">{t("sources")}</h2>
              {[...sources.values()].map((s) => (
                <p key={s.id}>
                  <span className="font-medium">{s.id}</span> {s.document}, {t("page")} {s.page}{" "}
                  <Link href={sourceHref(s)} className="text-brand underline">
                    {t("openPage")}
                  </Link>
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
