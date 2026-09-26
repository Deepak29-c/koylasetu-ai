"use client";

import Link from "next/link";

import { cn } from "@/lib/cn";

export type TabItem<V extends string = string> = {
  value: V;
  label: React.ReactNode;
  icon?: React.ReactNode;
  count?: number;
  /** Renders the tab as a link (route-based tabs). */
  href?: string;
};

const tabClass = (active: boolean) =>
  cn(
    "inline-flex h-9 shrink-0 items-center gap-2 rounded-full px-4 text-xs font-medium whitespace-nowrap transition-colors",
    active ? "bg-surface text-strong shadow-pill [&_svg]:text-brand" : "text-muted hover:text-brand",
  );

/** Pill tabs on a sunken track. Use buttons for in-page views, links for routes. */
export default function Tabs<V extends string>({
  items,
  value,
  onChange,
  label,
  className,
}: {
  items: TabItem<V>[];
  value: V;
  onChange?: (v: V) => void;
  label: string;
  className?: string;
}) {
  return (
    <div
      role={onChange ? "tablist" : undefined}
      aria-label={label}
      // On a phone the tabs wrap onto a second line rather than hiding off the edge.
      className={cn(
        "inline-flex max-w-full flex-wrap gap-1 rounded-card bg-surface-sunken p-1 scroll-quiet sm:flex-nowrap sm:overflow-x-auto sm:rounded-full",
        className,
      )}
    >
      {items.map((it) => {
        const active = it.value === value;
        const inner = (
          <>
            {it.icon}
            {it.label}
            {it.count !== undefined && (
              <span
                className={cn(
                  "min-w-5 rounded-full px-1.5 text-center text-[11px] leading-5 font-semibold",
                  active ? "bg-brand text-white" : "bg-surface text-muted",
                )}
              >
                {it.count}
              </span>
            )}
          </>
        );
        return it.href ? (
          <Link key={it.value} href={it.href} aria-current={active ? "page" : undefined} className={tabClass(active)}>
            {inner}
          </Link>
        ) : (
          <button
            key={it.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange?.(it.value)}
            className={tabClass(active)}
          >
            {inner}
          </button>
        );
      })}
    </div>
  );
}
