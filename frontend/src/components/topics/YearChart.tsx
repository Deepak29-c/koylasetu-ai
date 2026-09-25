"use client";

import { formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";

type YearChartProps = {
  /** The shared year axis, oldest first. */
  years: string[];
  counts: Record<string, number>;
  /** The year picked to filter the questions, if any. */
  active?: string;
  onPick: (year: string) => void;
};

const W = 640;
const H = 220;
const PAD = { l: 44, r: 8, t: 22, b: 40 };

/** Rounds the top of the axis up to a tidy number (1, 2, 5 × 10^n). */
function niceMax(v: number): number {
  if (v <= 5) return Math.max(1, v);
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 2, 5, 10]) if (m * p >= v) return m * p;
  return v;
}

/**
 * One-series bar chart: questions per year on a shared axis. Every bar with questions is a
 * button (Tab, then Enter or Space) that filters the question list to that year.
 */
export default function YearChart({ years, counts, active, onPick }: YearChartProps) {
  const { t, locale } = useT();
  const max = niceMax(Math.max(0, ...years.map((y) => counts[y] ?? 0)));
  const slot = (W - PAD.l - PAD.r) / Math.max(1, years.length);
  const barW = Math.min(36, Math.max(6, slot - 6));
  const y0 = H - PAD.b;
  const plotH = y0 - PAD.t;
  const scale = (v: number) => (plotH * v) / max;
  const ticks = max >= 2 ? [0, Math.round(max / 2), max] : [0, max];
  // With many years, label every other one (the picked year is always labelled).
  const step = years.length > 12 ? 2 : 1;

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full min-w-[30rem]"
        role="group"
        aria-label={t("topics.chartLabel")}
      >
        {ticks.map((v) => {
          const y = y0 - scale(v);
          return (
            <g key={v} aria-hidden>
              <line x1={PAD.l} x2={W - PAD.r} y1={y} y2={y} stroke={v === 0 ? "var(--border-strong)" : "var(--border)"} />
              <text x={PAD.l - 8} y={y + 4} textAnchor="end" fontSize="11" fill="var(--text-muted)" className="tabular-nums">
                {formatNumber(v, locale)}
              </text>
            </g>
          );
        })}
        <text
          aria-hidden
          x={12}
          y={PAD.t + plotH / 2}
          textAnchor="middle"
          fontSize="11"
          fill="var(--text-subtle)"
          transform={`rotate(-90 12 ${PAD.t + plotH / 2})`}
        >
          {t("topics.axisQuestions")}
        </text>
        <text aria-hidden x={PAD.l + (W - PAD.l - PAD.r) / 2} y={H - 4} textAnchor="middle" fontSize="11" fill="var(--text-subtle)">
          {t("topics.axisYear")}
        </text>

        {years.map((y, i) => {
          const v = counts[y] ?? 0;
          const h = v > 0 ? Math.max(scale(v), 4) : 0;
          const cx = PAD.l + i * slot + slot / 2;
          const x = cx - barW / 2;
          const picked = active === y;
          const dim = !!active && !picked;
          const label = `${y}: ${formatNumber(v, locale)} ${t("questionsWord")}`;
          const showYear = picked || i % step === 0;
          const r = Math.min(4, barW / 2, h / 2);
          const bar =
            v > 0 ? (
              <path
                d={`M${x},${y0} v${-(h - r)} q0,${-r} ${r},${-r} h${barW - 2 * r} q${r},0 ${r},${r} v${h - r} z`}
                fill="var(--brand)"
                opacity={dim ? 0.35 : 1}
                className="transition-opacity group-hover:opacity-85"
              />
            ) : null;
          const texts = (
            <>
              {v > 0 && (
                <text
                  x={cx}
                  y={y0 - h - 6}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight={picked ? 700 : 500}
                  fill={dim ? "var(--text-muted)" : "var(--text-strong)"}
                  className="tabular-nums"
                >
                  {formatNumber(v, locale)}
                </text>
              )}
              {showYear && (
                <text
                  x={cx}
                  y={y0 + 16}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight={picked ? 700 : 400}
                  fill={picked ? "var(--brand)" : "var(--text-muted)"}
                  className="tabular-nums"
                >
                  {y}
                </text>
              )}
              {picked && <rect x={cx - 12} y={y0 + 21} width={24} height={3} rx={1.5} fill="var(--accent)" />}
            </>
          );

          if (v === 0) {
            return (
              <g key={y} aria-hidden>
                <title>{label}</title>
                {texts}
              </g>
            );
          }
          return (
            <g
              key={y}
              role="button"
              tabIndex={0}
              aria-label={label}
              aria-pressed={picked}
              onClick={() => onPick(y)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onPick(y);
                }
              }}
              className="group cursor-pointer outline-none"
            >
              <title>{label}</title>
              {/* Hit and focus area larger than the bar. */}
              <rect
                x={PAD.l + i * slot + 1}
                y={PAD.t - 18}
                width={Math.max(1, slot - 2)}
                height={y0 - PAD.t + 18 + 26}
                rx={6}
                fill="transparent"
                strokeWidth={2}
                className="stroke-transparent group-focus-visible:stroke-brand"
              />
              {bar}
              {texts}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
