"use client";

import type { Fact } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";

/** Fills "{name}" placeholders in a label. */
export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

/** "coking_coal_production" -> "Coking coal production", for codes without a label. */
function humanise(code: string): string {
  const s = code.replace(/_/g, " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : code;
}

/** "2024-12" -> "December 2024" in the UI language; anything else unchanged. */
function monthText(value: string, locale: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(value);
  if (!m) return value;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, 1);
  return d.toLocaleDateString(locale, { month: "long", year: "numeric" });
}

/** Wording for a fact's metric, period and units, in the UI language. */
export function useFigureText() {
  const { t, locale } = useT();

  // t() returns undefined for a key that does not exist (a metric added after these labels).
  const metricLabel = (code: string) => t(`metric.${code}` as LabelKey) || humanise(code);

  const ruleLabel = (code: string) => t(`review.rule.${code}` as LabelKey) || code;

  const periodText = (f: Pick<Fact, "period" | "period_type">) => {
    if (!f.period) return "–";
    if (f.period_type === "YTD") return fill(t("review.periodYtd"), { period: monthText(f.period, locale) });
    if (f.period_type === "AS_ON") return fill(t("review.periodAsOn"), { date: formatDate(f.period, locale) });
    if (f.period_type === "MONTH") return monthText(f.period, locale);
    return f.period;
  };

  // Standard units (backend Metric enum): overburden is in million cubic metres, the rest in million tonnes.
  const stdUnit = (metric: string) => (metric === "ob_removal" ? t("review.unitMcum") : t("review.unitMT"));

  const printed = (f: Pick<Fact, "value_raw" | "unit">) => [f.value_raw, f.unit].filter(Boolean).join(" ");

  const standard = (f: Pick<Fact, "value_std" | "metric">) =>
    f.value_std != null ? `${f.value_std.toLocaleString(locale, { maximumFractionDigits: 6 })} ${stdUnit(f.metric)}` : "–";

  const who = (f: Pick<Fact, "subsidiary" | "state">) => f.subsidiary ?? f.state ?? "–";

  const pageRef = (document: string, page: number) => `${document}, ${t("ui.pageAbbr")} ${page}`;

  return { metricLabel, ruleLabel, periodText, stdUnit, printed, standard, who, pageRef };
}
