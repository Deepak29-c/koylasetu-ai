"use client";

import type { PageZoom } from "@/components/PageImage";
import { cn } from "@/lib/cn";
import { type LabelKey, useT } from "@/lib/i18n";

const OPTIONS: { value: PageZoom; label: LabelKey }[] = [
  { value: "fit", label: "viewer.zoomFit" },
  { value: 1, label: "viewer.zoom100" },
  { value: 1.5, label: "viewer.zoom150" },
];

/** Fit width / 100% / 150% for the page image. */
export default function ZoomControl({ value, onChange }: { value: PageZoom; onChange: (z: PageZoom) => void }) {
  const { t } = useT();
  return (
    <div role="group" aria-label={t("viewer.zoom")} className="inline-flex rounded-full bg-surface-sunken p-0.5">
      {OPTIONS.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={String(o.value)}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(o.value)}
            className={cn(
              "h-7 rounded-full px-3 text-xs font-semibold transition-colors",
              on ? "bg-surface text-brand shadow-pill" : "text-muted hover:text-brand",
            )}
          >
            {t(o.label)}
          </button>
        );
      })}
    </div>
  );
}
