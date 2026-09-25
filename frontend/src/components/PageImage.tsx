"use client";

import { useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { fetchImageUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { useT } from "@/lib/i18n";

/** "fit" fills the available width; a number scales the image's own pixel size. */
export type PageZoom = "fit" | 1 | 1.5;

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

type Loaded = { path: string; url: string } | { path: string; error: string };

/** A rendered document page with an optional highlight box (a passage or a table cell). */
export default function PageImage({
  imagePath,
  width,
  height,
  highlight,
  alt,
  zoom = "fit",
}: {
  imagePath: string | null;
  width: number | null;
  height: number | null;
  highlight?: number[] | null;
  alt: string;
  zoom?: PageZoom;
}) {
  const { t } = useT();
  const [image, setImage] = useState<Loaded | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [naturalWidth, setNaturalWidth] = useState<number | null>(null);

  useEffect(() => {
    if (!imagePath) return;
    let url: string | null = null;
    let cancelled = false;
    fetchImageUrl(`${imagePath}?dpi=110`).then(
      (u) => {
        url = u;
        if (cancelled) URL.revokeObjectURL(u);
        else setImage({ path: imagePath, url: u });
      },
      (e: unknown) => {
        if (!cancelled) setImage({ path: imagePath, error: errorText(e) });
      },
    );
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [imagePath, attempt]);

  if (!imagePath) return <Alert tone="info">{t("viewer.noImage")}</Alert>;

  const current = image && image.path === imagePath ? image : null;
  if (current && "error" in current)
    return (
      <Alert
        tone="danger"
        title={t("viewer.imageFailed")}
        action={
          <Button
            variant="danger-outline"
            size="sm"
            onClick={() => {
              setImage(null);
              setAttempt((n) => n + 1);
            }}
          >
            {t("retry")}
          </Button>
        }
      >
        {current.error}
      </Alert>
    );

  const ratio = width && height ? `${width} / ${height}` : "3 / 4";
  if (!current)
    return (
      // The placeholder keeps the page's own shape, so nothing jumps when it arrives.
      <div role="status" aria-label={t("loading")} className="w-full" style={{ aspectRatio: ratio }}>
        <Skeleton className="h-full w-full rounded-panel" />
      </div>
    );

  // The rendered width at the chosen zoom; unknown until the image has loaded once.
  const zoomWidth = zoom !== "fit" && naturalWidth ? naturalWidth * zoom : null;
  return (
    <div className="max-w-full overflow-auto rounded-panel border border-line bg-surface">
      <div
        className={cn("relative", zoomWidth ? "max-w-none" : "w-full")}
        style={zoomWidth ? { width: `${zoomWidth}px` } : undefined}
      >
        {/* eslint-disable-next-line @next/next/no-img-element -- authenticated blob URL */}
        <img
          src={current.url}
          alt={alt}
          className="block w-full"
          onLoad={(e) => setNaturalWidth(e.currentTarget.naturalWidth)}
        />
        {highlight && width && height && (
          <div
            aria-hidden
            className="pointer-events-none absolute rounded-sm border-2 border-warning-fg bg-warning-border/40"
            style={boxStyle(highlight, width, height)}
          />
        )}
      </div>
    </div>
  );
}
