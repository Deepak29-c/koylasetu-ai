"use client";

import { NotebookText, Sparkles } from "lucide-react";
import { useRef, useState } from "react";

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
import { draftBriefingNote, type ReportDraftOut } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

const MIN_TOPIC = 3;

export default function NewBriefingNotePage() {
  const me = useMe();
  const { t } = useT();
  const [topic, setTopic] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [topicError, setTopicError] = useState<string | null>(null);
  const job = useDraftRequest<ReportDraftOut>();
  const topicRef = useRef<HTMLInputElement>(null);

  // "YYYY-MM" strings compare in calendar order.
  const rangeError = from && to && from > to ? t("drafts.rangeOrder") : null;

  const header = (
    <PageHeader
      title={t("newBriefingNote")}
      description={t("briefingHelp")}
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

  function changed(set: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      set(e.target.value);
      job.inputChanged();
    };
  }

  function submit() {
    if (topic.trim().length < MIN_TOPIC) {
      setTopicError(t("drafts.topicRequired"));
      topicRef.current?.focus();
      return;
    }
    if (rangeError) return;
    void job.run((key) => draftBriefingNote({ topic: topic.trim(), from: from || null, to: to || null }, key));
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
          <legend className="sr-only">{t("briefingTitle")}</legend>
          <Card>
            <CardHeader
              title={t("drafts.briefingDetails")}
              subtitle={t("drafts.briefingPeriodHelp")}
              icon={<NotebookText />}
            />
            <div className="space-y-4">
              <Field label={t("briefingTopic")} required error={topicError}>
                <Input
                  ref={topicRef}
                  maxLength={500}
                  value={topic}
                  placeholder={t("briefingTopicPlaceholder")}
                  onChange={(e) => {
                    changed(setTopic)(e);
                    setTopicError(null);
                  }}
                />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t("fromMonth")}>
                  <Input type="month" value={from} max={to || undefined} onChange={changed(setFrom)} />
                </Field>
                <Field label={t("toMonth")} error={rangeError}>
                  <Input type="month" value={to} min={from || undefined} onChange={changed(setTo)} />
                </Field>
              </div>
            </div>
          </Card>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={job.busy}
              disabled={!!rangeError}
              icon={<Sparkles size={16} aria-hidden />}
            >
              {t("generateDraft")}
            </Button>
            {job.busy && <span className="text-xs text-muted">{t("drafts.formLocked")}</span>}
          </div>
        </fieldset>
      </form>
      <HowItWorks steps={(["drafts.step.findTopicFigures","drafts.step.computeTables","drafts.step.writeKeyPoints","drafts.step.saveDraft"] as const).map((k) => t(k))} />
      </div>

      {job.busy && job.startedAt !== null && (
        <DraftProgress
          startedAt={job.startedAt}
          secondsPerStep={20}
          detail={t("generatingBriefing")}
          steps={[
            t("drafts.step.findTopicFigures"),
            t("drafts.step.computeTables"),
            t("drafts.step.writeKeyPoints"),
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

      {job.result && <ReportDraftView draft={job.result} filePrefix="briefing-note" />}
    </div>
  );
}
