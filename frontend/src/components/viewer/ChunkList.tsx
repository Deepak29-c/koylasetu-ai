"use client";

import { FileText } from "lucide-react";
import { useEffect, useRef } from "react";

import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import type { PageData } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

/** The text blocks of a page. Choosing one highlights it on the page image. */
export default function ChunkList({
  chunks,
  selected,
  onSelect,
}: {
  chunks: PageData["chunks"];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const { t } = useT();
  const selectedRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selected, chunks]);

  return (
    <Card aria-labelledby="page-text">
      <CardHeader id="page-text" icon={<FileText />} title={t("pageText")} subtitle={t("viewer.textHelp")} />
      {chunks.length === 0 ? (
        <EmptyState compact title={t("viewer.noText")} />
      ) : (
        <ul aria-labelledby="page-text" className="max-h-[70vh] space-y-2 overflow-y-auto scroll-quiet p-0.5 pr-1">
          {chunks.map((c) => {
            const on = c.id === selected;
            return (
              <li key={c.id}>
                <button
                  ref={on ? selectedRef : undefined}
                  type="button"
                  aria-current={on ? "true" : undefined}
                  onClick={() => onSelect(c.id)}
                  className={cn(
                    "block w-full rounded-panel border p-3 text-left text-sm leading-relaxed whitespace-pre-wrap transition-colors",
                    on
                      ? "border-warning-fg bg-warning-bg text-strong ring-2 ring-warning-border"
                      : "border-line bg-surface text-foreground hover:border-brand hover:bg-brand-tint",
                  )}
                >
                  {on && (
                    <span className="mb-1 block text-xs font-semibold text-warning-fg">{t("viewer.highlighted")}</span>
                  )}
                  {c.text}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
