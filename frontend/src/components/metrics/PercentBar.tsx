"use client";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

import { pctText } from "./format";

type BarTone = "brand" | "success" | "danger";

const fills: Record<BarTone, string> = {
  brand: "bg-brand",
  success: "bg-success",
  danger: "bg-danger",
};

/** A horizontal bar for one percentage. A missing value shows an empty track and "n/a". */
export default function PercentBar({
  label,
  value,
  tone = "brand",
  className,
}: {
  label: string;
  value: number | null;
  tone?: BarTone;
  className?: string;
}) {
  const { t, locale } = useT();
  const clamped = value === null ? 0 : Math.min(100, Math.max(0, value));
  const text = pctText(value, t, locale);
  return (
    <div className={cn("space-y-1.5", className)}>
      <div aria-hidden className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-foreground">{label}</span>
        <span className="font-semibold text-strong tabular-nums">{text}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value === null ? undefined : clamped}
        aria-valuetext={text}
        className="h-2 w-full overflow-hidden rounded-full bg-surface-sunken"
      >
        <div className={cn("h-full rounded-full", fills[tone])} style={{ width: `${clamped}%` }} />
      </div>
    </div>
  );
}
