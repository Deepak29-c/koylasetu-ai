"use client";

import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import PageImage from "@/components/PageImage";
import {
  api,
  type DecidedItem,
  type Fact,
  type PageData,
  type ReviewItem,
  type ReviewSummary,
} from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

const SEV_STYLE = {
  high: "bg-red-100 text-red-800",
  medium: "bg-amber-100 text-amber-900",
  low: "bg-gray-100 text-gray-700",
};

type Decision = "ACCEPT" | "EDIT" | "REJECT";

const DONE_LABEL: Record<Decision, LabelKey> = {
  ACCEPT: "reviewDoneAccepted",
  EDIT: "reviewDoneCorrected",
  REJECT: "reviewDoneRejected",
};

const ACTION_LABEL: Record<Decision, LabelKey> = {
  ACCEPT: "reviewActionAccept",
  EDIT: "reviewActionEdit",
  REJECT: "reviewActionReject",
};

const ACTION_STYLE: Record<Decision, string> = {
  ACCEPT: "bg-green-100 text-green-800",
  EDIT: "bg-blue-100 text-blue-800",
  REJECT: "bg-red-100 text-red-800",
};

// What the reviewer just decided, shown for a few seconds after the queue moves on.
type Toast = { id: number; decision: Decision; figure: string; label: string | null; last: boolean };

function periodText(f: Fact) {
  if (!f.period) return "—";
  if (f.period_type === "YTD") return `Apr–${f.period} (year to date)`;
  if (f.period_type === "AS_ON") return `as on ${f.period}`;
  return f.period;
}

export default function ReviewPage() {
  const me = useMe();
  const { t } = useT();
  const [items, setItems] = useState<ReviewItem[] | null>(null);
  const [summary, setSummary] = useState<ReviewSummary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  // "decided": figures already accepted / corrected / rejected, so a mistake can be changed
  const [tab, setTab] = useState<"waiting" | "decided">("waiting");
  const [decided, setDecided] = useState<DecidedItem[] | null>(null);
  const [decidedId, setDecidedId] = useState<string | null>(null);
  const allowed = me.permissions.includes("review_facts");

  const loadDecided = useCallback(
    () =>
      api<DecidedItem[]>("/review/decided").then(
        (list) => {
          setDecided(list);
          setDecidedId((cur) => (cur && list.some((d) => d.fact.id === cur) ? cur : (list[0]?.fact.id ?? null)));
        },
        (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  );

  useEffect(() => {
    if (allowed && tab === "decided") loadDecided();
  }, [allowed, tab, loadDecided]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast((cur) => (cur?.id === toast.id ? null : cur)), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  const load = useCallback(
    () =>
      Promise.all([api<ReviewItem[]>("/review/issues"), api<ReviewSummary>("/review/summary")]).then(
        ([queue, s]) => {
          setItems(queue);
          setSummary(s);
          setSelectedId((cur) => cur ?? queue[0]?.fact.id ?? null);
        },
        (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  );

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  if (!allowed) return <p className="text-gray-600">{t("noPermission")}</p>;

  const selected = items?.find((i) => i.fact.id === selectedId) ?? null;

  const selectedDecided = decided?.find((d) => d.fact.id === decidedId) ?? null;

  function done(fact: Fact, decision: Decision, figure: string) {
    const rest = (items ?? []).filter((i) => i.fact.id !== fact.id);
    setItems(rest);
    setSelectedId(rest[0]?.fact.id ?? null);
    setToast({ id: Date.now(), decision, figure, label: fact.label, last: rest.length === 0 });
    api<ReviewSummary>("/review/summary").then(setSummary, () => {});
  }

  function changed(fact: Fact, decision: Decision, figure: string) {
    // The figure stays in the decided list, now with its new decision at the top
    setToast({ id: Date.now(), decision, figure, label: fact.label, last: false });
    setDecidedId(fact.id);
    loadDecided();
    api<ReviewSummary>("/review/summary").then(setSummary, () => {});
  }

  return (
    <div className="space-y-5">
      {/* Always rendered so screen readers announce each new decision */}
      <div role="status" aria-live="polite" className="fixed inset-x-4 bottom-4 z-50 sm:left-auto sm:right-6 sm:max-w-md">
        {toast && (
          <div
            className={`flex items-start gap-3 rounded border p-4 text-sm shadow-lg ${
              toast.decision === "REJECT" ? "border-red-300 bg-red-50 text-red-900" : "border-green-300 bg-green-50 text-green-900"
            }`}
          >
            <span aria-hidden="true" className="text-lg leading-none">
              {toast.decision === "REJECT" ? "✕" : "✓"}
            </span>
            <div className="flex-1">
              <p className="font-semibold">
                {t(DONE_LABEL[toast.decision])}: {toast.figure}
              </p>
              {toast.label && <p className="mt-0.5">{toast.label}</p>}
              <p className="mt-1 text-xs opacity-80">{t(toast.last ? "reviewDoneLast" : "reviewDoneNext")}</p>
            </div>
            <button
              onClick={() => setToast(null)}
              className="rounded px-2 py-0.5 text-xs font-medium underline hover:bg-black/5"
            >
              {t("reviewDoneClose")}
            </button>
          </div>
        )}
      </div>

      <div>
        <h1 className="text-2xl font-semibold">{t("reviewTitle")}</h1>
        <p className="text-sm text-gray-600">{t("reviewHelp")}</p>
      </div>

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            [t("totalFacts"), summary.total_facts],
            [t("autoVerified"), summary.auto_verified],
            [t("flaggedFacts"), summary.flagged],
            [t("automation"), summary.automation_percent != null ? `${summary.automation_percent}%` : "—"],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded border bg-white p-3">
              <div className="text-xs text-gray-500">{label}</div>
              <div className="text-xl font-semibold">{value}</div>
            </div>
          ))}
        </div>
      )}

      <div role="tablist" className="flex gap-2 border-b">
        {(
          [
            ["waiting", `${t("reviewTabWaiting")}${items ? ` (${items.length})` : ""}`],
            ["decided", t("reviewTabDecided")],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
              tab === key ? "border-brand text-brand" : "border-transparent text-gray-600 hover:text-brand"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}

      {tab === "decided" && (
        <>
          {decided === null && !error && <p className="text-gray-500">{t("loading")}</p>}
          {decided?.length === 0 && <p className="rounded border bg-white p-4 text-gray-700">{t("reviewNothingDecided")}</p>}
          {decided && decided.length > 0 && (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,5fr)]">
              <ul className="max-h-[75vh] space-y-2 overflow-y-auto pr-1">
                {decided.map((d) => (
                  <li key={d.fact.id}>
                    <button
                      onClick={() => setDecidedId(d.fact.id)}
                      className={`block w-full rounded border p-3 text-left text-sm ${
                        d.fact.id === decidedId ? "border-brand bg-brand-soft" : "bg-white hover:border-brand"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${ACTION_STYLE[d.action]}`}>
                          {t(ACTION_LABEL[d.action])}
                        </span>
                        <span className="font-semibold">
                          {d.fact.value_raw} {d.fact.unit}
                        </span>
                      </div>
                      <div className="mt-1 text-gray-700">{d.fact.label}</div>
                      <div className="text-xs text-gray-500">
                        {d.document_title} · p.{d.fact.page_no} · {d.decided_by}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
              {selectedDecided ? (
                <ReviewDetail
                  key={`${selectedDecided.fact.id}-${selectedDecided.decided_at}`}
                  item={selectedDecided}
                  earlier={selectedDecided}
                  onDone={changed}
                />
              ) : (
                <p className="text-gray-500">{t("selectItem")}</p>
              )}
            </div>
          )}
        </>
      )}

      {tab === "waiting" && items === null && !error && <p className="text-gray-500">{t("loading")}</p>}
      {tab === "waiting" && items?.length === 0 && (
        <p className="rounded border bg-white p-4 text-gray-700">{t("nothingToReview")}</p>
      )}

      {tab === "waiting" && items && items.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,5fr)]">
          <ul className="max-h-[75vh] space-y-2 overflow-y-auto pr-1">
            {items.map((item) => (
              <li key={item.fact.id}>
                <button
                  onClick={() => setSelectedId(item.fact.id)}
                  className={`block w-full rounded border p-3 text-left text-sm ${
                    item.fact.id === selectedId ? "border-brand bg-brand-soft" : "bg-white hover:border-brand"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${SEV_STYLE[item.worst_severity]}`}>
                      {item.issues.map((i) => i.rule_code).join(" ")}
                    </span>
                    <span className="font-semibold">
                      {item.fact.value_raw} {item.fact.unit}
                    </span>
                  </div>
                  <div className="mt-1 text-gray-700">{item.fact.label}</div>
                  <div className="text-xs text-gray-500">
                    {item.document_title} · p.{item.fact.page_no}
                  </div>
                </button>
              </li>
            ))}
          </ul>

          {selected ? (
            <ReviewDetail key={selected.fact.id} item={selected} onDone={done} />
          ) : (
            <p className="text-gray-500">{t("selectItem")}</p>
          )}
        </div>
      )}
    </div>
  );
}

function ReviewDetail({
  item,
  earlier,
  onDone,
}: {
  item: Pick<ReviewItem, "fact" | "document_title" | "issues" | "related">;
  /** Set when the figure was already decided: shown above the form; a comment is then required. */
  earlier?: Pick<DecidedItem, "action" | "comment" | "decided_by" | "decided_at">;
  onDone: (fact: Fact, decision: Decision, figure: string) => void;
}) {
  const { t } = useT();
  const f = item.fact;
  const [page, setPage] = useState<PageData | null>(null);
  const [mode, setMode] = useState<"EDIT" | null>(null);
  const [value, setValue] = useState(f.value_raw);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<PageData>(`/documents/${f.document_id}/pages/${f.page_no}`).then(setPage, (e: unknown) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }, [f.document_id, f.page_no]);

  async function submit(action: Decision) {
    if ((action !== "ACCEPT" || earlier) && !comment.trim()) {
      setError(t(earlier ? "reviewChangeNeedsComment" : "commentRequired"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Fact>(`/review/facts/${f.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          new_value: action === "EDIT" ? value : undefined,
          comment: comment.trim() || undefined,
        }),
      });
      // Show the value the server stored (for a correction, the new one), not what was typed
      const figure = action === "EDIT" ? `${f.value_raw} → ${saved.value} ${f.unit ?? ""}` : `${f.value_raw} ${f.unit ?? ""}`;
      onDone(f, action, figure.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  const rows: [string, string][] = [
    [t("metric"), f.metric.replaceAll("_", " ")],
    [t("who"), f.subsidiary ?? f.state ?? "—"],
    [t("category"), f.category ?? "—"],
    [t("period"), periodText(f)],
    [t("asPrinted"), `${f.value_raw} ${f.unit ?? ""}`],
    [t("standard"), f.value_std != null ? `${f.value_std} ${f.metric === "ob_removal" ? "Mcum" : "MT"}` : "—"],
    [t("confidence"), `${Math.round(f.confidence * 100)}%`],
  ];

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div className="space-y-2">
        <div className="text-sm text-gray-600">
          {item.document_title} · {t("page")} {f.page_no}
        </div>
        {page ? (
          <PageImage
            imagePath={page.image_url}
            width={page.width}
            height={page.height}
            highlight={f.bbox}
            alt={`${t("page")} ${f.page_no}`}
          />
        ) : (
          <p className="text-gray-500">{t("loading")}</p>
        )}
      </div>

      <div className="space-y-4">
        <div className="rounded border bg-white p-4">
          <div className="mb-2 text-sm font-medium text-gray-700">{f.label}</div>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-gray-500">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="rounded border bg-white p-4">
          <h2 className="mb-2 font-semibold">{t("why")}</h2>
          <ul className="space-y-1 text-sm">
            {item.issues.map((i) => (
              <li key={i.id}>
                <span className={`mr-2 rounded px-1.5 py-0.5 text-xs font-medium ${SEV_STYLE[i.severity]}`}>
                  {i.rule_code} · {t(`sev.${i.severity}` as LabelKey)}
                </span>
                {i.message}
              </li>
            ))}
          </ul>
          {item.related.map((r) => (
            <p key={r.id} className="mt-2 rounded bg-gray-50 p-2 text-sm">
              {t("otherSource")}: <b>{r.value_raw} {r.unit}</b> in {r.document_title}, p.{r.page_no}
            </p>
          ))}
        </div>

        <div className="space-y-3 rounded border bg-white p-4">
          {earlier && (
            <div className="rounded bg-gray-50 p-3 text-sm">
              <p>
                <span className="font-medium">{t("reviewEarlier")}:</span>{" "}
                <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${ACTION_STYLE[earlier.action]}`}>
                  {t(ACTION_LABEL[earlier.action])}
                </span>{" "}
                · {earlier.decided_by} · {new Date(earlier.decided_at).toLocaleString()}
              </p>
              {earlier.comment && <p className="mt-1 text-gray-700">“{earlier.comment}”</p>}
              <p className="mt-1 text-xs text-gray-600">{t("reviewChangeNeedsComment")}</p>
            </div>
          )}
          {mode === "EDIT" && (
            <label className="block">
              <span className="text-sm font-medium">{t("correctValue")}</span>
              <input
                value={value}
                onChange={(e) => setValue(e.target.value)}
                inputMode="decimal"
                className="mt-1 w-full rounded border px-3 py-2"
              />
            </label>
          )}
          <label className="block">
            <span className="text-sm font-medium">{t("comment")}</span>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
            />
          </label>
          {error && <p className="text-sm text-red-700">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <button
              disabled={busy}
              onClick={() => submit("ACCEPT")}
              className="rounded bg-green-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {t("accept")}
            </button>
            <button
              disabled={busy}
              onClick={() => (mode === "EDIT" ? submit("EDIT") : setMode("EDIT"))}
              className="rounded border border-brand px-4 py-2 text-sm font-medium text-brand disabled:opacity-50"
            >
              {mode === "EDIT" ? `${t("reviewEdit")} ✓` : t("reviewEdit")}
            </button>
            <button
              disabled={busy}
              onClick={() => submit("REJECT")}
              className="rounded border border-red-600 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
            >
              {t("reviewReject")}
            </button>
            {busy && <span className="self-center text-sm text-gray-500">{t("saving")}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
