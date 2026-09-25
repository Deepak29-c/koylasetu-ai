"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import Tabs from "@/components/ui/Tabs";
import type { ReviewItem } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

import { useFigureText } from "./figureText";

export type Severity = ReviewItem["worst_severity"];
export type ReviewFilterState = { severity: Severity | "all"; rule: string; document: string };
export const NO_FILTERS: ReviewFilterState = { severity: "all", rule: "", document: "" };

const SEVERITIES: Severity[] = ["high", "medium", "low"];

/** Applies the filters. Severity is the item's worst open issue; rule matches any open issue. */
export function applyFilters(items: ReviewItem[], f: ReviewFilterState): ReviewItem[] {
  return items.filter(
    (i) =>
      (f.severity === "all" || i.worst_severity === f.severity) &&
      (!f.rule || i.issues.some((x) => x.rule_code === f.rule)) &&
      (!f.document || i.fact.document_id === f.document),
  );
}

/** Severity tabs, a check (rule) picker and a document picker, built from the loaded queue. */
export default function ReviewFilters({
  items,
  value,
  onChange,
}: {
  items: ReviewItem[];
  value: ReviewFilterState;
  onChange: (v: ReviewFilterState) => void;
}) {
  const { t } = useT();
  const fx = useFigureText();

  // Severity counts follow the other two filters, so each count is what the tab would show.
  const base = applyFilters(items, { ...value, severity: "all" });
  const count = (s: Severity) => base.filter((i) => i.worst_severity === s).length;

  const rules = [...new Set(items.flatMap((i) => i.issues.map((x) => x.rule_code)))].sort();
  const docs = [...new Map(items.map((i) => [i.fact.document_id, i.document_title])).entries()].sort((a, b) =>
    a[1].localeCompare(b[1]),
  );

  const active = value.severity !== "all" || !!value.rule || !!value.document;

  return (
    <div className="space-y-3">
      <Tabs<Severity | "all">
        label={t("review.severityFilter")}
        value={value.severity}
        onChange={(severity) => onChange({ ...value, severity })}
        items={[
          { value: "all", label: t("ui.all"), count: base.length },
          ...SEVERITIES.map((s) => ({ value: s, label: t(`sev.${s}` as LabelKey), count: count(s) })),
        ]}
      />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
        <Field label={t("review.ruleFilter")}>
          <Select value={value.rule} onChange={(e) => onChange({ ...value, rule: e.target.value })}>
            <option value="">{t("review.allRules")}</option>
            {rules.map((r) => (
              <option key={r} value={r}>
                {r} · {fx.ruleLabel(r)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("review.documentFilter")}>
          <Select value={value.document} onChange={(e) => onChange({ ...value, document: e.target.value })}>
            <option value="">{t("review.allDocuments")}</option>
            {docs.map(([id, title]) => (
              <option key={id} value={id}>
                {title}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {active && (
        <Button variant="ghost" size="sm" icon={<X size={14} aria-hidden />} onClick={() => onChange(NO_FILTERS)}>
          {t("ui.clearFilters")}
        </Button>
      )}
    </div>
  );
}
