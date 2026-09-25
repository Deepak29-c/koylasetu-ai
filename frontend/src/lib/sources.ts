/**
 * Links from a figure or passage to the page it came from. The document viewer reads
 * page, chunk (text block to highlight), box (x0,y0,x1,y1 of a table cell) and from
 * (where to go back to), so every screen builds its links here.
 */
export type SourceLink = {
  document_id: string;
  page: number;
  chunk_id?: string | null;
  bbox?: number[] | null;
};

export function sourceHref(s: SourceLink, from?: string): string {
  const q = new URLSearchParams({ page: String(s.page) });
  if (s.bbox && s.bbox.length === 4) q.set("box", s.bbox.join(","));
  else if (s.chunk_id) q.set("chunk", s.chunk_id);
  if (from) q.set("from", from);
  return `/documents/${s.document_id}?${q}`;
}

/** The path (and query) of the current page, for a viewer back link. */
export function currentPath(): string {
  if (typeof window === "undefined") return "";
  return window.location.pathname + window.location.search;
}

/**
 * `value` if it is a path on this site ("/reports/1?x=y"), otherwise null. Used for ?next=
 * and ?from= so a crafted link cannot send someone to another site after login or on Back.
 * Browsers drop tabs and newlines and read "\" as "/", so those are refused outright, and
 * the result must still resolve to the same origin.
 */
export function safeInternalPath(value: string | null | undefined): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  if (/[\u0000-\u001f\u007f\\]/.test(value)) return null;
  const base = "http://internal.invalid";
  try {
    const u = new URL(value, base);
    return u.origin === base ? u.pathname + u.search + u.hash : null;
  } catch {
    return null;
  }
}
