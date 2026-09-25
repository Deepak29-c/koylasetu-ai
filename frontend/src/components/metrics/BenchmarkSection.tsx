"use client";

import { BadgeCheck, Clock, FlaskConical, Link2, ShieldCheck, Target, Zap } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import RecordList, { MonoId } from "@/components/ui/RecordList";
import Stat from "@/components/ui/Stat";
import type { MetricsOut } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";

import { pctText, secondsText } from "./format";
import PercentBar from "./PercentBar";

type Benchmark = NonNullable<MetricsOut["benchmark"]>;

const RUN_COMMAND = "python eval/run_eval.py";

/** The five headline numbers, in the order the guide lists them. */
const HEADLINES: {
  key: keyof Benchmark;
  label: LabelKey;
  note: LabelKey;
  icon: React.ReactNode;
}[] = [
  { key: "numeric_accuracy_pct", label: "metrics.numericAccuracy", note: "metrics.numericAccuracyNote", icon: <Target /> },
  { key: "time_saved_pct", label: "metrics.timeSaved", note: "metrics.timeSavedNote", icon: <Clock /> },
  { key: "automation_pct", label: "metrics.automation", note: "metrics.automationNote", icon: <Zap /> },
  { key: "grounded_pct", label: "metrics.grounded", note: "metrics.groundedNote", icon: <ShieldCheck /> },
  { key: "citation_correct_pct", label: "metrics.citationCorrect", note: "metrics.citationCorrectNote", icon: <Link2 /> },
];

export default function BenchmarkSection({ benchmark }: { benchmark: MetricsOut["benchmark"] }) {
  const { t, locale } = useT();

  if (!benchmark)
    return (
      <Card aria-labelledby="metrics-benchmark">
        <CardHeader id="metrics-benchmark" title={t("metrics.benchmark")} icon={<FlaskConical />} />
        <EmptyState icon={<FlaskConical />} title={t("metrics.noBenchmark")}>
          <p>{t("metrics.noBenchmarkBody")}</p>
          <p className="mt-3">
            <MonoId className="text-[13px] text-strong">{RUN_COMMAND}</MonoId>
          </p>
        </EmptyState>
      </Card>
    );

  const value = (key: keyof Benchmark) => benchmark[key] as number | null;
  const n = (v: number) => formatNumber(v, locale);

  return (
    <Card aria-labelledby="metrics-benchmark">
      <CardHeader
        id="metrics-benchmark"
        title={t("metrics.benchmark")}
        subtitle={`${t("metrics.benchmarkSub")} · ${t("metrics.benchmarkRunOn")} ${formatDate(benchmark.run_date, locale)}`}
        icon={<FlaskConical />}
      />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-5">
        {HEADLINES.map((h) => (
          <Stat
            key={h.key}
            label={t(h.label)}
            value={pctText(value(h.key), t, locale)}
            note={t(h.note)}
            icon={h.icon}
            className="items-start"
          />
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section aria-labelledby="metrics-glance" className="rounded-panel border border-line p-4">
          <h3 id="metrics-glance" className="mb-3 text-sm font-semibold text-strong">
            {t("metrics.atAGlance")}
          </h3>
          <div className="space-y-4">
            {HEADLINES.map((h) => (
              <PercentBar key={h.key} label={t(h.label)} value={value(h.key)} />
            ))}
            <PercentBar label={t("metrics.allCorrect")} value={benchmark.all_correct_pct} />
          </div>
        </section>
        <section aria-labelledby="metrics-run" className="rounded-panel border border-line p-4">
          <h3 id="metrics-run" className="mb-1 flex items-center gap-2 text-sm font-semibold text-strong">
            <BadgeCheck size={16} aria-hidden className="text-brand" />
            {t("metrics.runDetails")}
          </h3>
          <RecordList
            columns={2}
            items={[
              { label: t("metrics.runDate"), value: formatDate(benchmark.run_date, locale), wide: true },
              { label: t("metrics.questionsAsked"), value: n(benchmark.questions_asked) },
              { label: t("metrics.answered"), value: n(benchmark.answered) },
              { label: t("metrics.notFound"), value: n(benchmark.not_found) },
              { label: t("metrics.errors"), value: n(benchmark.errors) },
              { label: t("metrics.allCorrect"), value: pctText(benchmark.all_correct_pct, t, locale) },
              { label: t("metrics.medianLatency"), value: secondsText(benchmark.median_latency_ms, t, locale) },
            ]}
          />
        </section>
      </div>
    </Card>
  );
}
