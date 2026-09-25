import { cn } from "@/lib/cn";

/** A thin determinate progress bar. `value` is a fraction from 0 to 1. */
export default function ProgressBar({
  value,
  label,
  valueText,
  size = "md",
  className,
}: {
  value: number;
  /** Accessible name of the bar. */
  label: string;
  /** Read out instead of the percent, e.g. "3 / 12". */
  valueText?: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-valuetext={valueText}
      className={cn(
        "w-full overflow-hidden rounded-full bg-surface-sunken",
        size === "sm" ? "h-1.5" : "h-2.5",
        className,
      )}
    >
      <div className="h-full rounded-full bg-brand transition-[width] duration-300" style={{ width: `${pct}%` }} />
    </div>
  );
}
