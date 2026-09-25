"use client";

import {
  Activity,
  CalendarDays,
  CircleCheck,
  CircleX,
  ClipboardCheck,
  Clock,
  FileCheck2,
  FilePen,
  FileText,
  Flag,
  Hash,
  MessageSquareText,
  ShieldCheck,
  ThumbsUp,
  UserCheck,
  Zap,
} from "lucide-react";

import { useMe } from "@/components/AppShell";
import { Card, CardHeader } from "@/components/ui/Card";
import Stat from "@/components/ui/Stat";
import type { MetricsOut } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { can, canSeeReports } from "@/lib/permissions";

import { pctText, secondsText } from "./format";
import PercentBar from "./PercentBar";

function Group({
  id,
  title,
  icon,
  children,
  bars,
}: {
  id: string;
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  bars?: React.ReactNode;
  /** Four tiles to a row on wide screens instead of three. */
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h3 id={id} className="flex items-center gap-2 text-sm font-semibold text-strong">
        <span aria-hidden className="text-brand [&_svg]:size-4">
          {icon}
        </span>
        {title}
      </h3>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(13rem,1fr))] gap-4">{children}</div>
      {bars && <div className="grid grid-cols-[repeat(auto-fit,minmax(18rem,1fr))] gap-x-8 gap-y-4 rounded-panel border border-line p-4">{bars}</div>}
    </section>
  );
}

export default function UsageSection({ data }: { data: MetricsOut }) {
  const me = useMe();
  const { t, locale } = useT();
  const n = (v: number) => formatNumber(v, locale);
  const { qa, facts, reports } = data;

  // Tiles link to their list only when the user can open it.
  const askHref = can(me, "ask_questions") ? "/ask" : undefined;
  const reviewHref = can(me, "review_facts") ? "/review" : undefined;
  const reportsHref = (query = "") => (canSeeReports(me) ? `/reports${query}` : undefined);
  const approvalsHref = can(me, "approve_reports") ? "/approvals" : reportsHref("?status=IN_REVIEW");
  const rated = qa.helpful + qa.not_helpful;

  return (
    <Card aria-labelledby="metrics-live">
      <CardHeader
        id="metrics-live"
        title={t("metrics.liveUsage")}
        subtitle={t("metrics.liveUsageSub")}
        icon={<Activity />}
      />
      <div className="space-y-8">
        <Group
          id="metrics-qa"
          title={t("metrics.qa")}
          icon={<MessageSquareText />}
          bars={
            <>
              <PercentBar label={t("metrics.grounded")} value={qa.grounded_pct} />
              <PercentBar label={t("metrics.helpful")} value={qa.helpful_pct} />
            </>
          }
        >
          <Stat label={t("metrics.questionsTotal")} value={n(qa.questions_total)} icon={<Hash />} href={askHref} />
          <Stat
            label={t("metrics.questionsThisMonth")}
            value={n(qa.questions_this_month)}
            icon={<CalendarDays />}
            href={askHref}
          />
          <Stat
            label={t("metrics.grounded")}
            value={pctText(qa.grounded_pct, t, locale)}
            note={`${n(qa.grounded)} ${t("metrics.groundedCount")}`}
            icon={<ShieldCheck />}
            tone="success"
            href={askHref}
          />
          <Stat
            label={t("metrics.avgLatency")}
            value={secondsText(qa.avg_latency_ms, t, locale)}
            icon={<Clock />}
            tone="neutral"
          />
          <Stat
            label={t("metrics.helpful")}
            value={pctText(qa.helpful_pct, t, locale)}
            note={`${n(qa.helpful)} / ${n(rated)} ${t("metrics.ratings")}`}
            icon={<ThumbsUp />}
            tone="info"
            href={askHref}
          />
        </Group>

        <Group
          id="metrics-facts"
          title={t("metrics.figures")}
          icon={<ClipboardCheck />}
          bars={<PercentBar label={t("metrics.automationLive")} value={facts.automation_pct} />}
        >
          <Stat label={t("metrics.figuresTotal")} value={n(facts.total)} icon={<Hash />} href={reviewHref} />
          <Stat
            label={t("metrics.autoVerified")}
            value={n(facts.auto_verified)}
            icon={<CircleCheck />}
            tone="success"
            href={reviewHref}
          />
          <Stat
            label={t("metrics.reviewedVerified")}
            value={n(facts.reviewed_verified)}
            icon={<UserCheck />}
            tone="success"
            href={reviewHref}
          />
          <Stat
            label={t("metrics.flagged")}
            value={n(facts.flagged)}
            icon={<Flag />}
            tone="warning"
            href={reviewHref}
          />
          <Stat
            label={t("metrics.rejected")}
            value={n(facts.rejected)}
            icon={<CircleX />}
            tone="danger"
            href={reviewHref}
          />
          <Stat
            label={t("metrics.automationLive")}
            value={pctText(facts.automation_pct, t, locale)}
            note={t("metrics.automationNote")}
            icon={<Zap />}
            href={reviewHref}
          />
        </Group>

        <Group id="metrics-reports" title={t("metrics.reports")} icon={<FileText />}>
          <Stat label={t("metrics.reportsTotal")} value={n(reports.total)} icon={<FileText />} href={reportsHref()} />
          <Stat
            label={t("metrics.drafts")}
            value={n(reports.drafts)}
            icon={<FilePen />}
            tone="neutral"
            href={reportsHref("?status=DRAFT")}
          />
          <Stat
            label={t("metrics.inReview")}
            value={n(reports.in_review)}
            icon={<ClipboardCheck />}
            tone="warning"
            href={approvalsHref}
          />
          <Stat
            label={t("metrics.approved")}
            value={n(reports.approved)}
            icon={<FileCheck2 />}
            tone="success"
            href={reportsHref("?status=APPROVED")}
          />
        </Group>
      </div>
    </Card>
  );
}
