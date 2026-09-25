import type { LabelKey } from "@/lib/i18n";

/**
 * The label for a code the server sends (a rule, a section, a status outcome), or the
 * server's own English text when this screen has no label for that code yet.
 */
export function labelOr(t: (key: LabelKey) => string, key: string, fallback: string): string {
  return t(key as LabelKey) || fallback;
}

/** "0.5 %", "1,500 MT", "0.85": a threshold or limit with its unit. */
export function withUnit(value: number, unit: string, locale: string): string {
  const n = value.toLocaleString(locale, { maximumFractionDigits: 2 });
  return unit ? `${n} ${unit}` : n;
}
