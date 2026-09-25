"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import { type DashboardSummary, getDashboardSummary } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

type Tone = "plain" | "warn" | "urgent";

const TONE_STYLE: Record<Tone, string> = {
  plain: "border-gray-200 bg-white",
  warn: "border-amber-300 bg-amber-50",
  urgent: "border-red-300 bg-red-50",
};

type Tile = { key: string; count: number; label: LabelKey; href?: string; tone?: Tone; note?: LabelKey };

function AttentionTile({ tile, t }: { tile: Tile; t: (k: LabelKey) => string }) {
  const body = (
    <>
      <span className="text-3xl font-semibold">{tile.count}</span>
      <span className="text-sm text-gray-700">{t(tile.label)}</span>
      {tile.note && <span className="text-xs text-gray-500">{t(tile.note)}</span>}
    </>
  );
  const shell = `flex flex-col gap-1 rounded border p-4 ${TONE_STYLE[tile.tone ?? "plain"]}`;
  // Tiles without an href are counts we can show but not yet open — see the review queue below.
  return tile.href ? (
    <Link href={tile.href} className={`${shell} transition hover:border-brand hover:shadow-sm`}>
      {body}
    </Link>
  ) : (
    <div className={shell}>{body}</div>
  );
}

function attentionTiles(summary: DashboardSummary): Tile[] {
  const tiles: Tile[] = [];
  const { reports, documents, review } = summary;
  if (reports) {
    tiles.push(
      { key: "overdue", count: reports.overdue, label: "dash.overdue", href: "/reports", tone: "urgent" },
      { key: "returned", count: reports.returned_to_me, label: "dash.returnedToMe", href: "/reports", tone: "warn" },
      { key: "approval", count: reports.awaiting_approval, label: "dash.awaitingApproval", href: "/reports" },
      { key: "dueSoon", count: reports.due_soon, label: "dash.dueSoon", href: "/reports", tone: "warn" },
      { key: "drafts", count: reports.my_drafts, label: "dash.myDrafts", href: "/reports" },
    );
  }
  if (review) {
    tiles.push({
      key: "facts",
      count: review.pending_facts,
      label: "dash.pendingFacts",
      href: "/review",
      tone: review.flagged_facts > 0 ? "warn" : "plain",
    });
  }
  if (documents) {
    tiles.push(
      { key: "failed", count: documents.failed, label: "dash.docsFailed", href: "/documents", tone: "urgent" },
      { key: "docReview", count: documents.needs_review, label: "dash.docsNeedsReview", href: "/documents", tone: "warn" },
      { key: "processing", count: documents.processing, label: "dash.docsProcessing", href: "/documents" },
    );
  }
  return tiles.filter((tile) => tile.count > 0);
}

function QuickAsk({ t }: { t: (k: LabelKey) => string }) {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const tooShort = question.trim().length < 3;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (tooShort) return;
        router.push(`/ask?q=${encodeURIComponent(question.trim())}`);
      }}
      className="space-y-2 rounded border bg-white p-4"
    >
      <label htmlFor="quick-ask" className="font-medium">
        {t("dash.quickAskTitle")}
      </label>
      <p className="text-sm text-gray-600">{t("dash.quickAskHelp")}</p>
      <div className="flex flex-wrap gap-2">
        <input
          id="quick-ask"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t("askPlaceholder")}
          className="min-w-0 flex-1 rounded border px-3 py-2"
        />
        <button
          type="submit"
          disabled={tooShort}
          className="rounded bg-brand px-6 py-2 font-medium text-white disabled:opacity-50"
        >
          {t("askButton")}
        </button>
      </div>
    </form>
  );
}

export default function HomePage() {
  const me = useMe();
  const { t } = useT();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      getDashboardSummary().then(
        (s) => {
          setSummary(s);
          setError(null);
        },
        (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
      ),
    [],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const tiles = summary ? attentionTiles(summary) : [];
  const glance: { key: string; label: LabelKey; value: number }[] = [];
  if (summary?.documents) {
    glance.push({
      key: "processed",
      label: "dash.processedThisMonth",
      value: summary.documents.processed_this_month,
    });
  }
  if (summary?.activity) {
    glance.push({
      key: "questions",
      label: "dash.questionsThisMonth",
      value: summary.activity.questions_this_month,
    });
  }

  const shortcuts: { href: string; label: LabelKey }[] = [
    ...(me.permissions.includes("upload_documents") ? [{ href: "/upload", label: "uploadTitle" as LabelKey }] : []),
    ...(me.permissions.includes("view_processing") ? [{ href: "/documents", label: "documents" as LabelKey }] : []),
    ...(summary?.reports ? [{ href: "/reports", label: "reports" as LabelKey }] : []),
    ...(me.permissions.includes("view_audit") ? [{ href: "/audit", label: "auditLog" as LabelKey }] : []),
    ...(me.permissions.includes("manage_admin") ? [{ href: "/admin/users", label: "users" as LabelKey }] : []),
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">
          {t("welcome")}, {me.name}
        </h1>
        <p className="text-gray-600">{t("dash.subtitle")}</p>
      </div>

      {me.permissions.includes("ask_questions") && <QuickAsk t={t} />}

      <section className="space-y-3">
        <h2 className="font-semibold">{t("dash.needsYou")}</h2>
        {error && (
          <p className="flex flex-wrap items-center gap-3 rounded border border-red-300 bg-red-50 p-3 text-red-800">
            {t("dash.loadFailed")} {error}
            <button onClick={load} className="rounded border border-red-400 px-2 py-0.5">
              {t("dash.tryAgain")}
            </button>
          </p>
        )}
        {!summary && !error && <p className="text-gray-500">{t("loading")}</p>}
        {summary && tiles.length === 0 && <p className="text-gray-600">{t("dash.allClear")}</p>}
        {tiles.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {tiles.map((tile) => (
              <AttentionTile key={tile.key} tile={tile} t={t} />
            ))}
          </div>
        )}
      </section>

      {glance.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-semibold">{t("dash.atAGlance")}</h2>
          <dl className="grid gap-3 sm:grid-cols-2">
            {glance.map((g) => (
              <div key={g.key} className="rounded border bg-white p-4">
                <dt className="text-sm text-gray-600">{t(g.label)}</dt>
                <dd className="text-2xl font-semibold">{g.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {shortcuts.length > 0 && (
        <section className="space-y-3">
          <h2 className="font-semibold">{t("dash.shortcuts")}</h2>
          <div className="flex flex-wrap gap-3">
            {shortcuts.map((s) => (
              <Link key={s.href} href={s.href} className="rounded border border-brand px-4 py-2 text-brand">
                {t(s.label)}
              </Link>
            ))}
          </div>
        </section>
      )}

      <dl className="grid max-w-xl grid-cols-[max-content_1fr] gap-x-6 gap-y-2 rounded border bg-white p-4 text-sm">
        <dt className="text-gray-500">{t("yourRoles")}</dt>
        <dd>{me.roles.map((r) => t(`role.${r}` as LabelKey)).join(", ")}</dd>
        <dt className="text-gray-500">{t("yourUnit")}</dt>
        <dd>
          {me.org_unit.name} ({me.org_unit.code})
        </dd>
      </dl>
    </div>
  );
}
