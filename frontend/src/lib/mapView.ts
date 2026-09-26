// Pure helpers for the Map screen (#97), kept out of the component so `npm test` can check
// them without a browser. Type-only imports: no runtime code is pulled in.

import type { MapFigures } from "@/lib/api";

/** Shades from light to dark, as CSS variables defined in globals.css. */
export const SHADES = ["var(--map-1)", "var(--map-2)", "var(--map-3)", "var(--map-4)", "var(--map-5)"];

/**
 * Upper bounds of each shade, from the values' quantiles: resources range from a few tonnes
 * (Sikkim) to ~90,000 MT (Jharkhand), so equal-width steps would paint every state but two
 * the lightest shade. Fewer distinct values give fewer shades.
 */
export function shadeBreaks(values: number[], shades = SHADES.length): number[] {
  const sorted = [...new Set(values)].sort((a, b) => a - b);
  if (sorted.length === 0) return [];
  const n = Math.min(shades, sorted.length);
  return Array.from({ length: n }, (_, i) => sorted[Math.ceil(((i + 1) * sorted.length) / n) - 1]);
}

/** Index into SHADES for a value, given shadeBreaks(). */
export function shadeIndex(value: number, breaks: number[]): number {
  const i = breaks.findIndex((b) => value <= b);
  return i === -1 ? breaks.length - 1 : i;
}

/** States are matched by name; the boundary file and the extractor spell a few differently. */
export function stateKey(name: string): string {
  return name
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z]/g, "");
}

export type Projection = { west: number; north: number; scale: number; kx: number };

/** Longitude/latitude to the map's viewBox, as scripts/build_india_map.py projects. */
export function project(lon: number, lat: number, p: Projection): [number, number] {
  return [(lon - p.west) * p.kx * p.scale, (p.north - lat) * p.scale];
}

/** Circle radius: area in proportion to the value, so twice the coal looks twice as big. */
export function radius(value: number, max: number, maxRadius = 34, minRadius = 5): number {
  if (max <= 0 || value <= 0) return minRadius;
  return Math.max(minRadius, maxRadius * Math.sqrt(value / max));
}

/** Where each company's circle sits: its headquarters (longitude, latitude). ECL and BCCL
 * are 60 km apart, so ECL's label goes below its circle. */
export const SUBSIDIARY_HQ: Record<string, { name: string; at: [number, number]; label?: "below" }> = {
  ECL: { name: "Eastern Coalfields (Sanctoria)", at: [87.05, 23.73], label: "below" },
  BCCL: { name: "Bharat Coking Coal (Dhanbad)", at: [86.43, 23.8] },
  CCL: { name: "Central Coalfields (Ranchi)", at: [85.33, 23.36] },
  NCL: { name: "Northern Coalfields (Singrauli)", at: [82.67, 24.2] },
  WCL: { name: "Western Coalfields (Nagpur)", at: [79.09, 21.15] },
  SECL: { name: "South Eastern Coalfields (Bilaspur)", at: [82.15, 22.08] },
  MCL: { name: "Mahanadi Coalfields (Sambalpur)", at: [83.97, 21.47] },
  NEC: { name: "North Eastern Coalfields (Margherita)", at: [95.69, 27.28] },
  SCCL: { name: "Singareni Collieries (Kothagudem)", at: [80.63, 17.55] },
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2024-04" -> "as on Apr 2024" for resources (a stock), "Apr 2024" for production;
 * "FY 2023-24" and anything else is shown as stored. */
export function periodLabel(period: string | null, metric: MapFigures["metric"], asOn: string): string {
  if (!period) return "–";
  const m = /^(\d{4})-(\d{2})$/.exec(period);
  if (!m) return period;
  const month = `${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
  return metric === "coal_resource" ? `${asOn} ${month}` : month;
}

/** "0-300" -> "0–300 m". */
export function depthLabel(range: string): string {
  return `${range.replace("-", "–")} m`;
}

/** Jharia's coal is printed only as 0-600 m, not split into 0-300 and 300-600. */
export const JHARIA_BAND = "0-600";

/** Each segment's width in % of the widest band, so bands compare by length. */
export function segmentWidths(
  bands: { measured: number; indicated: number; inferred: number; total: number }[],
): { measured: number; indicated: number; inferred: number }[] {
  const max = Math.max(0, ...bands.map((b) => b.total));
  const pct = (v: number) => (max > 0 ? (100 * v) / max : 0);
  return bands.map((b) => ({ measured: pct(b.measured), indicated: pct(b.indicated), inferred: pct(b.inferred) }));
}
