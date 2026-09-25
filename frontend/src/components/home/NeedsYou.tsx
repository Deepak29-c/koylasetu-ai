"use client";

import {
  CalendarClock,
  CalendarX2,
  CircleCheckBig,
  ClipboardCheck,
  FileClock,
  FilePenLine,
  FileSearch,
  FileX,
  Inbox,
  Undo2,
} from "lucide-react";

import type { Tone } from "@/components/ui/Badge";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import Stat from "@/components/ui/Stat";
import type { DashboardSummary, Me } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

type Tile = {
  key: string;
  count: number;
  label: LabelKey;
  href: string;
  tone: Tone;
  icon: React.ReactNode;
  note?: string;
};

/** Tiles for the things waiting on this person; each opens the list already filtered to them. */
function attentionTiles(summary: DashboardSummary, me: Me, t: (k: LabelKey) => string, locale: string): Tile[] {
  const tiles: Tile[] = [];
  const { reports, documents, review } = summary;
  if (reports) {
    tiles.push(
      {
        key: "overdue",
        count: reports.overdue,
        label: "dash.overdue",
        href: "/reports?due=overdue",
        tone: "danger",
        icon: <CalendarX2 />,
      },
      {
        key: "returned",
        count: reports.returned_to_me,
        label: "dash.returnedToMe",
        href: "/reports?status=RETURNED&mine=1",
        tone: "warning",
        icon: <Undo2 />,
      },
      {
        key: "approval",
        count: reports.awaiting_approval,
        label: "dash.awaitingApproval",
        href: can(me, "approve_reports") ? "/approvals" : "/reports?status=IN_REVIEW",
        tone: "info",
        icon: <Inbox />,
      },
      {
        key: "dueSoon",
        count: reports.due_soon,
        label: "dash.dueSoon",
        href: "/reports?due=soon",
        tone: "warning",
        icon: <CalendarClock />,
      },
      {
        key: "drafts",
        count: reports.my_drafts,
        label: "dash.myDrafts",
        href: "/reports?status=DRAFT&mine=1",
        tone: "brand",
        icon: <FilePenLine />,
      },
    );
  }
  if (review) {
    tiles.push({
      key: "facts",
      count: review.pending_facts,
      label: "dash.pendingFacts",
      href: "/review",
      tone: review.flagged_facts > 0 ? "warning" : "brand",
      icon: <ClipboardCheck />,
      note:
        review.flagged_facts > 0 ? `${formatNumber(review.flagged_facts, locale)} ${t("dash.flaggedFacts")}` : undefined,
    });
  }
  if (documents) {
    tiles.push(
      {
        key: "failed",
        count: documents.failed,
        label: "dash.docsFailed",
        href: "/documents?status=FAILED",
        tone: "danger",
        icon: <FileX />,
      },
      {
        key: "docReview",
        count: documents.needs_review,
        label: "dash.docsNeedsReview",
        href: "/documents?status=NEEDS_REVIEW",
        tone: "warning",
        icon: <FileSearch />,
      },
      {
        key: "processing",
        count: documents.processing,
        label: "dash.docsProcessing",
        href: "/documents?status=PROCESSING",
        tone: "info",
        icon: <FileClock />,
      },
    );
  }
  return tiles.filter((tile) => tile.count > 0);
}

export function StatGridSkeleton({ count = 3 }: { count?: number }) {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className="h-28 rounded-card sm:h-[76px]" />
      ))}
    </div>
  );
}

/** The counts that need this person, only those above zero, or an all-clear message. */
export default function NeedsYou({ summary, me }: { summary: DashboardSummary | null; me: Me }) {
  const { t, locale } = useT();
  if (!summary) return <StatGridSkeleton />;
  const tiles = attentionTiles(summary, me, t, locale);
  if (tiles.length === 0) {
    return (
      <EmptyState compact icon={<CircleCheckBig />} title={t("dash.allClear")}>
        {t("home.allClearBody")}
      </EmptyState>
    );
  }
  return (
    <ul className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
      {tiles.map((tile) => (
        <li key={tile.key}>
          <Stat
            className="h-full"
            href={tile.href}
            icon={tile.icon}
            tone={tile.tone}
            label={t(tile.label)}
            value={formatNumber(tile.count, locale)}
            note={tile.note}
          />
        </li>
      ))}
    </ul>
  );
}
