"use client";

import { ListTree } from "lucide-react";
import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/Skeleton";
import { type PqPartsOut, previewPqParts } from "@/lib/api-pqform";
import { useT } from "@/lib/i18n";

const MIN_TEXT = 10;
const WAIT_MS = 400;

type Preview = { text: string; data: PqPartsOut | null; failed: boolean };

/**
 * The parts (a), (b)… the server finds in the question, checked a moment after typing stops.
 * The model is not asked, so a question without markers says it may still be split when the
 * draft is generated. The last result stays on screen while the next one is checked.
 */
export default function PartsPreview({ text }: { text: string }) {
  const { t } = useT();
  const question = text.trim();
  const [preview, setPreview] = useState<Preview | null>(null);

  useEffect(() => {
    if (question.length < MIN_TEXT) return;
    const abort = new AbortController();
    const timer = window.setTimeout(() => {
      previewPqParts(question, abort.signal).then(
        (data) => setPreview({ text: question, data, failed: false }),
        () => {
          if (!abort.signal.aborted) setPreview((p) => ({ text: question, data: p?.data ?? null, failed: true }));
        },
      );
    }, WAIT_MS);
    return () => {
      window.clearTimeout(timer);
      abort.abort();
    };
  }, [question]);

  if (question.length < MIN_TEXT) return null;
  const checking = preview?.text !== question;
  const data = preview?.data ?? null;
  const count = data?.parts.length ?? 0;

  return (
    <section
      aria-labelledby="pq-parts-title"
      aria-busy={checking || undefined}
      className="mt-4 rounded-panel border border-line bg-surface-subtle p-4"
    >
      <div className="flex flex-wrap items-center gap-2">
        <ListTree size={16} aria-hidden className="text-brand" />
        <h3 id="pq-parts-title" className="text-sm font-semibold text-strong">
          {t("pqform.partsTitle")}
        </h3>
        <p role="status" className="text-xs text-muted">
          {checking
            ? t("pqform.partsChecking")
            : data?.method === "markers"
              ? count === 1
                ? t("pqform.onePart")
                : t("pqform.partsFound").replace("{n}", String(count))
              : null}
        </p>
      </div>

      {!data && checking && (
        <div className="mt-3 space-y-2">
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      )}

      {preview?.failed && !checking && <p className="mt-2 text-xs text-muted">{t("pqform.partsFailed")}</p>}

      {data?.method === "single" && <p className="mt-2 text-sm text-muted">{t("pqform.noMarkers")}</p>}

      {data?.method === "markers" && (
        <>
          <ol className="mt-3 space-y-1.5 text-sm text-foreground">
            {data.parts.map((p, i) => (
              <li key={`${p.part}-${i}`} className="flex gap-2">
                <span className="shrink-0 font-mono font-semibold text-strong">({p.part})</span>
                <span className="line-clamp-2 min-w-0">{p.text}</span>
              </li>
            ))}
          </ol>
          {count > data.max_parts && (
            <p className="mt-3 text-xs font-medium text-warning-fg">
              {t("pqform.tooManyParts").replace("{n}", String(data.max_parts))}
            </p>
          )}
        </>
      )}
    </section>
  );
}
