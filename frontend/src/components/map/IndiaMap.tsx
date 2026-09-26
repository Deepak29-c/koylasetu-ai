"use client";

import { INDIA_STATES, MAP_HEIGHT, MAP_WIDTH, PROJECTION } from "@/components/map/indiaStates";
import type { MapFigures } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { project, radius, SHADES, shadeBreaks, shadeIndex, stateKey, SUBSIDIARY_HQ } from "@/lib/mapView";

type Item = MapFigures["items"][number];

type Props = {
  figures: MapFigures;
  selected: string | null;
  onSelect: (key: string | null) => void;
};

/** India's states as inline SVG: shaded by value (resources) or with a circle per company
 * (production). Works offline; the boundaries ship with the app (indiaStates.ts). */
export default function IndiaMap({ figures, selected, onSelect }: Props) {
  const { t, locale } = useT();
  const byState = new Map<string, Item>();
  if (figures.level === "state") for (const i of figures.items) byState.set(stateKey(i.key), i);
  const breaks = shadeBreaks(figures.items.map((i) => i.value));
  const max = Math.max(0, ...figures.items.map((i) => i.value));
  const label = (i: Item, name: string) => `${name}: ${formatNumber(i.value, locale, 2)} ${figures.unit}`;
  const keyActivate = (key: string) => (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(key);
    }
  };

  const selectedPath =
    figures.level === "state" && selected
      ? INDIA_STATES.find((s) => stateKey(s.name) === stateKey(selected))?.d
      : undefined;

  // Bigger circles first, so a small one is never hidden under a big neighbour
  const circles = figures.level === "subsidiary" ? [...figures.items].sort((a, b) => b.value - a.value) : [];

  return (
    <svg
      viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
      role="group"
      aria-label={t("map.mapLabel")}
      className="h-auto w-full max-h-[70vh]"
      onClick={(e) => e.target === e.currentTarget && onSelect(null)}
    >
      {INDIA_STATES.map((s) => {
        const item = byState.get(stateKey(s.name));
        const active = item && selected === item.key;
        const common = { d: s.d, stroke: "var(--map-stroke)", strokeLinejoin: "round" as const };
        if (!item)
          return (
            <path key={s.name} {...common} fill="var(--map-none)" strokeWidth={0.8}>
              <title>{s.name}</title>
            </path>
          );
        return (
          <path
            key={s.name}
            {...common}
            fill={SHADES[shadeIndex(item.value, breaks)]}
            strokeWidth={0.8}
            className="cursor-pointer outline-none hover:opacity-85 focus-visible:stroke-[var(--accent)] focus-visible:[stroke-width:3]"
            tabIndex={0}
            role="button"
            aria-pressed={active}
            aria-label={label(item, s.name)}
            onClick={() => onSelect(item.key)}
            onKeyDown={keyActivate(item.key)}
          >
            <title>{label(item, s.name)}</title>
          </path>
        );
      })}
      {selectedPath && (
        // Drawn again on top, so neighbouring states don't cover half of its outline
        <path d={selectedPath} fill="none" stroke="var(--accent)" strokeWidth={3} pointerEvents="none" />
      )}
      {circles.map((i) => {
        const hq = SUBSIDIARY_HQ[i.key];
        if (!hq) return null;
        const [x, y] = project(hq.at[0], hq.at[1], PROJECTION);
        const r = radius(i.value, max);
        const below = hq.label === "below";
        const active = selected === i.key;
        return (
          <g
            key={i.key}
            className="cursor-pointer outline-none [&:focus-visible>circle]:[stroke-width:4]"
            tabIndex={0}
            role="button"
            aria-pressed={active}
            aria-label={label(i, hq.name)}
            onClick={() => onSelect(i.key)}
            onKeyDown={keyActivate(i.key)}
          >
            <title>{label(i, hq.name)}</title>
            <circle
              cx={x}
              cy={y}
              r={r}
              fill="var(--accent)"
              fillOpacity={0.75}
              stroke={active ? "var(--brand)" : "var(--accent-ink)"}
              strokeWidth={active ? 4 : 1.5}
            />
            <text
              x={x}
              y={below ? y + r + 20 : y - r - 6}
              textAnchor="middle"
              fontSize={20}
              fontWeight={600}
              fill="var(--text-strong)"
              stroke="var(--surface)"
              strokeWidth={4}
              paintOrder="stroke"
            >
              {i.key}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
