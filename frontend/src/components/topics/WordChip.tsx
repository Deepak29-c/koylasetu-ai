"use client";

import { X } from "lucide-react";

import { useT } from "@/lib/i18n";

/** The active word filter, with a button to remove it. */
export default function WordChip({ word, onRemove }: { word: string; onRemove: () => void }) {
  const { t } = useT();
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-brand/15 bg-brand-soft py-0.5 pr-1 pl-3 text-xs font-medium text-brand">
      <span className="truncate">
        {t("topics.wordFilter")}: <span className="font-semibold">{word}</span>
      </span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`${t("topics.removeWordFilter")}: ${word}`}
        title={t("topics.removeWordFilter")}
        className="grid size-5 shrink-0 place-items-center rounded-full hover:bg-brand hover:text-white"
      >
        <X size={12} aria-hidden />
      </button>
    </span>
  );
}
