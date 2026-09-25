import { cn } from "@/lib/cn";

export type RecordItem = {
  label: React.ReactNode;
  value: React.ReactNode;
  /** Monospace value: ids, hashes, codes. */
  mono?: boolean;
  /** Spans both columns in the two-column layout. */
  wide?: boolean;
};

/**
 * Label / value pairs for one record (a figure, a report, an audit entry). Values that are
 * missing show an en dash, never an empty cell.
 */
export default function RecordList({
  items,
  columns = 1,
  className,
}: {
  items: RecordItem[];
  columns?: 1 | 2;
  className?: string;
}) {
  return (
    <dl className={cn("grid gap-x-6", columns === 2 && "sm:grid-cols-2", className)}>
      {items.map((it, i) => (
        <div
          key={i}
          className={cn("border-b border-line py-2.5 last:border-b-0", columns === 2 && it.wide && "sm:col-span-2")}
        >
          <dt className="text-[11px] font-semibold tracking-wide text-subtle uppercase">{it.label}</dt>
          <dd className={cn("mt-0.5 text-sm break-words text-strong", it.mono && "font-mono text-[13px]")}>
            {it.value === null || it.value === undefined || it.value === "" ? "–" : it.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** An id or code in monospace, e.g. a fact id or a report number. */
export function MonoId({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn("rounded bg-surface-sunken px-1.5 py-0.5 font-mono text-[12px] text-muted", className)}>
      {children}
    </span>
  );
}
