"use client";

import { FileText } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";
import { type SourceLink, sourceHref } from "@/lib/sources";

/** What every citation chip needs: a marker id, the document and page, and where it links. */
export type ChipSource = SourceLink & {
  id: string;
  document: string;
  /** A short excerpt, shown on hover and focus. */
  excerpt?: string | null;
  /** A figure that has not been verified by a reviewer yet. */
  unverified?: boolean;
};

/**
 * A source marker inside text: "S1 · Coal Directory 2023-24, p. 14". Opens the page with the
 * figure or passage highlighted. The full document name is always available to hover,
 * focus and screen readers even when the visible name is shortened.
 */
export function CitationChip({ source, from, showId = true }: { source: ChipSource; from?: string; showId?: boolean }) {
  const { t } = useT();
  const full = `${source.document}, ${t("ui.pageAbbr")} ${source.page}`;
  const tip = source.excerpt ? `${full}\n\n${source.excerpt.slice(0, 240)}` : full;
  return (
    <Link
      href={sourceHref(source, from)}
      title={tip}
      aria-label={`${t("ui.sourceOf")} ${source.id}: ${full}${source.unverified ? ` (${t("unverified")})` : ""}`}
      className={cn(
        "mx-0.5 inline-flex max-w-[18rem] items-center gap-1 rounded-full border px-2 py-px align-baseline text-[11px] leading-5 font-medium no-underline",
        source.unverified
          ? "border-warning-border bg-warning-bg text-warning-fg hover:bg-warning-bg/70"
          : "border-brand/15 bg-brand-soft text-brand hover:bg-brand-tint",
      )}
    >
      {showId && <span className="font-mono font-semibold">{source.id}</span>}
      <span className="truncate">{source.document}</span>
      <span className="shrink-0">
        · {t("ui.pageAbbr")} {source.page}
      </span>
    </Link>
  );
}

/**
 * Text with inline source markers ([S1], [C2], [F3]) turned into chips. Markers without a
 * matching source are shown as plain text rather than silently dropped.
 */
export function TextWithCitations({
  text,
  sources,
  from,
  renderText,
  className,
}: {
  text: string;
  sources: Map<string, ChipSource>;
  from?: string;
  /** Render a plain text piece (e.g. to highlight unmatched numbers). */
  renderText?: (piece: string, key: number) => React.ReactNode;
  className?: string;
}) {
  const parts = text.split(/(\[\s*[A-Z]\d+\s*\])/g);
  return (
    <span className={className}>
      {parts.map((part, i) => {
        const id = part.match(/^\[\s*([A-Z]\d+)\s*\]$/)?.[1];
        if (id) {
          const s = sources.get(id);
          return s ? <CitationChip key={i} source={s} from={from} /> : <span key={i}>{part}</span>;
        }
        return renderText ? renderText(part, i) : <span key={i}>{part}</span>;
      })}
    </span>
  );
}

/** The numbered list of sources under a draft or an answer. */
export function SourcesList({
  sources,
  from,
  title,
  className,
}: {
  sources: ChipSource[];
  from?: string;
  title?: React.ReactNode;
  className?: string;
}) {
  const { t } = useT();
  if (!sources.length) return null;
  return (
    <section className={cn("space-y-2", className)}>
      <h3 className="text-sm font-semibold text-strong">{title ?? t("sources")}</h3>
      <ol className="divide-y divide-line overflow-hidden rounded-panel border border-line bg-surface">
        {sources.map((s) => (
          <li key={s.id}>
            <Link
              href={sourceHref(s, from)}
              className="flex items-start gap-3 px-4 py-2.5 text-sm hover:bg-surface-hover"
            >
              <span className="mt-0.5 font-mono text-xs font-semibold text-brand">{s.id}</span>
              <FileText size={16} aria-hidden className="mt-0.5 shrink-0 text-subtle" />
              <span className="min-w-0 flex-1">
                <span className="block font-medium break-words text-strong">{s.document}</span>
                {s.excerpt && <span className="mt-0.5 line-clamp-2 block text-xs text-muted">{s.excerpt}</span>}
              </span>
              <span className="shrink-0 text-xs text-muted">
                {t("ui.pageAbbr")} {s.page}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
