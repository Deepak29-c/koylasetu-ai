import { failureKey, type LabelKey } from "@/lib/i18n";

/**
 * A readable message from anything a promise rejected with. Given `t`, a server error that
 * carries a known code is shown as its translated sentence instead of the English text.
 */
export function errorText(e: unknown, t?: (key: LabelKey) => string): string {
  if (t) {
    const key = failureKey((e as { code?: string | null } | null)?.code);
    if (key) return t(key);
  }
  return e instanceof Error ? e.message : String(e);
}
