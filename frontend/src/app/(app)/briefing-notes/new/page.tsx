"use client";

import { useState } from "react";

import { useMe } from "@/components/AppShell";
import ReportDraftView, { newKey } from "@/components/ReportDraftView";
import { draftBriefingNote, type ReportDraftOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

export default function NewBriefingNotePage() {
  const me = useMe();
  const { t } = useT();
  const [topic, setTopic] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<ReportDraftOut | null>(null);
  // Same key while the form is unchanged, so a retry returns the draft already made.
  const [requestKey, setRequestKey] = useState<string | null>(null);

  if (!me.permissions.includes("edit_reports")) return <p className="text-gray-600">{t("noPermission")}</p>;

  function changed<T>(set: (v: T) => void) {
    return (v: T) => {
      set(v);
      setRequestKey(null);
    };
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || topic.trim().length < 3) return;
    const key = requestKey ?? newKey();
    setRequestKey(key);
    setBusy(true);
    setError(null);
    setDraft(null);
    try {
      setDraft(await draftBriefingNote({ topic: topic.trim(), from: from || null, to: to || null }, key));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const input = "mt-1 w-full rounded border px-3 py-2";

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("briefingTitle")}</h1>
        <p className="text-sm text-gray-600">{t("briefingHelp")}</p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4 rounded border bg-white p-4">
        <label className="block">
          <span className="text-sm font-medium">{t("briefingTopic")}</span>
          <input
            required
            minLength={3}
            maxLength={500}
            value={topic}
            placeholder={t("briefingTopicPlaceholder")}
            onChange={(e) => changed(setTopic)(e.target.value)}
            className={input}
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="text-sm font-medium">{t("fromMonth")}</span>
            <input type="month" value={from} onChange={(e) => changed(setFrom)(e.target.value)} className={input} />
          </label>
          <label className="block">
            <span className="text-sm font-medium">{t("toMonth")}</span>
            <input type="month" value={to} onChange={(e) => changed(setTo)(e.target.value)} className={input} />
          </label>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={busy || topic.trim().length < 3}
            className="rounded bg-brand px-6 py-2.5 font-medium text-white disabled:opacity-50"
          >
            {t("generateDraft")}
          </button>
          {busy && <span className="text-sm text-gray-600">{t("generatingBriefing")}</span>}
        </div>
      </form>

      {error && <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
      {draft && <ReportDraftView draft={draft} filePrefix="briefing-note" />}
    </div>
  );
}
