"use client";

import { Building2, FileCheck, FilePlus2, MessageSquareText, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import NeedsYou, { StatGridSkeleton } from "@/components/home/NeedsYou";
import QuickAsk from "@/components/home/QuickAsk";
import RecentReports from "@/components/home/RecentReports";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import PageHeader from "@/components/ui/PageHeader";
import Stat from "@/components/ui/Stat";
import { type DashboardSummary, getDashboardSummary } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatNumber } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { can, canSeeReports } from "@/lib/permissions";

const sectionTitle = "mb-3 text-base leading-6 font-semibold text-strong";

export default function HomePage() {
  const me = useMe();
  const { t, locale } = useT();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      getDashboardSummary().then(
        (s) => {
          setSummary(s);
          setError(null);
        },
        (e: unknown) => setError(errorText(e)),
      ),
    [],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const glance: { key: string; label: LabelKey; value: number; href: string; icon: React.ReactNode }[] = [];
  if (summary?.documents) {
    glance.push({
      key: "processed",
      label: "dash.processedThisMonth",
      value: summary.documents.processed_this_month,
      href: "/documents?status=PROCESSED",
      icon: <FileCheck />,
    });
  }
  if (summary?.activity) {
    glance.push({
      key: "questions",
      label: "dash.questionsThisMonth",
      value: summary.activity.questions_this_month,
      href: "/ask",
      icon: <MessageSquareText />,
    });
  }

  const starts: { href: string; label: LabelKey; icon: React.ReactNode }[] = [
    ...(can(me, "ask_questions")
      ? [{ href: "/ask", label: "askTitle" as LabelKey, icon: <MessageSquareText size={16} aria-hidden /> }]
      : []),
    ...(can(me, "upload_documents")
      ? [{ href: "/upload", label: "uploadTitle" as LabelKey, icon: <Upload size={16} aria-hidden /> }]
      : []),
    ...(can(me, "edit_reports")
      ? [
          { href: "/pq-replies/new", label: "newPqReply" as LabelKey, icon: <FilePlus2 size={16} aria-hidden /> },
          { href: "/monthly-reports/new", label: "newMonthlyReport" as LabelKey, icon: <FilePlus2 size={16} aria-hidden /> },
          { href: "/briefing-notes/new", label: "newBriefingNote" as LabelKey, icon: <FilePlus2 size={16} aria-hidden /> },
        ]
      : []),
  ];

  const showAsk = can(me, "ask_questions");
  const showReports = canSeeReports(me);

  return (
    <div className="flex flex-1 flex-col gap-6">
      <PageHeader
        title={`${t("welcome")}, ${me.name}`}
        description={t("dash.subtitle")}
        meta={
          <>
            {me.roles.map((r) => (
              <Badge key={r} tone="brand">
                {t(`role.${r}` as LabelKey)}
              </Badge>
            ))}
            <Badge tone="neutral" icon={<Building2 size={12} aria-hidden />} title={t("yourUnit")}>
              {me.org_unit.name} ({me.org_unit.code})
            </Badge>
          </>
        }
        actions={
          starts.length > 0 ? (
            <nav aria-label={t("home.startSomething")} className="flex flex-wrap justify-end gap-2">
              {starts.map((s, i) => (
                <ButtonLink key={s.href} href={s.href} variant={i === 0 ? "primary" : "secondary"} icon={s.icon}>
                  {t(s.label)}
                </ButtonLink>
              ))}
            </nav>
          ) : undefined
        }
        className="mb-0"
      />

      <div className="grid items-start gap-6 xl:grid-cols-3">
      <section aria-labelledby="home-needs" className="space-y-3 xl:col-span-2">
        <h2 id="home-needs" className={sectionTitle}>
          {t("dash.needsYou")}
        </h2>
        {error && (
          <Alert
            tone="danger"
            action={
              <Button size="sm" variant="danger-outline" onClick={() => void load()}>
                {t("dash.tryAgain")}
              </Button>
            }
          >
            {t("dash.loadFailed")} {error}
          </Alert>
        )}
        {(summary || !error) && <NeedsYou summary={summary} me={me} />}
      </section>

      {(!summary && !error) || glance.length > 0 ? (
        <section aria-labelledby="home-glance" className="space-y-3">
          <h2 id="home-glance" className={sectionTitle}>
            {t("dash.atAGlance")}
          </h2>
          {!summary ? (
            <StatGridSkeleton count={2} />
          ) : (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              {glance.map((g) => (
                <li key={g.key}>
                  <Stat
                    className="h-full"
                    href={g.href}
                    icon={g.icon}
                    tone="neutral"
                    label={t(g.label)}
                    value={formatNumber(g.value, locale)}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
      </div>

      {(showReports || showAsk) && (
        <div className="grid flex-1 gap-6 lg:grid-cols-5">
          {showReports && (
            <div className={showAsk ? "lg:col-span-3" : "lg:col-span-5"}>
              <RecentReports />
            </div>
          )}
          {showAsk && (
            <div className={showReports ? "lg:col-span-2" : "lg:col-span-5"}>
              <QuickAsk />
            </div>
          )}
        </div>
      )}

    </div>
  );
}
