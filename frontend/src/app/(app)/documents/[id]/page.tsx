"use client";

import { ExternalLink, Info, ScanText } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import PageImage, { type PageZoom } from "@/components/PageImage";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import PageHeader from "@/components/ui/PageHeader";
import RecordList, { type RecordItem } from "@/components/ui/RecordList";
import { Skeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import ChunkList from "@/components/viewer/ChunkList";
import PageNav from "@/components/viewer/PageNav";
import PageTables from "@/components/viewer/PageTables";
import ZoomControl from "@/components/viewer/ZoomControl";
import { api, type DocumentRow, type PageData } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { safeInternalPath } from "@/lib/sources";

export default function DocumentViewerPage() {
  return (
    <Suspense>
      <Viewer />
    </Suspense>
  );
}

/**
 * Where the back button goes. `from` is a path inside the app ("/ask?qa=…", "/reports/…");
 * older links carry only a saved answer's id. Anything else (another site, "//host")
 * falls back to the document list.
 */
/** Only http(s) links are shown; source_url is free text typed at upload. */
function isWebLink(url: string): boolean {
  return /^https?:\/\//i.test(url);
}

function backTarget(from: string | null): { href: string; label: LabelKey } {
  const path = safeInternalPath(from);
  if (path) return { href: path, label: path.startsWith("/ask") ? "qa.backToAnswer" : "ui.back" };
  if (from && /^[0-9a-f-]{8,64}$/i.test(from)) return { href: `/ask?qa=${from}`, label: "qa.backToAnswer" };
  return { href: "/documents", label: "documents" };
}

function Viewer() {
  const { t, locale } = useT();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const pageNo = Math.max(1, Number(search.get("page") ?? 1) || 1);
  const selected = search.get("chunk");
  const from = search.get("from");
  // box=x0,y0,x1,y1: highlight a table cell (a figure's source) instead of a passage
  const box = search.get("box")?.split(",").map(Number).filter((n) => !Number.isNaN(n));

  const [data, setData] = useState<PageData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  // Document details need a permission not every reader has, so they are optional.
  const [doc, setDoc] = useState<DocumentRow | null>(null);
  const [zoom, setZoom] = useState<PageZoom>("fit");

  useEffect(() => {
    let cancelled = false;
    api<PageData>(`/documents/${id}/pages/${pageNo}`).then(
      (d) => {
        if (cancelled) return;
        setData(d);
        setError(null);
      },
      (e: unknown) => !cancelled && setError(errorText(e)),
    );
    return () => {
      cancelled = true;
    };
  }, [id, pageNo, attempt]);

  useEffect(() => {
    let cancelled = false;
    api<DocumentRow>(`/documents/${id}`).then(
      (d) => !cancelled && setDoc(d),
      () => {},
    );
    return () => {
      cancelled = true;
    };
  }, [id]);

  function go(page: number, chunk?: string) {
    const q = new URLSearchParams({ page: String(page) });
    if (chunk) q.set("chunk", chunk);
    // Keep the way back while moving around the document.
    if (from) q.set("from", from);
    router.replace(`/documents/${id}?${q}`);
  }

  const back = backTarget(from);
  const title = data?.document_title ?? doc?.title;
  const total = data?.page_count ?? doc?.page_count ?? pageNo;
  // A page change keeps the header and navigation in place while the new page loads.
  const current = data && data.page_no === pageNo ? data : null;

  const header = (
    <PageHeader
      className="mb-0"
      title={title ?? <Skeleton className="h-7 w-72 max-w-full" />}
      documentTitle={title ?? t("documents")}
      breadcrumbs={[{ label: t("documents"), href: "/documents" }]}
      back={{ href: back.href, label: t(back.label) }}
      meta={doc && <StatusBadge kind="document" value={doc.status} />}
      actions={
        data?.source_url && isWebLink(data.source_url) && (
          <a
            href={data.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-brand hover:underline"
          >
            <ExternalLink size={16} aria-hidden />
            {t("viewer.sourceLink")}
          </a>
        )
      }
    />
  );

  if (error)
    return (
      <div className="space-y-6">
        {header}
        <Alert
          tone="danger"
          title={t("ui.somethingWrong")}
          action={
            <Button
              variant="danger-outline"
              size="sm"
              onClick={() => {
                setError(null);
                setAttempt((n) => n + 1);
              }}
            >
              {t("retry")}
            </Button>
          }
        >
          {error}
        </Alert>
      </div>
    );

  const highlight = box?.length === 4 ? box : current?.chunks.find((c) => c.id === selected)?.bbox;

  const details: RecordItem[] = [];
  if (doc) {
    details.push(
      { label: t("type"), value: t(`doc.${doc.doc_type}` as LabelKey) },
      { label: t("fyShort"), value: doc.fy },
      { label: t("language"), value: t(`lang.${doc.language}` as LabelKey) || doc.language },
      { label: t("pages"), value: doc.page_count },
      { label: t("uploadedOn"), value: formatDateTime(doc.created_at, locale) },
      { label: t("viewer.visibility"), value: doc.is_public ? t("viewer.public") : t("viewer.unitOnly") },
      { label: t("viewer.fileName"), value: doc.original_filename, mono: true, wide: true },
    );
  }
  if (current)
    details.push({
      label: t("viewer.textLayer"),
      value: current.has_text_layer ? t("viewer.textLayerYes") : t("viewer.textLayerNo"),
    });
  if (data?.source_url && isWebLink(data.source_url))
    details.push({
      label: t("viewer.sourceLink"),
      wide: true,
      value: (
        <a href={data.source_url} target="_blank" rel="noreferrer" className="text-brand hover:underline">
          {data.source_url.replace(/^https?:\/\//, "")}
        </a>
      ),
    });

  const ocrPercent = current?.ocr_confidence != null ? Math.round(current.ocr_confidence * 100) : null;

  return (
    <div className="space-y-6">
      {header}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Card aria-label={`${t("page")} ${pageNo}`} className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <PageNav page={pageNo} total={total} onGo={(p) => go(p)} />
            <ZoomControl value={zoom} onChange={setZoom} />
          </div>
          {current?.ocr_used && (
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
              <Badge
                tone={ocrPercent !== null && ocrPercent >= 80 ? "info" : "warning"}
                icon={<ScanText size={14} aria-hidden />}
              >
                {t("ocrPage")} · {t("ocrConfidence")} {ocrPercent !== null ? `${ocrPercent}%` : "–"}
              </Badge>
              <span>{t("viewer.ocrHelp")}</span>
            </div>
          )}
          {current ? (
            <PageImage
              imagePath={current.image_url}
              width={current.width}
              height={current.height}
              highlight={highlight}
              alt={`${title ?? ""}, ${t("page")} ${pageNo}`}
              zoom={zoom}
            />
          ) : (
            <div role="status" aria-label={t("loading")} className="aspect-[3/4] w-full">
              <Skeleton className="h-full w-full rounded-panel" />
            </div>
          )}
        </Card>

        <div className="min-w-0 space-y-6">
          {current ? (
            <ChunkList chunks={current.chunks} selected={selected} onSelect={(c) => go(pageNo, c)} />
          ) : (
            <Card>
              <div role="status" aria-label={t("loading")} className="space-y-3">
                <Skeleton className="h-5 w-40" />
                {Array.from({ length: 4 }, (_, i) => (
                  <Skeleton key={i} className="h-16 w-full rounded-panel" />
                ))}
              </div>
            </Card>
          )}

          {details.length > 0 && (
            <Card aria-labelledby="doc-details">
              <CardHeader id="doc-details" icon={<Info />} title={t("viewer.details")} />
              <RecordList items={details} columns={2} />
            </Card>
          )}
        </div>
      </div>

      {current && <PageTables tables={current.tables} />}
    </div>
  );
}
