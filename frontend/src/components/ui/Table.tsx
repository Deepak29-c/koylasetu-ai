"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

/**
 * The data table. Rounded header on a soft background, 48px rows, hairline row
 * dividers, no column rules. Wrap in <TableFrame> for the white card and horizontal scroll.
 */

export function TableFrame({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("ks-card overflow-hidden rounded-card border border-line bg-surface shadow-card", className)}>
      {children}
    </div>
  );
}

export function Table({
  className,
  caption,
  children,
  maxHeight,
}: {
  className?: string;
  /** Read by screen readers; not shown. */
  caption?: string;
  children: React.ReactNode;
  /** Bounded scroll so the header stays in view on long tables. */
  maxHeight?: string;
}) {
  return (
    <div className="ks-grow overflow-auto px-3 pb-2" style={maxHeight ? { maxHeight } : undefined}>
      <table className={cn("w-full border-separate border-spacing-0 text-left text-sm", className)}>
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}

export function THead({ children }: { children: React.ReactNode }) {
  return (
    <thead className="sticky top-0 z-[1] bg-surface">
      <tr className="[&>th]:bg-surface-sunken [&>th:first-child]:rounded-l-full [&>th:last-child]:rounded-r-full">
        {children}
      </tr>
    </thead>
  );
}

type SortDir = "asc" | "desc";

type THProps = React.ThHTMLAttributes<HTMLTableCellElement> & {
  /** Makes the header a sort button. */
  sort?: { active: boolean; dir: SortDir; onClick: () => void };
  align?: "left" | "right" | "center";
};

export function TH({ sort, align = "left", className, children, ...rest }: THProps) {
  const { t } = useT();
  const alignClass = align === "right" ? "text-right" : align === "center" ? "text-center" : "text-left";
  return (
    <th
      scope="col"
      aria-sort={sort?.active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
      className={cn(
        "h-10 px-3.5 text-xs font-semibold whitespace-nowrap text-muted first:pl-5 last:pr-5",
        alignClass,
        className,
      )}
      {...rest}
    >
      {sort ? (
        <button
          type="button"
          onClick={sort.onClick}
          className={cn(
            "inline-flex items-center gap-1 rounded-sm hover:text-brand",
            sort.active && "text-brand",
            align === "right" && "flex-row-reverse",
          )}
        >
          {children}
          {sort.active ? (
            sort.dir === "asc" ? (
              <ArrowUp size={12} aria-hidden />
            ) : (
              <ArrowDown size={12} aria-hidden />
            )
          ) : (
            <ArrowUpDown size={12} aria-hidden className="opacity-50" />
          )}
          {sort.active && <span className="sr-only">{sort.dir === "asc" ? t("ui.sortAsc") : t("ui.sortDesc")}</span>}
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function TR({ className, selected, ...rest }: React.HTMLAttributes<HTMLTableRowElement> & { selected?: boolean }) {
  return (
    <tr
      className={cn(
        "group [&>td]:border-b [&>td]:border-line last:[&>td]:border-b-0 hover:[&>td]:bg-surface-hover",
        selected && "[&>td]:bg-brand-tint",
        className,
      )}
      {...rest}
    />
  );
}

export function TD({
  className,
  align = "left",
  ...rest
}: React.TdHTMLAttributes<HTMLTableCellElement> & { align?: "left" | "right" | "center" }) {
  return (
    <td
      className={cn(
        "h-12 px-3.5 py-2.5 align-middle first:pl-5 last:pr-5",
        align === "right" && "text-right tabular-nums",
        align === "center" && "text-center",
        className,
      )}
      {...rest}
    />
  );
}

/** Title, "(Showing n)", search and actions above a table. */
export function TableToolbar({
  title,
  count,
  total,
  search,
  filters,
  actions,
  className,
}: {
  title?: React.ReactNode;
  count?: number;
  total?: number;
  search?: React.ReactNode;
  filters?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  const { t } = useT();
  return (
    <div className={cn("flex flex-wrap items-center gap-3 px-5 pt-4 pb-3", className)}>
      {(title || count !== undefined) && (
        <div className="mr-auto flex items-baseline gap-2">
          {title && <h2 className="text-base font-semibold text-strong">{title}</h2>}
          {count !== undefined && (
            <span className="text-xs text-subtle" aria-live="polite">
              ({t("ui.showing")}: {count}
              {total !== undefined && total !== count ? ` / ${total}` : ""})
            </span>
          )}
        </div>
      )}
      {filters}
      {search}
      {actions}
    </div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  label,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label?: string;
  className?: string;
}) {
  const { t } = useT();
  return (
    <div className={cn("relative w-full sm:w-64", className)}>
      <Search size={15} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-subtle" />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? t("ui.search")}
        aria-label={label ?? placeholder ?? t("ui.search")}
        className="h-9 w-full rounded-full border border-line-strong bg-surface pr-8 pl-9 text-sm placeholder:text-subtle focus:border-brand focus:ring-[3px] focus:ring-brand/15 focus:outline-none [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label={t("ui.clearSearch")}
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded-full p-1 text-subtle hover:text-brand"
        >
          <X size={14} aria-hidden />
        </button>
      )}
    </div>
  );
}

export function Pagination({
  page,
  pageCount,
  onPage,
  from,
  to,
  total,
}: {
  page: number;
  pageCount: number;
  onPage: (p: number) => void;
  from?: number;
  to?: number;
  total?: number;
}) {
  const { t } = useT();
  if (pageCount <= 1 && total === undefined) return null;
  return (
    <div className="mt-auto flex flex-wrap items-center justify-end gap-3 border-t border-line px-5 py-3 text-xs text-muted">
      {from !== undefined && to !== undefined && (
        <span aria-live="polite">
          {from}–{to}
          {total !== undefined ? ` ${t("of")} ${total}` : ""}
        </span>
      )}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          aria-label={t("ui.previousPage")}
          className="grid size-8 place-items-center rounded-control border border-line-strong bg-surface text-brand hover:bg-brand-tint disabled:cursor-not-allowed disabled:text-disabled disabled:hover:bg-surface"
        >
          <ChevronLeft size={16} aria-hidden />
        </button>
        <span className="min-w-12 text-center">
          {page} / {Math.max(pageCount, 1)}
        </span>
        <button
          type="button"
          onClick={() => onPage(page + 1)}
          disabled={page >= pageCount}
          aria-label={t("ui.nextPage")}
          className="grid size-8 place-items-center rounded-control border border-line-strong bg-surface text-brand hover:bg-brand-tint disabled:cursor-not-allowed disabled:text-disabled disabled:hover:bg-surface"
        >
          <ChevronRight size={16} aria-hidden />
        </button>
      </div>
    </div>
  );
}

/** Client-side sorting for a list. `get` returns the value to compare for a column key. */
export function useSort<T, K extends string>(
  rows: T[],
  get: (row: T, key: K) => string | number | null | undefined,
  initial: { key: K; dir: SortDir },
) {
  const [sort, setSort] = useState(initial);
  const sorted = useMemo(() => {
    const out = [...rows];
    out.sort((a, b) => {
      const x = get(a, sort.key);
      const y = get(b, sort.key);
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      const c = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return sort.dir === "asc" ? c : -c;
    });
    return out;
    // `get` is expected to be stable in meaning; it is usually an inline arrow.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sort]);
  const header = (key: K) => ({
    active: sort.key === key,
    dir: sort.dir,
    onClick: () =>
      setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" })),
  });
  return { sorted, sort, header };
}

/** Client-side paging over an already filtered list. */
export function usePaged<T>(rows: T[], pageSize = 25) {
  const [page, setPage] = useState(1);
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const current = Math.min(page, pageCount);
  const start = (current - 1) * pageSize;
  return {
    rows: rows.slice(start, start + pageSize),
    page: current,
    pageCount,
    setPage,
    from: rows.length ? start + 1 : 0,
    to: Math.min(start + pageSize, rows.length),
    total: rows.length,
  };
}
