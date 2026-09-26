"use client";

import { ExternalLink, Layers } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import { type DepthView, getDepth } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { depthLabel, JHARIA_BAND, periodLabel, segmentWidths } from "@/lib/mapView";
import { sourceHref } from "@/lib/sources";

const SEGMENTS = [
  { key: "measured", label: "map.category.measured", color: "var(--map-5)" },
  { key: "indicated", label: "map.category.indicated", color: "var(--map-3)" },
  { key: "inferred", label: "map.category.inferred", color: "var(--accent)" },
] as const;

/** A state's (or all India's) coal resources by depth: one bar per depth band, shallow at
 * the top like a cross-section, split into Measured / Indicated / Inferred. */
export default function DepthColumn({ state, period }: { state: string | null; period: string | null }) {
  const { t, locale } = useT();
  const [data, setData] = useState<DepthView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getDepth({ state: state ?? undefined, period: period ?? undefined }).then(
      (d) => live && (setData(d), setError(null)),
      (e) => live && setError(errorText(e)),
    );
    return () => {
      live = false;
    };
  }, [state, period]);

  const title = state ? t("map.depthTitle") : t("map.depthTitleIndia");
  if (error) return <p className="mt-6 text-sm text-danger">{error}</p>;
  if (!data) return <Skeleton className="mt-6 h-48 rounded-panel" />;
  if (data.bands.length === 0)
    return (
      <div className="mt-6">
        <CardHeader icon={<Layers />} title={title} level={3} />
        <EmptyState compact title={t("map.depthEmpty")}>
          {t("map.depthEmptyBody")}
        </EmptyState>
      </div>
    );

  const widths = segmentWidths(data.bands);
  const source = data.bands[0].sources[0];
  return (
    <div className="mt-6 border-t border-line pt-5">
      <CardHeader
        icon={<Layers />}
        title={title}
        subtitle={`${periodLabel(data.period, "coal_resource", t("map.asOn"))} · ${t("map.unitNote")} ${data.unit}`}
        level={3}
      />
      <ol className="space-y-3" aria-label={title}>
        {data.bands.map((b, i) => (
          <li key={b.depth_range}>
            <div className="flex items-baseline justify-between gap-2 text-xs">
              <span className="font-semibold text-strong">
                {depthLabel(b.depth_range)}
                {b.depth_range === JHARIA_BAND && <span className="font-normal text-subtle"> · {t("map.jhariaOnly")}</span>}
              </span>
              <span className="tabular-nums text-muted">
                {formatNumber(b.total, locale, 2)}{" "}
                <span className="text-subtle">
                  ({data.total ? formatNumber((100 * b.total) / data.total, locale, 1) : 0}%)
                </span>
              </span>
            </div>
            <div
              className="mt-1 flex h-4 overflow-hidden rounded-sm bg-surface-sunken"
              role="img"
              aria-label={SEGMENTS.map((s) => `${t(s.label)} ${formatNumber(b[s.key], locale, 2)}`).join(", ")}
            >
              {SEGMENTS.map((s) => (
                <span
                  key={s.key}
                  style={{ width: `${widths[i][s.key]}%`, background: s.color }}
                  title={`${t(s.label)}: ${formatNumber(b[s.key], locale, 2)} ${data.unit}`}
                />
              ))}
            </div>
          </li>
        ))}
      </ol>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label={t("map.legend")}>
        {SEGMENTS.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span aria-hidden className="inline-block size-3 rounded-sm border border-line" style={{ background: s.color }} />
            {t(s.label)}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-subtle">
        {t("map.depthNote")}{" "}
        <Link
          href={sourceHref({ document_id: source.document_id, page: source.page_no }, "/map")}
          className="inline-flex items-center gap-1 text-brand underline hover:text-brand-hover"
        >
          {source.document_title}, {t("map.page")} {source.page_no}
          <ExternalLink size={12} aria-hidden />
        </Link>
      </p>
    </div>
  );
}
