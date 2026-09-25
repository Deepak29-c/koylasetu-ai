"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import PageImage from "@/components/PageImage";
import { api, type PageData } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function DocumentViewerPage() {
  return (
    <Suspense>
      <Viewer />
    </Suspense>
  );
}

function Viewer() {
  const { t } = useT();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const pageNo = Math.max(1, Number(search.get("page") ?? 1) || 1);
  const selected = search.get("chunk");
  // box=x0,y0,x1,y1: highlight a table cell (a figure's source) instead of a passage
  const box = search.get("box")?.split(",").map(Number).filter((n) => !Number.isNaN(n));

  const [data, setData] = useState<PageData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<PageData>(`/documents/${id}/pages/${pageNo}`).then(
      (d) => {
        if (cancelled) return;
        setData(d);
        setError(null);
      },
      (e: unknown) => !cancelled && setError(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      cancelled = true;
    };
  }, [id, pageNo]);

  function go(page: number, chunk?: string) {
    const q = new URLSearchParams({ page: String(page) });
    if (chunk) q.set("chunk", chunk);
    router.replace(`/documents/${id}?${q}`);
  }

  if (error) return <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>;
  if (!data || data.page_no !== pageNo) return <p className="text-gray-500">{t("loading")}</p>;

  const total = data.page_count ?? pageNo;
  const highlight = box?.length === 4 ? box : data.chunks.find((c) => c.id === selected)?.bbox;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h1 className="text-xl font-semibold">{data.document_title}</h1>
        {data.source_url && (
          <a href={data.source_url} target="_blank" rel="noreferrer" className="text-sm text-brand underline">
            {data.source_url.replace(/^https?:\/\//, "").slice(0, 60)}
          </a>
        )}
        <div className="ml-auto flex items-center gap-2 text-sm">
          <button
            disabled={pageNo <= 1}
            onClick={() => go(pageNo - 1)}
            className="rounded border bg-white px-3 py-1 disabled:opacity-40"
          >
            {t("prev")}
          </button>
          <span>
            {t("page")} {pageNo} {t("of")} {total}
          </span>
          <button
            disabled={pageNo >= total}
            onClick={() => go(pageNo + 1)}
            className="rounded border bg-white px-3 py-1 disabled:opacity-40"
          >
            {t("next")}
          </button>
        </div>
      </div>

      {data.ocr_used && (
        <p className="text-sm text-amber-800">
          {t("ocrPage")} · {t("ocrConfidence")}{" "}
          {data.ocr_confidence != null ? `${Math.round(data.ocr_confidence * 100)}%` : "—"}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <PageImage
          imagePath={data.image_url}
          width={data.width}
          height={data.height}
          highlight={highlight}
          alt={`${t("page")} ${pageNo}`}
        />

        <div className="space-y-4">
          <section>
            <h2 className="mb-2 font-semibold">{t("pageText")}</h2>
            <div className="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
              {data.chunks.map((c) => (
                <button
                  key={c.id}
                  onClick={() => go(pageNo, c.id)}
                  className={`block w-full rounded border p-2 text-left text-sm whitespace-pre-wrap ${
                    c.id === selected ? "border-amber-500 bg-yellow-50" : "bg-white hover:border-brand"
                  }`}
                >
                  {c.text}
                </button>
              ))}
            </div>
          </section>

          {data.tables.length > 0 && (
            <section>
              <h2 className="mb-2 font-semibold">{t("tablesOnPage")}</h2>
              {data.tables.map((tb) => (
                <div key={tb.id} className="mb-3 overflow-x-auto rounded border bg-white">
                  <table className="text-xs">
                    <tbody>
                      {tb.rows_json.map((row, r) => (
                        <tr key={r} className={r === 0 ? "bg-gray-50 font-medium" : "border-t"}>
                          {row.map((cell, c) => (
                            <td key={c} className="px-2 py-1 whitespace-nowrap">
                              {cell}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </section>
          )}
        </div>
      </div>

      {/* Carries the answer this page was opened from, so "back" restores it (#40). */}
      <Link
        href={search.get("from") ? `/ask?qa=${search.get("from")}` : "/ask"}
        className="text-sm text-brand underline"
      >
        ← {search.get("from") ? t("qa.backToAnswer") : t("ask")}
      </Link>
    </div>
  );
}
