"use client";

import Link from "next/link";
import { useState } from "react";

import { useMe } from "@/components/AppShell";
import { type DraftSection, type DraftSource, exportReport, type ReportDraftOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

/** A random key per request (crypto.randomUUID needs https, so build one from random bytes). */
export function newKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function sourceHref(s: DraftSource) {
  return `/documents/${s.document_id}?page=${s.page}`;
}

function Chip({ s }: { s: DraftSource }) {
  return (
    <Link
      href={sourceHref(s)}
      className="mx-0.5 inline-block rounded bg-brand-soft px-1.5 text-xs font-medium text-brand hover:underline"
    >
      {s.id} · {s.document.slice(0, 28)}, p.{s.page}
    </Link>
  );
}

/** Text with [S1] markers shown as source chips (document, page). */
function WithChips({ text, sources }: { text: string; sources: Map<string, DraftSource> }) {
  return (
    <>
      {text.split(/(\[S\d+\])/g).map((piece, i) => {
        const s = sources.get(piece.slice(1, -1));
        return /^\[S\d+\]$/.test(piece) && s ? <Chip key={i} s={s} /> : <span key={i}>{piece}</span>;
      })}
    </>
  );
}

function Table({ table, sources }: { table: NonNullable<DraftSection["table"]>; sources: Map<string, DraftSource> }) {
  const sourceCol = table.columns.indexOf("Source");
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
                <td key={j} className={`border px-2 py-1 ${j > 0 && j !== sourceCol ? "text-right tabular-nums" : ""}`}>
                  {j === sourceCol
                    ? cell.split(", ").map((id) => {
                        const s = sources.get(id);
                        return s ? <Chip key={id} s={s} /> : <span key={id}>{id}</span>;
                      })
                    : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A generated monthly report / briefing note: sections, tables, source chips, downloads. */
export default function ReportDraftView({ draft, filePrefix }: { draft: ReportDraftOut; filePrefix: string }) {
  const me = useMe();
  const { t } = useT();
  const [error, setError] = useState<string | null>(null);
  const content = draft.report.content_json;
  const sources = new Map((content.sources ?? []).map((s) => [s.id, s]));
  const canExport = me.permissions.includes("export_reports");

  async function download(format: "docx" | "pdf") {
    try {
      setError(null);
      await exportReport(draft.report.id, format, filePrefix);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
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
      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {(content.warnings ?? []).map((w) => (
        <p key={w} className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {w}
        </p>
      ))}

      <div className="space-y-5 rounded border bg-white p-5">
        <div className="text-center">
          <h2 className="font-semibold">{content.title}</h2>
          {content.subtitle && <p className="text-sm text-gray-700">{content.subtitle}</p>}
        </div>
        {(content.sections ?? []).map((s) => (
          <section key={s.id} className="space-y-2">
            {s.heading && <h3 className="font-semibold">{s.heading}</h3>}
            {s.bullets ? (
              <ul className="list-disc space-y-1 pl-5 leading-7">
                {s.lines.map((line, i) => (
                  <li key={i}>
                    <WithChips text={line} sources={sources} />
                  </li>
                ))}
              </ul>
            ) : (
              s.lines.map((line, i) => (
                <p key={i} className="leading-7">
                  <WithChips text={line} sources={sources} />
                </p>
              ))
            )}
            {s.removed_numbers.length > 0 && (
              <p className="text-xs text-red-800">
                {t("removedFigures")}: {s.removed_numbers.join(", ")}
              </p>
            )}
            {s.table && <Table table={s.table} sources={sources} />}
            {s.notes.map((n) => (
              <p key={n} className="text-xs text-gray-600">
                {n}
              </p>
            ))}
          </section>
        ))}
      </div>

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
  );
}
