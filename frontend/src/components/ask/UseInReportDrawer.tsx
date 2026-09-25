"use client";

import { FilePlus2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import { Field, Fieldset, Input, Select } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { AskResult, ReportRow, ReportType } from "@/lib/api";
import {
  appendToReport,
  listEditableReports,
  newReportWithText,
  NotPlainText,
} from "@/lib/api-pqform";
import { answerForReport } from "@/lib/askReport";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";

const REPORT_TYPES: ReportType[] = ["briefing", "monthly", "pq_reply"];
const TITLE_MAX = 500;

type Target = "existing" | "new";

/**
 * Add an Ask answer to a report: at the end of an editable plain-text report, or as the start
 * of a new one. Part-by-part reports are left out, because their text is rendered again from
 * the parts on every save and anything added at the end would be lost.
 */
export default function UseInReportDrawer({
  result,
  question,
  onClose,
}: {
  result: AskResult;
  question: string;
  onClose: () => void;
}) {
  const { t, locale } = useT();
  const toast = useToast();
  const router = useRouter();

  const [reports, setReports] = useState<ReportRow[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [loadSeq, setLoadSeq] = useState(0);
  const [target, setTarget] = useState<Target>("existing");
  const [reportId, setReportId] = useState("");
  const [title, setTitle] = useState(() => question.trim().slice(0, TITLE_MAX));
  const [reportType, setReportType] = useState<ReportType>("briefing");
  const [fieldError, setFieldError] = useState<LabelKey | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  useEffect(() => {
    let live = true;
    listEditableReports().then(
      (rows) => {
        if (!live) return;
        setReports(rows);
        setLoadError(null);
        if (rows.length === 0) setTarget("new");
      },
      (e) => {
        if (live) setLoadError(e);
      },
    );
    return () => {
      live = false;
    };
  }, [loadSeq]);

  const addition = answerForReport(result.answer, result.citations, {
    page: t("ui.pageAbbr"),
    sources: t("sources"),
    unverified: t("ask.report.unverified"),
  });

  async function save() {
    setSaveError(null);
    if (target === "existing" && !reportId) return setFieldError("ask.report.chooseReport");
    if (target === "new" && !title.trim()) return setFieldError("ask.report.titleRequired");
    setFieldError(null);
    setSaving(true);
    try {
      const saved =
        target === "existing"
          ? await appendToReport(reportId, addition)
          : await newReportWithText(title.trim(), reportType, addition);
      toast({
        title: t(target === "existing" ? "ask.report.added" : "ask.report.created"),
        body: saved.title,
        action: { label: t("openReport"), onClick: () => router.push(`/reports/${saved.id}`) },
      });
      onClose();
    } catch (e) {
      setSaveError(e);
      setSaving(false);
    }
  }

  const noneEditable = reports !== null && reports.length === 0;

  return (
    <Drawer
      title={t("ask.report.title")}
      description={t("ask.report.description")}
      onClose={saving ? () => {} : onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={saving}>
            {t("cancel")}
          </Button>
          <Button
            variant="primary"
            loading={saving}
            disabled={target === "existing" && reports === null}
            icon={<FilePlus2 size={16} aria-hidden />}
            onClick={() => void save()}
          >
            {t(target === "existing" ? "ask.report.add" : "ask.report.create")}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <Fieldset legend={t("ask.report.target")}>
          <div className="grid gap-2 sm:grid-cols-2">
            <TargetOption
              label={t("ask.report.existing")}
              checked={target === "existing"}
              disabled={noneEditable || saving}
              onChange={() => {
                setTarget("existing");
                setFieldError(null);
              }}
            />
            <TargetOption
              label={t("ask.report.new")}
              checked={target === "new"}
              disabled={saving}
              onChange={() => {
                setTarget("new");
                setFieldError(null);
              }}
            />
          </div>
        </Fieldset>

        {target === "existing" &&
          (loadError ? (
            <Alert
              tone="danger"
              title={t("ask.report.loadFailed")}
              action={
                <Button variant="danger-outline" size="sm" onClick={() => setLoadSeq((n) => n + 1)}>
                  {t("retry")}
                </Button>
              }
            >
              {errorText(loadError, t)}
            </Alert>
          ) : reports === null ? (
            <div role="status" aria-label={t("loading")} className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-10 w-full rounded-control" />
            </div>
          ) : (
            <Field
              label={t("ask.report.pick")}
              hint={t("ask.report.pickHint")}
              error={fieldError === "ask.report.chooseReport" ? t(fieldError) : null}
              required
            >
              <Select
                value={reportId}
                disabled={saving}
                onChange={(e) => {
                  setReportId(e.target.value);
                  setFieldError(null);
                }}
              >
                <option value="">{t("ask.report.chooseReport")}</option>
                {reports.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title} · {t(`status.${r.status}` as LabelKey)} · {formatDate(r.updated_at, locale)}
                  </option>
                ))}
              </Select>
            </Field>
          ))}

        {target === "new" && (
          <div className="grid gap-4">
            {noneEditable && <Alert tone="info">{t("ask.report.noneEditable")}</Alert>}
            <Field
              label={t("ask.report.newTitle")}
              required
              error={fieldError === "ask.report.titleRequired" ? t(fieldError) : null}
            >
              <Input
                value={title}
                maxLength={TITLE_MAX}
                disabled={saving}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setFieldError(null);
                }}
              />
            </Field>
            <Field label={t("reportType")}>
              <Select
                value={reportType}
                disabled={saving}
                onChange={(e) => setReportType(e.target.value as ReportType)}
              >
                {REPORT_TYPES.map((rt) => (
                  <option key={rt} value={rt}>
                    {t(`reportType.${rt}` as LabelKey)}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        )}

        <p className="text-xs text-muted">{t("ask.report.plainOnlyNote")}</p>

        <section className="space-y-2" aria-labelledby="use-in-report-preview">
          <h3 id="use-in-report-preview" className="text-xs font-semibold text-strong">
            {t("ask.report.preview")}
          </h3>
          <pre className="max-h-64 overflow-y-auto rounded-panel border border-line bg-surface-subtle p-3 font-sans text-sm leading-6 whitespace-pre-wrap text-foreground">
            {addition}
          </pre>
        </section>

        {saveError !== null && (
          <Alert tone="danger" title={t("ask.report.saveFailed")}>
            {saveError instanceof NotPlainText ? t("ask.report.notPlainText") : errorText(saveError, t)}
          </Alert>
        )}
      </div>
    </Drawer>
  );
}

function TargetOption({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: () => void;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-center gap-2.5 rounded-panel border px-3 py-2.5 text-sm",
        checked ? "border-brand bg-brand-soft font-semibold text-brand" : "border-line-strong text-foreground",
        disabled && "cursor-not-allowed text-disabled",
      )}
    >
      <input
        type="radio"
        name="use-in-report-target"
        className="size-4 shrink-0 accent-brand"
        checked={checked}
        disabled={disabled}
        onChange={onChange}
      />
      {label}
    </label>
  );
}
