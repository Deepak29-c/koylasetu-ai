"use client";

import { useEffect, useState } from "react";

import { fetchImageUrl } from "@/lib/api";
import { useT } from "@/lib/i18n";

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

/** A rendered document page with an optional highlight box (a passage or a table cell). */
export default function PageImage({
  imagePath,
  width,
  height,
  highlight,
  alt,
}: {
  imagePath: string | null;
  width: number | null;
  height: number | null;
  highlight?: number[] | null;
  alt: string;
}) {
  const { t } = useT();
  const [image, setImage] = useState<{ path: string; url: string } | null>(null);

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
      () => {},
    );
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [imagePath]);

  const ready = image && image.path === imagePath;
  return (
    <div className="relative self-start overflow-hidden rounded border bg-white">
      {ready ? (
        // eslint-disable-next-line @next/next/no-img-element -- authenticated blob URL
        <img src={image.url} alt={alt} className="block w-full" />
      ) : (
        <div className="flex aspect-[3/4] items-center justify-center text-gray-400">{t("loading")}</div>
      )}
      {ready && highlight && width && height && (
        <div
          className="pointer-events-none absolute rounded-sm border-2 border-amber-500 bg-yellow-300/30"
          style={boxStyle(highlight, width, height)}
        />
      )}
    </div>
  );
}
