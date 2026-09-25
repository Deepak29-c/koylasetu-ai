import type { Tone } from "@/components/ui/Badge";
import type { AskResult, DocumentStatus, ReportStatus } from "@/lib/api";
import type { LabelKey } from "@/lib/i18n";

/**
 * One place that decides how each state looks. Screens show a state with
 * <StatusBadge kind="…" value={…} /> instead of keeping their own colour maps.
 */

export const DOCUMENT_STATUS: Record<DocumentStatus, { tone: Tone; label: LabelKey }> = {
  UPLOADED: { tone: "neutral", label: "status.UPLOADED" },
  PROCESSING: { tone: "info", label: "status.PROCESSING" },
  PROCESSED: { tone: "success", label: "status.PROCESSED" },
  NEEDS_REVIEW: { tone: "warning", label: "status.NEEDS_REVIEW" },
  FAILED: { tone: "danger", label: "status.FAILED" },
};

export const REPORT_STATUS: Record<ReportStatus, { tone: Tone; label: LabelKey }> = {
  DRAFT: { tone: "neutral", label: "reportStatus.DRAFT" },
  IN_REVIEW: { tone: "info", label: "reportStatus.IN_REVIEW" },
  RETURNED: { tone: "warning", label: "reportStatus.RETURNED" },
  APPROVED: { tone: "success", label: "reportStatus.APPROVED" },
  EXPORTED: { tone: "brand", label: "reportStatus.EXPORTED" },
};

export const SEVERITY: Record<"high" | "medium" | "low", { tone: Tone; label: LabelKey }> = {
  high: { tone: "danger", label: "sev.high" },
  medium: { tone: "warning", label: "sev.medium" },
  low: { tone: "neutral", label: "sev.low" },
};

export const CONFIDENCE: Record<AskResult["confidence"], { tone: Tone; label: LabelKey }> = {
  high: { tone: "success", label: "conf.high" },
  medium: { tone: "warning", label: "conf.medium" },
  low: { tone: "danger", label: "conf.low" },
};

export const UPLOAD_RESULT: Record<"created" | "duplicate" | "rejected", { tone: Tone; label: LabelKey }> = {
  created: { tone: "success", label: "created" },
  duplicate: { tone: "warning", label: "duplicate" },
  rejected: { tone: "danger", label: "rejected" },
};

export const USER_ACTIVE: Record<"active" | "inactive", { tone: Tone; label: LabelKey }> = {
  active: { tone: "success", label: "active" },
  inactive: { tone: "neutral", label: "inactive" },
};

export const HEALTH: Record<"ok" | "warn" | "error", { tone: Tone; label: LabelKey }> = {
  ok: { tone: "success", label: "adminStatus.ok" },
  warn: { tone: "warning", label: "adminStatus.warn" },
  error: { tone: "danger", label: "adminStatus.error" },
};

export const STATUS_MAPS = {
  document: DOCUMENT_STATUS,
  report: REPORT_STATUS,
  severity: SEVERITY,
  confidence: CONFIDENCE,
  upload: UPLOAD_RESULT,
  user: USER_ACTIVE,
  health: HEALTH,
} as const;

export type StatusKind = keyof typeof STATUS_MAPS;
