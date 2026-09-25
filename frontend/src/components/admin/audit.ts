import type { Tone } from "@/components/ui/Badge";
import type { AuditLogRow } from "@/lib/api";
import type { LabelKey } from "@/lib/i18n";

type T = (key: LabelKey) => string;

/** "create_pq_draft" -> "Create pq draft", for action codes that have no label yet. */
export function humanise(code: string): string {
  const words = code.replace(/[_.-]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : code;
}

/** The translated name of an action code, falling back to a readable form of the code. */
export function actionLabel(t: T, code: string): string {
  return t(`auditAction.${code}` as LabelKey) || humanise(code);
}

export function entityLabel(t: T, entity: string): string {
  return t(`auditEntity.${entity}` as LabelKey) || humanise(entity);
}

const ACTION_TONES: Record<string, Tone> = {
  login_failed: "danger",
  review_reject: "danger",
  reject_report: "warning",
  review_accept: "success",
  approve_report: "success",
};

/** Badge tone for an action code; most actions are plain records of work. */
export function actionTone(code: string): Tone {
  return ACTION_TONES[code] ?? "neutral";
}

/** Where the record an entry is about can be opened, when it has its own page. */
export function entityHref(row: AuditLogRow): string | null {
  if (row.entity === "topics") return "/topics";
  if (!row.entity_id) return null;
  if (row.entity === "document") return `/documents/${row.entity_id}?from=${encodeURIComponent("/audit")}`;
  if (row.entity === "report") return `/reports/${row.entity_id}`;
  return null;
}

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const raw = typeof value === "string" ? value : JSON.stringify(value);
  // A leading = + - @ tab or CR makes a spreadsheet read the cell as a formula; a quote keeps it text.
  const s = /^[=+\-@\t\r]/.test(raw) ? `'${raw}` : raw;
  // Quote every cell so commas, quotes and line breaks inside values stay in one cell.
  return `"${s.replace(/"/g, '""')}"`;
}

export function buildAuditCsv(rows: AuditLogRow[], t: T): string {
  const header = [
    t("auditWhen"),
    t("audit.csvUserName"),
    t("audit.csvUserEmail"),
    t("audit.csvActionCode"),
    t("auditAction"),
    t("audit.entity"),
    t("audit.entityId"),
    t("auditIp"),
    t("audit.csvDetails"),
  ];
  const lines = rows.map((r) =>
    [
      r.created_at,
      r.user?.name ?? t("auditSystem"),
      r.user?.email ?? "",
      r.action,
      actionLabel(t, r.action),
      r.entity ?? "",
      r.entity_id ?? "",
      r.ip ?? "",
      r.details_json && Object.keys(r.details_json).length ? r.details_json : "",
    ]
      .map(csvCell)
      .join(","),
  );
  return [header.map(csvCell).join(","), ...lines].join("\r\n");
}

/** Local calendar date as YYYY-MM-DD. */
export function todayStamp(d = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Saves text as a file. The byte-order mark makes spreadsheet apps read it as UTF-8 (Hindi). */
export function downloadCsv(csv: string, filename: string) {
  const blob = new Blob(["﻿", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
