"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import { api, type DocumentRow, type DocumentStatus } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

const STATUS_STYLE: Record<DocumentStatus, string> = {
  UPLOADED: "bg-gray-100 text-gray-800",
  PROCESSING: "bg-blue-100 text-blue-800",
  PROCESSED: "bg-green-100 text-green-800",
  NEEDS_REVIEW: "bg-amber-100 text-amber-900",
  FAILED: "bg-red-100 text-red-800",
};

export default function DocumentsPage() {
  const me = useMe();
  const { t } = useT();
  const [docs, setDocs] = useState<DocumentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const allowed = me.permissions.includes("view_processing");

  const load = useCallback(
    () =>
      api<DocumentRow[]>("/documents").then(
        (rows) => {
          setDocs(rows);
          setError(null);
        },
        (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  );

  // Poll while the page is open so officers see processing progress.
  useEffect(() => {
    if (!allowed) return;
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [allowed, load]);

  if (!allowed) return <p className="text-gray-600">{t("noPermission")}</p>;

  async function retry(id: string) {
    try {
      await api(`/documents/${id}/retry`, { method: "POST" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t("documents")}</h1>
      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {docs === null && !error && <p className="text-gray-500">{t("loading")}</p>}
      {docs?.length === 0 && <p className="text-gray-600">{t("noDocuments")}</p>}
      {docs && docs.length > 0 && (
        <div className="overflow-x-auto rounded border bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2 font-medium">{t("title")}</th>
                <th className="px-4 py-2 font-medium">{t("type")}</th>
                <th className="px-4 py-2 font-medium">FY</th>
                <th className="px-4 py-2 font-medium">{t("status")}</th>
                <th className="px-4 py-2 font-medium">{t("pages")}</th>
                <th className="px-4 py-2 font-medium">{t("uploadedOn")}</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-t align-top">
                  <td className="px-4 py-2">
                    <Link href={`/documents/${d.id}`} className="font-medium text-brand hover:underline">
                      {d.title}
                    </Link>
                    {d.error_message && <div className="text-xs text-red-700">{d.error_message}</div>}
                  </td>
                  <td className="px-4 py-2">{t(`doc.${d.doc_type}` as LabelKey)}</td>
                  <td className="px-4 py-2">{d.fy ?? "—"}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[d.status]}`}>
                      {t(`status.${d.status}` as LabelKey)}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    {d.page_count ? `${d.pages_done} / ${d.page_count}` : "—"}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap">
                    {new Date(d.created_at).toLocaleString("en-IN")}
                  </td>
                  <td className="px-4 py-2">
                    {(d.status === "FAILED" || d.status === "UPLOADED") &&
                      me.permissions.includes("upload_documents") && (
                        <button onClick={() => retry(d.id)} className="text-brand underline">
                          {t("retry")}
                        </button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
