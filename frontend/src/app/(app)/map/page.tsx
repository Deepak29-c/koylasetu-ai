"use client";

import { ExternalLink, Lock, MapPinned } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import DepthColumn from "@/components/map/DepthColumn";
import IndiaMap from "@/components/map/IndiaMap";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Field, Select } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { getMapFigures, type MapFigures } from "@/lib/api";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { formatNumber } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { depthLabel, JHARIA_BAND, periodLabel, SHADES, shadeBreaks, shadeIndex, SUBSIDIARY_HQ } from "@/lib/mapView";
import { can } from "@/lib/permissions";
import { sourceHref } from "@/lib/sources";

const METRICS: { value: MapFigures["metric"]; label: LabelKey }[] = [
  { value: "coal_resource", label: "map.metric.coal_resource" },
  { value: "coal_production", label: "map.metric.coal_production" },
  { value: "coal_offtake", label: "map.metric.coal_offtake" },
  { value: "coking_coal_production", label: "map.metric.coking_coal_production" },
];
const CATEGORIES: { value: string; label: LabelKey }[] = [
  { value: "", label: "map.category.total" },
  { value: "Measured", label: "map.category.measured" },
  { value: "Indicated", label: "map.category.indicated" },
  { value: "Inferred", label: "map.category.inferred" },
];

type Item = MapFigures["items"][number];

export default function MapPage() {
  const me = useMe();
  const { t, locale } = useT();
  const allowed = can(me, "ask_questions");
  const [metric, setMetric] = useState<MapFigures["metric"]>("coal_resource");
  const [category, setCategory] = useState("");
  const [period, setPeriod] = useState("");
  const [depth, setDepth] = useState("");
  const [data, setData] = useState<MapFigures | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    return getMapFigures({ metric, category, period, depth })
      .then(
        (d) => {
          setData(d);
          setError(null);
        },
        (e) => setError(errorText(e)),
      )
      .finally(() => setLoading(false));
  }, [metric, category, period, depth]);

  useEffect(() => {
    if (!allowed) return;
    // Fetch when the filters change; the state updates happen after the request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [allowed, load]);

  if (!allowed)
    return (
      <>
        <PageHeader title={t("map.title")} />
        <EmptyState icon={<Lock />} title={t("noPermission")} />
      </>
    );

  const asOn = t("map.asOn");
  const name = (key: string) => (data?.level === "subsidiary" ? (SUBSIDIARY_HQ[key]?.name ?? key) : key);
  const chosen = data?.items.find((i) => i.key === selected) ?? null;
  const total = data?.items.reduce((sum, i) => sum + i.value, 0) ?? 0;

  return (
    <>
      <PageHeader title={t("map.title")} description={t("map.description")} />
      <div className="space-y-6">
        <Card>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label={t("map.metric")}>
              <Select
                value={metric}
                onChange={(e) => {
                  setMetric(e.target.value as MapFigures["metric"]);
                  setPeriod("");
                  setDepth("");
                  setSelected(null);
                }}
              >
                {METRICS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {t(m.label)}
                  </option>
                ))}
              </Select>
            </Field>
            {metric === "coal_resource" && (
              <Field label={t("map.category")}>
                <Select
                  value={category}
                  onChange={(e) => {
                    setCategory(e.target.value);
                    setPeriod("");
                  }}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c.value} value={c.value}>
                      {t(c.label)}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            {metric === "coal_resource" && (
              <Field label={t("map.depth")}>
                <Select
                  value={depth}
                  disabled={!data?.depths.length}
                  onChange={(e) => {
                    setDepth(e.target.value);
                    setPeriod(""); // depth figures come from a different table, with their own periods
                  }}
                >
                  <option value="">{t("map.allDepths")}</option>
                  {data?.depths.map((d) => (
                    <option key={d} value={d}>
                      {depthLabel(d)}
                      {d === JHARIA_BAND ? ` (${t("map.jhariaOnly")})` : ""}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Field label={t("map.period")}>
              <Select
                value={period || data?.period || ""}
                disabled={!data?.periods.length}
                onChange={(e) => setPeriod(e.target.value)}
              >
                {!data?.periods.length && <option value="">–</option>}
                {data?.periods.map((p) => (
                  <option key={p} value={p}>
                    {periodLabel(p, metric, asOn)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </Card>

        {error && (
          <Alert
            tone="danger"
            title={t("map.loadFailed")}
            action={
              <Button variant="danger-outline" size="sm" loading={loading} onClick={load}>
                {t("retry")}
              </Button>
            }
          >
            {error}
          </Alert>
        )}

        {!data && !error && <Skeleton className="h-[32rem] rounded-card" />}

        {data && (
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className={cn("lg:col-span-2", loading && "opacity-60")}>
              <CardHeader
                icon={<MapPinned />}
                title={t(METRICS.find((m) => m.value === data.metric)!.label)}
                subtitle={
                  data.period
                    ? [
                        data.depth && `${t("map.depth")} ${depthLabel(data.depth)}`,
                        periodLabel(data.period, data.metric, asOn),
                        `${t("map.unitNote")} ${data.unit}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")
                    : undefined
                }
              />
              {data.items.length === 0 ? (
                <EmptyState compact title={t("map.empty")}>
                  {t("map.emptyBody")}
                </EmptyState>
              ) : (
                <>
                  <IndiaMap figures={data} selected={selected} onSelect={setSelected} />
                  <Legend data={data} />
                  {data.depth && data.depth !== JHARIA_BAND && data.depth !== "600-1200" && (
                    <p className="mt-2 text-xs text-subtle">{t("map.jhariaNote")}</p>
                  )}
                </>
              )}
              <p className="mt-4 text-xs text-subtle">
                {t("map.boundaryCredit")}{" "}
                <a
                  className="underline hover:text-strong"
                  href="https://github.com/datameet/maps"
                  target="_blank"
                  rel="noreferrer"
                >
                  DataMeet (CC BY 4.0)
                </a>
              </p>
            </Card>

            <Card>
              {chosen ? (
                <>
                  <Detail item={chosen} name={name(chosen.key)} data={data} onClose={() => setSelected(null)} />
                  {data.metric === "coal_resource" && <DepthColumn state={chosen.key} period={data.period} />}
                </>
              ) : (
                <>
                  <CardHeader
                    title={data.level === "state" ? t("map.byState") : t("map.bySubsidiary")}
                    subtitle={t("map.pickHint")}
                  />
                  <ol className="divide-y divide-line">
                    {data.items.map((i) => (
                      <li key={i.key}>
                        <button
                          type="button"
                          onClick={() => setSelected(i.key)}
                          className="flex w-full items-center gap-3 py-2 text-left text-sm hover:bg-surface-hover"
                        >
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-strong">
                              {i.key}
                            </span>
                            {data.level === "subsidiary" && (
                              <span className="block truncate text-xs text-subtle">{name(i.key)}</span>
                            )}
                          </span>
                          {i.status !== "VERIFIED" && <Badge tone="warning">{t("map.unverified")}</Badge>}
                          <span className="tabular-nums text-muted">{formatNumber(i.value, locale, 2)}</span>
                          <span className="w-12 text-right text-xs text-subtle tabular-nums">
                            {total ? `${formatNumber((100 * i.value) / total, locale, 1)}%` : ""}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ol>
                  {data.metric === "coal_resource" && <DepthColumn state={null} period={data.period} />}
                </>
              )}
            </Card>
          </div>
        )}
      </div>
    </>
  );
}

function Legend({ data }: { data: MapFigures }) {
  const { t, locale } = useT();
  if (data.level === "subsidiary")
    return (
      <p className="mt-3 flex items-center gap-2 text-xs text-muted">
        <span aria-hidden className="inline-block size-3 rounded-full border border-accent-ink bg-accent" />
        {t("map.circleLegend")}
      </p>
    );
  const breaks = shadeBreaks(data.items.map((i) => i.value));
  const lows = [Math.min(...data.items.map((i) => i.value)), ...breaks.slice(0, -1)];
  return (
    <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label={t("map.legend")}>
      {breaks.map((b, i) => (
        <li key={i} className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block size-3 rounded-sm" style={{ background: SHADES[i] }} />
          {formatNumber(lows[i], locale)} – {formatNumber(b, locale)}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="inline-block size-3 rounded-sm border border-line-strong bg-[var(--map-none)]" />
        {t("map.noFigure")}
      </li>
    </ul>
  );
}

function Detail({ item, name, data, onClose }: { item: Item; name: string; data: MapFigures; onClose: () => void }) {
  const { t, locale } = useT();
  const breaks = shadeBreaks(data.items.map((i) => i.value));
  const rank = data.items.findIndex((i) => i.key === item.key) + 1;
  return (
    <>
      <CardHeader
        title={name}
        subtitle={periodLabel(data.period, data.metric, t("map.asOn"))}
        actions={
          <Button variant="secondary" size="sm" onClick={onClose}>
            {t("map.showAll")}
          </Button>
        }
      />
      <p className="text-3xl font-semibold tabular-nums text-strong">
        {formatNumber(item.value, locale, 2)} <span className="text-base font-normal text-muted">{data.unit}</span>
      </p>
      <p className="mt-1 text-xs text-subtle">
        {t("map.rank")} {rank} / {data.items.length}
        {data.level === "state" && (
          <span
            aria-hidden
            className="ml-2 inline-block size-2.5 rounded-sm align-middle"
            style={{ background: SHADES[shadeIndex(item.value, breaks)] }}
          />
        )}
      </p>
      <dl className="mt-4 space-y-2 text-sm">
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-muted">{t("map.asPrinted")}</dt>
          <dd className="tabular-nums">
            {item.value_raw} {item.unit}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-muted">{t("map.status")}</dt>
          <dd>
            {item.status === "VERIFIED" ? (
              <Badge tone="success">{t("map.verified")}</Badge>
            ) : (
              <Badge tone="warning">{t("map.unverified")}</Badge>
            )}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-muted">{t("map.source")}</dt>
          <dd className="min-w-0">
            <Link
              href={sourceHref({ document_id: item.document_id, page: item.page_no }, "/map")}
              className="inline-flex items-center gap-1 text-brand underline hover:text-brand-hover"
            >
              {item.document_title}, {t("map.page")} {item.page_no}
              <ExternalLink size={14} aria-hidden />
            </Link>
          </dd>
        </div>
      </dl>
    </>
  );
}
