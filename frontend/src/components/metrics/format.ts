import { formatNumber } from "@/lib/format";
import type { LabelKey } from "@/lib/i18n";

type T = (key: LabelKey) => string;

/** "84.2%", or the translated "n/a" when the number is not known. */
export function pctText(value: number | null, t: T, locale: string): string {
  return value === null ? t("metrics.na") : `${formatNumber(value, locale, 1)}%`;
}

/** Milliseconds shown as seconds with one decimal, e.g. "2.4 s". */
export function secondsText(ms: number | null, t: T, locale: string): string {
  return ms === null ? t("metrics.na") : `${formatNumber(ms / 1000, locale, 1)} ${t("ui.seconds")}`;
}
