"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { api, fetchImageUrl, type PageData } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function DocumentViewerPage() {
  return (
    <Suspense>
      <Viewer />
    </Suspense>
  );
}

/** Box in page coordinates -> CSS percentages over the rendered page image. */
function boxStyle(bbox: number[], width: number, height: number): React.CSSProperties {
  const [x0, y0, x1, y1] = bbox;
  return {
    left: `${(x0 / width) * 100}%`,
    top: `${(y0 / height) * 100}%`,
    width: `${((x1 - x0) / width) * 100}%`,
    height: `${((y1 - y0) / height) * 100}%`,
  };
}

function Viewer() {
  const { t } = useT();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const pageNo = Math.max(1, Number(search.get("page") ?? 1) || 1);
  const selected = search.get("chunk");

  const [data, setData] = useState<PageData | null>(null);
  const [image, setImage] = useState<{ page: number; url: string } | null>(null);
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

  const imagePath = data?.page_no === pageNo ? data.image_url : null;
  useEffect(() => {
    if (!imagePath) return;
    let url: string | null = null;
    let cancelled = false;
    fetchImageUrl(`${imagePath}?dpi=110`).then(
      (u) => {
        url = u;
        if (cancelled) URL.revokeObjectURL(u);
        else setImage({ page: pageNo, url: u });
      },
      () => {},
    );
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [imagePath, pageNo]);

  function go(page: number, chunk?: string) {
    const q = new URLSearchParams({ page: String(page) });
    if (chunk) q.set("chunk", chunk);
    router.replace(`/documents/${id}?${q}`);
  }

  if (error) return <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>;
  if (!data || data.page_no !== pageNo) return <p className="text-gray-500">{t("loading")}</p>;

  const total = data.page_count ?? pageNo;
  const canDraw = data.width && data.height;
  const highlight = data.chunks.find((c) => c.id === selected);

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
        <div className="relative self-start overflow-hidden rounded border bg-white">
          {image?.page === pageNo ? (
            // eslint-disable-next-line @next/next/no-img-element -- authenticated blob URL
            <img src={image.url} alt={`${t("page")} ${pageNo}`} className="block w-full" />
          ) : (
            <div className="flex aspect-[3/4] items-center justify-center text-gray-400">{t("loading")}</div>
          )}
          {canDraw && highlight?.bbox && image?.page === pageNo && (
            <div
              className="pointer-events-none absolute rounded-sm border-2 border-amber-500 bg-yellow-300/30"
              style={boxStyle(highlight.bbox, data.width!, data.height!)}
            />
          )}
        </div>

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

      <Link href="/ask" className="text-sm text-brand underline">
        ← {t("ask")}
      </Link>
    </div>
  );
}
