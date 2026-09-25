import { api, type DocumentStatus, type ReportType } from "@/lib/api";

/** Administration screens: validation rules, report templates, system status (all read-only). */

export type Severity = "high" | "medium" | "low";

export type RuleThreshold = { key: string; value: number; unit: string };

export type AdminRule = {
  code: string;
  name: string;
  checks: string;
  severities: Severity[];
  thresholds: RuleThreshold[];
  uses_other_documents: boolean;
  /** Open issues from this rule in the caller's units. */
  open_issues: number;
};

export type TemplateLimit = { key: string; value: number };

export type TemplateSection = {
  key: string;
  kind: "header" | "lines" | "bullets" | "table" | "sources";
  /** The heading printed in the report, exactly as the generator writes it. */
  heading: string | null;
  sources: string[];
  columns: string[];
  rows: string[];
  metrics: string[];
  chart: boolean;
  optional: boolean;
  limits: TemplateLimit[];
};

export type ReportTemplate = {
  report_type: ReportType;
  title: string | null;
  generator: string;
  sections: TemplateSection[];
};

export type Health = "ok" | "warn" | "error";

export type HealthCheck = {
  key: string;
  status: Health;
  /** Short outcome code, translated on screen; `message` has the English detail. */
  code: string;
  message: string;
  details: Record<string, unknown>;
};

export type SystemStatus = {
  checked_at: string;
  version: string;
  overall: Health;
  checks: HealthCheck[];
  queues: { name: string; queued: number; failed: number }[] | null;
  workers: number | null;
  models: { name: string; role: "llm" | "embed"; pulled: boolean | null }[];
  storage: { path: string; free_bytes: number; total_bytes: number } | null;
  documents: Record<DocumentStatus, number> | null;
  flags: { ingest_inline: boolean; allow_external_calls: boolean };
};

export function listAdminRules(): Promise<AdminRule[]> {
  return api<AdminRule[]>("/admin/rules");
}

export function listReportTemplates(): Promise<ReportTemplate[]> {
  return api<ReportTemplate[]>("/admin/templates");
}

export function getSystemStatus(): Promise<SystemStatus> {
  return api<SystemStatus>("/admin/status");
}
