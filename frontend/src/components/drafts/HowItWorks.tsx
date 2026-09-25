"use client";

import { ListChecks } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { useT } from "@/lib/i18n";

/** The steps a generator runs, shown next to its form so the wait is expected. */
export default function HowItWorks({ steps }: { steps: string[] }) {
  const { t } = useT();
  return (
    <Card as="aside">
      <CardHeader title={t("drafts.howItWorks")} icon={<ListChecks />} />
      <ol className="space-y-3">
        {steps.map((s, i) => (
          <li key={i} className="flex items-start gap-3 text-sm">
            <span
              aria-hidden
              className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-semibold text-brand"
            >
              {i + 1}
            </span>
            <span className="pt-0.5">{s}</span>
          </li>
        ))}
      </ol>
      <p className="mt-5 rounded-panel bg-surface-subtle px-4 py-3 text-xs text-muted">{t("drafts.leaveSafe")}</p>
    </Card>
  );
}
