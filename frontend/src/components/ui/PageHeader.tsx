"use client";

import { ArrowLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

export type Crumb = { label: string; href?: string };

type PageHeaderProps = {
  title: React.ReactNode;
  /** Plain-text title for the browser tab when `title` is not a string. */
  documentTitle?: string;
  description?: React.ReactNode;
  /** Parent pages, most general first. The current page is the title, not a crumb. */
  breadcrumbs?: Crumb[];
  /** Where "Back" goes. Defaults to the last breadcrumb that has a link. */
  back?: { href: string; label?: string };
  /** Chips next to the title (status, type). */
  meta?: React.ReactNode;
  actions?: React.ReactNode;
  /** A tab row under the title. */
  tabs?: React.ReactNode;
  className?: string;
};

export default function PageHeader({
  title,
  documentTitle,
  description,
  breadcrumbs,
  back,
  meta,
  actions,
  tabs,
  className,
}: PageHeaderProps) {
  const { t } = useT();
  const tabTitle = documentTitle ?? (typeof title === "string" ? title : undefined);

  useEffect(() => {
    if (tabTitle) document.title = `${tabTitle} · KoylaSetu AI`;
  }, [tabTitle]);

  return (
    <header className={cn("mb-6 space-y-3", className)}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb">
          <ol className="flex flex-wrap items-center gap-1 text-xs text-muted">
            {breadcrumbs.map((c, i) => (
              <li key={`${c.label}-${i}`} className="flex items-center gap-1">
                {c.href ? (
                  <Link href={c.href} className="rounded-sm hover:text-brand hover:underline">
                    {c.label}
                  </Link>
                ) : (
                  <span>{c.label}</span>
                )}
                <ChevronRight size={12} aria-hidden className="text-disabled" />
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
        {back && (
          <Link
            href={back.href}
            aria-label={back.label ?? t("ui.back")}
            title={back.label ?? t("ui.back")}
            className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-surface text-brand shadow-pill hover:bg-brand-tint"
          >
            <ArrowLeft size={18} aria-hidden />
          </Link>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <h1 className="text-xl leading-8 font-semibold tracking-tight text-strong sm:text-2xl">{title}</h1>
            {meta && <div className="flex flex-wrap items-center gap-2">{meta}</div>}
          </div>
          {description && <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>}
        </div>
        {/* On a phone the actions take their own line so the title keeps the full width. */}
        {actions && <div className="flex basis-full flex-wrap items-center gap-2 sm:basis-auto">{actions}</div>}
      </div>
      {tabs}
    </header>
  );
}
