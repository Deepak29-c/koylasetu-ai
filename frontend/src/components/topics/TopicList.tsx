"use client";

import Badge from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { keywordsInclude, type TopicRow } from "@/lib/topics";

type TopicListProps = {
  topics: TopicRow[];
  selectedId?: string;
  /** The word picked in the cloud; matching keywords are highlighted. */
  word?: string;
  onSelect: (topic: TopicRow) => void;
};

const MAX_KEYWORDS = 6;

/** Topics largest first, each with a size bar on a shared scale and its keywords. */
export default function TopicList({ topics, selectedId, word, onSelect }: TopicListProps) {
  const { t, locale } = useT();
  const max = Math.max(1, ...topics.map((x) => x.size));
  return (
    <ul className="max-h-[60vh] overflow-y-auto scroll-quiet space-y-2 pr-0.5">
      {topics.map((topic) => {
        const picked = topic.id === selectedId;
        return (
          <li key={topic.id}>
            <button
              type="button"
              onClick={() => onSelect(topic)}
              aria-pressed={picked}
              className={cn(
                "w-full rounded-panel border p-3 text-left transition-colors",
                picked ? "border-brand bg-brand-tint" : "border-line bg-surface hover:border-line-strong hover:bg-surface-hover",
              )}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className={cn("min-w-0 text-sm text-strong", picked ? "font-semibold" : "font-medium")}>
                  {topic.label}
                </span>
                <span className="shrink-0 text-xs text-muted tabular-nums">
                  {formatNumber(topic.size, locale)} {t("questionsWord")}
                </span>
              </div>
              <div aria-hidden className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-sunken">
                <div
                  className={cn("h-full rounded-full", picked ? "bg-brand" : "bg-brand/60")}
                  style={{ width: `${(topic.size / max) * 100}%` }}
                />
              </div>
              {topic.keywords.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  <span className="sr-only">{t("keywords")}:</span>
                  {topic.keywords.slice(0, MAX_KEYWORDS).map((k) => (
                    <Badge key={k} tone={word && keywordsInclude([k], word) ? "brand" : "neutral"}>
                      {k}
                    </Badge>
                  ))}
                  {topic.keywords.length > MAX_KEYWORDS && (
                    <span className="self-center text-xs text-subtle tabular-nums">
                      +{formatNumber(topic.keywords.length - MAX_KEYWORDS, locale)}
                    </span>
                  )}
                </div>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
