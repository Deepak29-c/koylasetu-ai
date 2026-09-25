import { Inbox } from "lucide-react";

import { cn } from "@/lib/cn";

type EmptyStateProps = {
  icon?: React.ReactNode;
  title: React.ReactNode;
  children?: React.ReactNode;
  action?: React.ReactNode;
  /** Smaller, for use inside a card or table. */
  compact?: boolean;
  className?: string;
};

/** Keeps its height so a table or list never collapses to nothing. */
export default function EmptyState({ icon, title, children, action, compact, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "ks-empty flex flex-col items-center justify-center rounded-panel border border-dashed border-line-strong bg-surface-subtle text-center",
        compact ? "min-h-40 gap-2 px-4 py-6" : "min-h-56 gap-3 px-6 py-10",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "grid place-items-center rounded-full bg-brand-soft text-brand",
          compact ? "size-10 [&_svg]:size-5" : "size-12 [&_svg]:size-6",
        )}
      >
        {icon ?? <Inbox />}
      </span>
      <p className={cn("font-semibold text-strong", compact ? "text-sm" : "text-base")}>{title}</p>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
