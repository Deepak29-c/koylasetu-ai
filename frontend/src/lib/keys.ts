/**
 * A random Idempotency-Key for one generation request. Keep the same key until the input
 * changes, so a retry after a proxy timeout returns the draft already made instead of a
 * second one. (crypto.randomUUID needs https, so build it from random bytes.)
 */
export function newKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}
