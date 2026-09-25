"use client";

import { CalendarDays, Sparkles } from "lucide-react";
import { useState } from "react";

import { useMe } from "@/components/AppShell";
import DraftProgress from "@/components/drafts/DraftProgress";
import HowItWorks from "@/components/drafts/HowItWorks";
import { useDraftRequest } from "@/components/drafts/useDraftRequest";
import ReportDraftView from "@/components/ReportDraftView";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { draftMonthlyReport, type ReportDraftOut } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

/** Last month as "YYYY-MM": the usual month to report on. */
function lastMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() - 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function NewMonthlyReportPage() {
  const me = useMe();
  const { t } = useT();
  const [month, setMonth] = useState(lastMonth);
  const [monthError, setMonthError] = useState<string | null>(null);
  const job = useDraftRequest<ReportDraftOut>();

  const header = (
    <PageHeader
      title={t("newMonthlyReport")}
      description={t("monthlyHelp")}
      breadcrumbs={[{ label: t("reports"), href: "/reports" }]}
    />
  );

  if (!can(me, "edit_reports")) {
    return (
      <div>
        {header}
        <Alert tone="warning">{t("noPermission")}</Alert>
      </div>
    );
  }

  function submit() {
    if (!month) {
      setMonthError(t("drafts.monthRequired"));
      return;
    }
    void job.run((key) => draftMonthlyReport(month, key));
  }

  return (
    <div className="space-y-6">
      {header}

      <div className="grid items-start gap-6 xl:grid-cols-2">
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <fieldset disabled={job.busy} className="min-w-0 space-y-6">
          <legend className="sr-only">{t("monthlyTitle")}</legend>
          <Card>
            <CardHeader title={t("drafts.reportPeriod")} icon={<CalendarDays />} />
            <Field
              label={t("reportMonth")}
              required
              hint={t("drafts.monthHelp")}
              error={monthError}
              className="max-w-xs"
            >
              <Input
                type="month"
                value={month}
                onChange={(e) => {
                  setMonth(e.target.value);
                  setMonthError(null);
                  job.inputChanged();
                }}
              />
            </Field>
          </Card>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" variant="primary" size="lg" loading={job.busy} icon={<Sparkles size={16} aria-hidden />}>
              {t("generateDraft")}
            </Button>
            {job.busy && <span className="text-xs text-muted">{t("drafts.formLocked")}</span>}
          </div>
        </fieldset>
      </form>
      <HowItWorks steps={(["drafts.step.collectFigures","drafts.step.computeTables","drafts.step.writeRemarks","drafts.step.saveDraft"] as const).map((k) => t(k))} />
      </div>

      {job.busy && job.startedAt !== null && (
        <DraftProgress
          startedAt={job.startedAt}
          secondsPerStep={8}
          detail={t("generatingMonthly")}
          steps={[
            t("drafts.step.collectFigures"),
            t("drafts.step.computeTables"),
            t("drafts.step.writeRemarks"),
            t("drafts.step.saveDraft"),
          ]}
        />
      )}

      {job.error && (
        <Alert
          tone="danger"
          title={t("drafts.failed")}
          action={
            <Button variant="outline" size="sm" onClick={submit}>
              {t("retry")}
            </Button>
          }
        >
          {job.error}
        </Alert>
      )}

      {job.result && <ReportDraftView draft={job.result} filePrefix="monthly-report" />}
    </div>
  );
}
