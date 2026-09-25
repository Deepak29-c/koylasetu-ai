"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { useMe } from "@/components/AppShell";
import {
  ApiError,
  type DocumentDetail,
  type DocumentStatus,
  fetchPageImage,
  getDocument,
  getPage,
  type PageOut,
} from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

const STATUS_STYLE: Record<DocumentStatus, string> = {
  UPLOADED: "bg-gray-100 text-gray-800",
  PROCESSING: "bg-blue-100 text-blue-800",
  PROCESSED: "bg-green-100 text-green-800",
  NEEDS_REVIEW: "bg-amber-100 text-amber-900",
  FAILED: "bg-red-100 text-red-800",
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const me = useMe();
  const { t } = useT();
  const allowed = me.permissions.includes("view_processing");

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [pageNo, setPageNo] = useState(1);
  const [page, setPage] = useState<PageOut | null>(null);
  const [pageErrorKind, setPageErrorKind] = useState<"processing" | "not-ready" | null>(null);
  const [pageErrorMessage, setPageErrorMessage] = useState<string | null>(null);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const imageUrlRef = useRef<string | null>(null);
  const currentKey = `${id}:${pageNo}`;
  const pageLoading = loadedKey !== currentKey;

  const loadDoc = useCallback(
    () =>
      getDocument(id).then(
        (d) => {
          setDoc(d);
          setDocError(null);
        },
        (e: unknown) => setDocError(e instanceof Error ? e.message : String(e)),
      ),
    [id],
  );

  // Poll while the document is still being processed.
  useEffect(() => {
    if (!allowed) return;
    loadDoc();
    const interval = setInterval(() => {
      setDoc((current) => {
        if (current && current.status !== "UPLOADED" && current.status !== "PROCESSING") {
          clearInterval(interval);
        }
        return current;
      });
      loadDoc();
    }, 5000);
    return () => clearInterval(interval);
  }, [allowed, loadDoc]);

  // Load the current page's text/tables, then its image. Keyed off doc.status (not the
  // whole `doc` object, which gets a new reference on every 5s poll) so this only re-runs
  // when something that actually matters changes — never on every render.
  const docStatus = doc?.status;
  useEffect(() => {
    if (!allowed || !docStatus) return;
    let cancelled = false;
    const key = `${id}:${pageNo}`;
    getPage(id, pageNo).then(
      (p) => {
        if (cancelled) return;
        setPage(p);
        setPageErrorKind(null);
        setPageErrorMessage(null);
        setLoadedKey(key);
        if (p.image_url) {
          fetchPageImage(p.image_url).then(
            (url) => {
              if (cancelled) {
                URL.revokeObjectURL(url);
                return;
              }
              if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
              imageUrlRef.current = url;
              setImageUrl(url);
            },
            () => {},
          );
        } else {
          if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
          imageUrlRef.current = null;
          setImageUrl(null);
        }
      },
      (e: unknown) => {
        if (cancelled) return;
        setPage(null);
        setLoadedKey(key);
        if (e instanceof ApiError && e.status === 404) {
          setPageErrorKind(docStatus === "PROCESSING" ? "processing" : "not-ready");
          setPageErrorMessage(null);
        } else {
          setPageErrorKind(null);
          setPageErrorMessage(e instanceof Error ? e.message : String(e));
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [allowed, docStatus, id, pageNo]);

  useEffect(
    () => () => {
      if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
    },
    [],
  );

  if (!allowed) return <p className="text-gray-600">{t("noPermission")}</p>;
  if (docError) return <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{docError}</p>;
  if (!doc) return <p className="text-gray-500">{t("loading")}</p>;

  const totalPages = page?.page_count ?? doc.page_count;

  return (
    <div className="space-y-4">
      <Link href="/documents" className="text-sm text-brand underline">
        ← {t("backToDocuments")}
      </Link>

      <div className="rounded border bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-semibold">{doc.title}</h1>
            <p className="text-sm text-gray-500">{doc.original_filename}</p>
          </div>
          <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[doc.status]}`}>
            {t(`status.${doc.status}` as LabelKey)}
          </span>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
          <dt className="text-gray-500">{t("type")}</dt>
          <dd>{t(`doc.${doc.doc_type}` as LabelKey)}</dd>
          <dt className="text-gray-500">FY</dt>
          <dd>{doc.fy ?? "—"}</dd>
          <dt className="text-gray-500">{t("pages")}</dt>
          <dd>{doc.page_count ? `${doc.pages_done} / ${doc.page_count}` : "—"}</dd>
          <dt className="text-gray-500">{t("uploadedOn")}</dt>
          <dd>{new Date(doc.created_at).toLocaleString("en-IN")}</dd>
        </dl>
        {doc.error_message && (
          <p className="mt-3 rounded border border-red-300 bg-red-50 p-2 text-sm text-red-800">
            {t("documentFailed")}: {doc.error_message}
          </p>
        )}
      </div>

      {totalPages && totalPages > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded border bg-white p-3">
          <button
            onClick={() => setPageNo((n) => Math.max(1, n - 1))}
            disabled={pageNo <= 1}
            className="rounded border px-3 py-1 text-sm disabled:opacity-40"
          >
            {t("previousPage")}
          </button>
          <span className="text-sm">
            {t("page")} {pageNo} {t("ofPages")} {totalPages}
          </span>
          <button
            onClick={() => setPageNo((n) => Math.min(totalPages, n + 1))}
            disabled={pageNo >= totalPages}
            className="rounded border px-3 py-1 text-sm disabled:opacity-40"
          >
            {t("nextPage")}
          </button>
          <input
            type="number"
            min={1}
            max={totalPages}
            value={pageNo}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (n >= 1 && n <= totalPages) setPageNo(n);
            }}
            className="ml-auto w-20 rounded border px-2 py-1 text-sm"
            aria-label={t("jumpToPage")}
          />
        </div>
      )}

      {pageLoading && !pageErrorKind && !pageErrorMessage && (
        <p className="text-gray-500">{t("loading")}</p>
      )}
      {!pageLoading && (pageErrorKind || pageErrorMessage) && (
        <p className="rounded border bg-gray-50 p-3 text-sm text-gray-700">
          {pageErrorKind === "processing" && t("processingInProgress")}
          {pageErrorKind === "not-ready" && t("noPagesYet")}
          {pageErrorMessage}
        </p>
      )}

      {!pageLoading && page && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded border bg-white p-3">
            {imageUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={imageUrl} alt={`${t("page")} ${pageNo}`} className="w-full rounded border" />
            ) : (
              <p className="text-sm text-gray-500">{t("noPageImage")}</p>
            )}
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
              <span>{page.ocr_used ? t("ocrUsedLabel") : t("textLayerLabel")}</span>
              {page.ocr_confidence != null && (
                <span>
                  {t("ocrConfidence")}: {Math.round(page.ocr_confidence * 100)}%
                </span>
              )}
            </div>
          </div>

          <div className="space-y-4">
            <p className="rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-900">
              {t("factsComingSoon")}
            </p>

            <div className="rounded border bg-white p-3">
              <h2 className="mb-2 font-medium">{t("extractedText")}</h2>
              {page.chunks.length === 0 ? (
                <p className="text-sm text-gray-500">{t("noTextOnPage")}</p>
              ) : (
                <div className="max-h-80 space-y-2 overflow-y-auto text-sm">
                  {page.chunks.map((c) => (
                    <p key={c.id} className="border-b pb-2 whitespace-pre-wrap text-gray-800 last:border-0">
                      {c.text}
                    </p>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded border bg-white p-3">
              <h2 className="mb-2 font-medium">{t("extractedTables")}</h2>
              {page.tables.length === 0 ? (
                <p className="text-sm text-gray-500">{t("noTablesOnPage")}</p>
              ) : (
                <div className="space-y-4">
                  {page.tables.map((tbl) => (
                    <div key={tbl.id} className="overflow-x-auto">
                      {tbl.table_title && <p className="mb-1 text-sm font-medium">{tbl.table_title}</p>}
                      <table className="w-full border-collapse text-xs">
                        <tbody>
                          {tbl.rows_json.map((row, i) => (
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
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
