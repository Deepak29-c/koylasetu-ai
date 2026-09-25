"use client";

import Badge from "@/components/ui/Badge";
import type { ReportRow, ReportStatus } from "@/lib/api";
import { daysUntil } from "@/lib/format";
import { useT } from "@/lib/i18n";

/** Reports still being worked on; a due date only matters for these. */
export const OPEN_STATUSES: ReportStatus[] = ["DRAFT", "IN_REVIEW", "RETURNED"];
export const DUE_SOON_DAYS = 7;

export type DueState = "overdue" | "soon" | null;

export function dueState(r: Pick<ReportRow, "status" | "due_date">): DueState {
  if (!OPEN_STATUSES.includes(r.status)) return null;
  const days = daysUntil(r.due_date);
  if (days === null) return null;
  if (days < 0) return "overdue";
  return days <= DUE_SOON_DAYS ? "soon" : null;
}

/** "Overdue" / "Due in 3 days" next to a due date, for open reports only. */
export default function DueBadge({ report }: { report: Pick<ReportRow, "status" | "due_date"> }) {
  const { t } = useT();
  const state = dueState(report);
  if (!state) return null;
  const days = daysUntil(report.due_date) ?? 0;
  if (state === "overdue") return <Badge tone="danger" dot>{t("dash.overdue")}</Badge>;
  return (
    <Badge tone="warning" dot>
      {days === 0 ? t("reports.dueToday") : `${t("reports.dueIn")} ${days} ${t(days === 1 ? "reports.day" : "reports.days")}`}
    </Badge>
  );
}
