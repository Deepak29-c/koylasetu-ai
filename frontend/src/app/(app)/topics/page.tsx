"use client";

// Topic explorer (guide section 11): word cloud, top topics, per-topic trend by year, and a
// topic's questions. The server returns weighted words as JSON; the cloud is drawn here.

import { useEffect, useMemo, useState } from "react";

import { useMe } from "@/components/AppShell";
import { useT, type LabelKey } from "@/lib/i18n";
import {
  getWordCloud,
  listTopicQuestions,
  listTopics,
  rerunTopics,
  type TopicQuestion,
  type TopicRow,
  type TopicRun,
  type WordCloud,
  type WordCloudFilters,
} from "@/lib/topics";

const SUBSIDIARIES = ["ECL", "BCCL", "CCL", "NCL", "WCL", "SECL", "MCL", "NEC", "CMPDI", "SCCL"];

function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export default function TopicsPage() {
  const me = useMe();
  const { t } = useT();
  const isAdmin = me.permissions.includes("manage_admin");

  const [filters, setFilters] = useState<WordCloudFilters>({ source: "questions" });
  const [cloud, setCloud] = useState<WordCloud | null>(null);
  const [run, setRun] = useState<TopicRun | null>(null);
  const [selected, setSelected] = useState<TopicRow | null>(null);
  const [year, setYear] = useState<string | undefined>(undefined);
  const [questions, setQuestions] = useState<TopicQuestion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    getWordCloud(filters).then(setCloud, (e: unknown) => setError(errorText(e)));
  }, [filters]);

  useEffect(() => {
    listTopics().then(
      (r) => {
        setRun(r);
        setSelected(r.topics[0] ?? null);
      },
      (e: unknown) => setError(errorText(e)),
    );
  }, []);

  useEffect(() => {
    if (!selected) return;
    listTopicQuestions(selected.id, year).then(setQuestions, (e: unknown) => setError(errorText(e)));
  }, [selected, year]);

  // One shared year axis for every topic, so trends are comparable.
  const years = useMemo(() => {
    const all = new Set<string>();
    for (const topic of run?.topics ?? []) {
      for (const y of Object.keys(topic.period_counts.year ?? {})) all.add(y);
    }
    const sorted = [...all].sort();
    if (sorted.length === 0) return [];
    const out: string[] = [];
    for (let y = Number(sorted[0]); y <= Number(sorted[sorted.length - 1]); y++) out.push(String(y));
    return out;
  }, [run]);

  function setFilter(key: keyof WordCloudFilters, value: string) {
    setCloud(null);
    setFilters({ ...filters, [key]: value || undefined });
  }

  function selectTopic(topic: TopicRow) {
    setQuestions(null);
    setYear(undefined);
    setSelected(topic);
  }

  async function rerun() {
    try {
      const res = await rerunTopics();
      setNotice(res.queued ? t("rerunQueued") : t("rerunOffline"));
    } catch (e) {
      setError(errorText(e));
    }
  }

  const maxSize = Math.max(1, ...(run?.topics ?? []).map((x) => x.size));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("topicsTitle")}</h1>
          <p className="mt-1 max-w-3xl text-sm text-gray-600">{t("topicsHelp")}</p>
        </div>
        {isAdmin && (
          <button onClick={rerun} className="rounded border border-brand px-3 py-1.5 text-sm text-brand hover:bg-brand-soft">
            {t("rerunTopics")}
          </button>
        )}
      </div>
      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {notice && <p className="rounded border border-blue-200 bg-blue-50 p-3 text-blue-900">{notice}</p>}

      <section className="space-y-3 rounded border bg-white p-4">
        <h2 className="text-lg font-semibold">{t("wordCloud")}</h2>
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <FilterSelect label={t("textSource")} value={filters.source ?? "questions"} onChange={(v) => setFilter("source", v)}
            options={["questions", "documents", "all"].map((s) => [s, t(`source.${s}` as LabelKey)])} />
          <FilterSelect label={t("house")} value={filters.house ?? ""} onChange={(v) => setFilter("house", v)}
            options={[["", t("allHouses")], ["LS", t("house.LS")], ["RS", t("house.RS")]]} />
          <FilterSelect label={t("session")} value={filters.session ?? ""} onChange={(v) => setFilter("session", v)}
            options={[["", t("allSessions")], ...["budget", "monsoon", "winter"].map((s) => [s, t(`session.${s}` as LabelKey)] as [string, string])]} />
          <FilterSelect label={t("subsidiary")} value={filters.subsidiary ?? ""} onChange={(v) => setFilter("subsidiary", v)}
            options={[["", t("allSubsidiaries")], ...SUBSIDIARIES.map((s) => [s, s] as [string, string])]} />
          <YearInput label={t("yearFrom")} value={filters.from} onChange={(v) => setFilter("from", v)} />
          <YearInput label={t("yearTo")} value={filters.to} onChange={(v) => setFilter("to", v)} />
        </div>
        {!cloud && <p className="text-gray-500">{t("loading")}</p>}
        {cloud && cloud.words.length === 0 && <p className="text-gray-500">{t("noWords")}</p>}
        {cloud && cloud.words.length > 0 && (
          <>
            <WordCloudView words={cloud.words} />
            <p className="text-xs text-gray-500">
              {cloud.texts} {t("textsCounted")}
            </p>
          </>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <div className="space-y-2 rounded border bg-white p-4">
          <h2 className="text-lg font-semibold">{t("topTopics")}</h2>
          {!run && <p className="text-gray-500">{t("loading")}</p>}
          {run && run.topics.length === 0 && <p className="text-gray-600">{t("noTopicsYet")}</p>}
          {run?.built_at && (
            <p className="text-xs text-gray-500">
              {t("builtAt")} {new Date(run.built_at).toLocaleString()} · {run.total_questions} {t("questionsWord")}
            </p>
          )}
          <ul className="space-y-2">
            {run?.topics.map((topic) => (
              <li key={topic.id}>
                <button
                  onClick={() => selectTopic(topic)}
                  className={`w-full rounded border p-2 text-left hover:bg-brand-soft ${
                    selected?.id === topic.id ? "border-brand bg-brand-soft" : ""
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-medium">{topic.label}</span>
                    <span className="text-sm text-gray-600">{topic.size}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded bg-gray-100">
                    <div className="h-1.5 rounded bg-brand" style={{ width: `${(topic.size / maxSize) * 100}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-gray-600">{topic.keywords.join(", ")}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {selected && (
          <div className="space-y-3 rounded border bg-white p-4">
            <h2 className="text-lg font-semibold">{selected.label}</h2>
            <div>
              <h3 className="text-sm font-medium">{t("questionsPerYear")}</h3>
              <YearBars
                years={years}
                counts={selected.period_counts.year ?? {}}
                active={year}
                onPick={(y) => {
                  setQuestions(null);
                  setYear(y === year ? undefined : y);
                }}
              />
              <p className="text-xs text-gray-500">
                {t("clickBarHint")}{" "}
                {year && (
                  <button className="text-brand underline" onClick={() => { setQuestions(null); setYear(undefined); }}>
                    {t("allYears")}
                  </button>
                )}
              </p>
            </div>
            <h3 className="text-sm font-medium">
              {t("questionsInTopic")} {year ? `(${year})` : ""}
            </h3>
            {!questions && <p className="text-gray-500">{t("loading")}</p>}
            <ul className="divide-y">
              {questions?.map((q) => (
                <li key={q.id} className="py-2 text-sm">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-medium">{q.subject || q.question_text.slice(0, 80)}</span>
                    <span className="text-xs text-gray-500">
                      {t(`house.${q.house}` as LabelKey)} {q.q_no ? `Q${q.q_no}` : ""} {q.answer_date ?? ""}
                    </span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 text-gray-700">{q.question_text}</p>
                  {q.keywords.length > 0 && (
                    <p className="mt-0.5 text-xs text-gray-500">
                      {t("keywords")}: {q.keywords.join(", ")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}

function FilterSelect(props: {
  label: string;
  value: string;
  options: (string[] | [string, string])[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="font-medium">{props.label}</span>
      <select value={props.value} onChange={(e) => props.onChange(e.target.value)} className="mt-1 block rounded border px-2 py-1.5">
        {props.options.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </label>
  );
}

function YearInput(props: { label: string; value?: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="font-medium">{props.label}</span>
      <input
        type="number"
        min={1990}
        max={2100}
        defaultValue={props.value}
        onBlur={(e) => props.onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && props.onChange((e.target as HTMLInputElement).value)}
        className="mt-1 block w-24 rounded border px-2 py-1.5"
        placeholder="2019"
      />
    </label>
  );
}

/** Words sized by weight (square-root scale, so a few big words don't swamp the rest). */
function WordCloudView({ words }: { words: { text: string; weight: number }[] }) {
  const max = Math.max(...words.map((w) => w.weight));
  // Alphabetical order scatters big and small words; stable between renders.
  const ordered = [...words].sort((a, b) => a.text.localeCompare(b.text));
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded bg-gray-50 p-4 leading-tight">
      {ordered.map((w) => {
        const scale = Math.sqrt(w.weight / max);
        return (
          <span
            key={w.text}
            title={`${w.text}: ${w.weight}`}
            className="cursor-default text-brand"
            style={{ fontSize: `${0.75 + scale * 1.9}rem`, opacity: 0.45 + scale * 0.55, fontWeight: scale > 0.6 ? 600 : 400 }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
}

/** One-series bar chart: questions per year, a bar per year on a shared axis. */
function YearBars(props: {
  years: string[];
  counts: Record<string, number>;
  active?: string;
  onPick: (year: string) => void;
}) {
  const { years, counts } = props;
  if (years.length === 0) return <p className="text-sm text-gray-500">—</p>;
  const max = Math.max(1, ...years.map((y) => counts[y] ?? 0));
  const W = 480;
  const H = 150;
  const pad = { l: 28, r: 8, t: 12, b: 22 };
  const slot = (W - pad.l - pad.r) / years.length;
  const barW = Math.min(36, slot - 2);
  const y0 = H - pad.b;
  const scale = (v: number) => ((H - pad.t - pad.b) * v) / max;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-xl" role="img" aria-label="questions per year">
      <line x1={pad.l} x2={W - pad.r} y1={y0} y2={y0} stroke="#d1d5db" />
      <text x={pad.l - 6} y={pad.t + 4} textAnchor="end" fontSize="10" fill="#6b7280">
        {max}
      </text>
      <line x1={pad.l} x2={W - pad.r} y1={pad.t} y2={pad.t} stroke="#f3f4f6" />
      {years.map((y, i) => {
        const v = counts[y] ?? 0;
        const h = Math.max(scale(v), 5); // room for the rounded top
        const x = pad.l + i * slot + (slot - barW) / 2;
        const dim = props.active && props.active !== y;
        return (
          <g key={y} onClick={() => v > 0 && props.onPick(y)} className={v > 0 ? "cursor-pointer" : ""}>
            <title>{`${y}: ${v}`}</title>
            {/* Hit area bigger than the bar. */}
            <rect x={pad.l + i * slot} y={pad.t} width={slot} height={y0 - pad.t} fill="transparent" />
            {v > 0 && (
              <path
                d={`M${x},${y0} v${-(h - 4)} q0,-4 4,-4 h${barW - 8} q4,0 4,4 v${h - 4} z`}
                fill="var(--brand)"
                opacity={dim ? 0.35 : 1}
              />
            )}
            {v > 0 && (
              <text x={x + barW / 2} y={y0 - h - 3} textAnchor="middle" fontSize="10" fill="#374151">
                {v}
              </text>
            )}
            <text x={pad.l + i * slot + slot / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="#6b7280">
              {y}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
