"use client";

import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { WordCloudWord } from "@/lib/topics";

type WordCloudViewProps = {
  words: WordCloudWord[];
  /** The word picked to narrow the topics, if any. */
  active?: string;
  onPick: (word: string) => void;
};

/** Colour and weight steps by relative size; every step keeps AA contrast on the card. */
function tier(scale: number): string {
  if (scale > 0.8) return "font-bold text-brand";
  if (scale > 0.6) return "font-semibold text-brand";
  if (scale > 0.35) return "font-medium text-brand/85";
  return "font-normal text-brand/75";
}

/**
 * Words sized by weight (square-root scale, so a few big words don't swamp the rest). Each
 * word is a button; picking one narrows the topic list to topics that use it.
 */
export default function WordCloudView({ words, active, onPick }: WordCloudViewProps) {
  const { locale } = useT();
  const max = Math.max(1, ...words.map((w) => w.weight));
  // Alphabetical order scatters big and small words; stable between renders.
  const ordered = [...words].sort((a, b) => a.text.localeCompare(b.text));
  return (
    <ul className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1 rounded-panel bg-surface-subtle p-4 leading-tight sm:p-6">
      {ordered.map((w) => {
        const scale = Math.sqrt(w.weight / max);
        const picked = active === w.text;
        return (
          <li key={w.text}>
            <button
              type="button"
              onClick={() => onPick(w.text)}
              aria-pressed={picked}
              aria-label={`${w.text}, ${formatNumber(w.weight, locale)}`}
              title={`${w.text}: ${formatNumber(w.weight, locale)}`}
              style={{ fontSize: `${0.8 + scale * 1.6}rem` }}
              className={cn(
                "rounded-full px-2 py-0.5 transition-colors",
                picked ? "bg-brand font-semibold text-white" : cn(tier(scale), "hover:bg-brand-soft hover:text-brand"),
              )}
            >
              {w.text}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
