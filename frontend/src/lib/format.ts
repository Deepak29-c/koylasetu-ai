/** Date and number formatting that follows the UI language. */

export function formatDateTime(value: string | null | undefined, locale: string): string {
  if (!value) return "–";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}

/** A calendar date ("2026-10-03") without shifting it through the local time zone. */
export function formatDate(value: string | null | undefined, locale: string): string {
  if (!value) return "–";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  const d = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString(locale, { dateStyle: "medium" });
}

export function formatNumber(value: number | null | undefined, locale: string, digits = 0): string {
  if (value === null || value === undefined) return "–";
  return value.toLocaleString(locale, { maximumFractionDigits: digits });
}

/** Whole days from today to a calendar date; negative when it has passed. */
export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!m) return null;
  const due = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - today.getTime()) / 86_400_000);
}
