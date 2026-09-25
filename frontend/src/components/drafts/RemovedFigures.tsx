"use client";

import { CircleSlash } from "lucide-react";

import { useT } from "@/lib/i18n";

/** Figures taken out of a draft because no source has them. */
export default function RemovedFigures({ numbers }: { numbers: string[] }) {
  const { t } = useT();
  if (!numbers.length) return null;
  return (
    <div className="flex items-start gap-2 rounded-control border border-danger-border bg-danger-bg px-3 py-2 text-xs text-danger-fg">
      <CircleSlash size={14} aria-hidden className="mt-0.5 shrink-0" />
      <p>
        <span className="font-semibold">{t("removedFigures")}:</span>{" "}
        <span className="tabular-nums">{numbers.join(", ")}</span>
        <span className="block opacity-90">{t("drafts.removedHelp")}</span>
      </p>
    </div>
  );
}
