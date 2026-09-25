import Link from "next/link";

import { cn } from "@/lib/cn";

import type { Tone } from "./Badge";

const iconTone: Record<Tone, string> = {
  success: "bg-success-bg text-success-fg",
  warning: "bg-warning-bg text-warning-fg",
  danger: "bg-danger-bg text-danger-fg",
  info: "bg-info-bg text-info-fg",
  neutral: "bg-neutral-bg text-neutral-fg",
  brand: "bg-brand-soft text-brand",
};

type StatProps = {
  label: React.ReactNode;
  value: React.ReactNode;
  icon?: React.ReactNode;
  tone?: Tone;
  /** Short line under the value (a comparison, a unit, the source). */
  note?: React.ReactNode;
  /** Every number on screen should lead somewhere: its list or its source. */
  href?: string;
  onClick?: () => void;
  /** For click-to-filter tiles. */
  selected?: boolean;
  className?: string;
};

/** A metric tile: icon, label, big number. Becomes a link or a filter button when given one. */
export default function Stat({ label, value, icon, tone = "brand", note, href, onClick, selected, className }: StatProps) {
  const body = (
    <>
      {icon && (
        <span aria-hidden className={cn("grid size-10 shrink-0 place-items-center rounded-full [&_svg]:size-5", iconTone[tone])}>
          {icon}
        </span>
      )}
      <span className="w-full min-w-0 flex-1">
        <span className="block text-xs font-medium text-muted">{label}</span>
        <span className="mt-0.5 block text-2xl leading-8 font-semibold text-strong tabular-nums">{value}</span>
        {note && <span className="mt-0.5 block text-xs text-subtle">{note}</span>}
      </span>
    </>
  );
  const cls = cn(
    // Two tiles share a row on a phone, so the icon sits above the text there.
    "flex flex-col items-start gap-2.5 rounded-card border border-line bg-surface p-4 text-left shadow-card sm:flex-row sm:items-center sm:gap-3.5",
    (href || onClick) && "transition-colors hover:border-brand/40 hover:bg-brand-tint",
    selected && "border-brand ring-2 ring-brand/20",
    className,
  );
  if (href)
    return (
      <Link href={href} className={cls}>
        {body}
      </Link>
    );
  if (onClick)
    return (
      <button type="button" onClick={onClick} aria-pressed={selected} className={cls}>
        {body}
      </button>
    );
  return <div className={cls}>{body}</div>;
}
