"use client";

import { BarChart3, FileText, LayoutTemplate, Lock } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { labelOr, withUnit } from "@/components/admin/labels";
import { useMe } from "@/components/AppShell";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import RecordList, { MonoId, type RecordItem } from "@/components/ui/RecordList";
import { Skeleton } from "@/components/ui/Skeleton";
import Tabs from "@/components/ui/Tabs";
import type { ReportType } from "@/lib/api";
import { listReportTemplates, type ReportTemplate, type TemplateSection } from "@/lib/api-admin";
import { errorText } from "@/lib/errors";
import { type LabelKey, useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

export default function AdminTemplatesPage() {
  const me = useMe();
  const { t } = useT();
  const allowed = can(me, "manage_admin");
  const [templates, setTemplates] = useState<ReportTemplate[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<ReportType | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    return listReportTemplates()
      .then(
        (list) => {
          setTemplates(list);
          setError(null);
        },
        (e: unknown) => setError(e),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!allowed) return;
    // Fetch on mount; the state updates happen after the request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [allowed, load]);

  const header = (
    <PageHeader
      title={t("adminTemplates.title")}
      description={t("adminTemplates.description")}
      breadcrumbs={[{ label: t("nav.admin") }]}
    />
  );

  if (!allowed)
    return (
      <>
        {header}
        <EmptyState icon={<Lock />} title={t("noPermission")} />
      </>
    );

  const current = templates?.find((tpl) => tpl.report_type === selected) ?? templates?.[0];

  return (
    <>
      {header}
      <div className="space-y-6">
        {error !== null && (
          <Alert
            tone="danger"
            title={t("adminTemplates.loadFailed")}
            action={
              <Button variant="danger-outline" size="sm" loading={loading} onClick={load}>
                {t("retry")}
              </Button>
            }
          >
            {errorText(error, t)}
          </Alert>
        )}

        {!templates && error === null && (
          <div role="status" aria-label={t("loading")} className="space-y-4">
            <Skeleton className="h-11 w-96 max-w-full rounded-full" />
            <Skeleton className="h-40 rounded-card" />
            <Skeleton className="h-72 rounded-card" />
          </div>
        )}

        {templates && templates.length === 0 && (
          <EmptyState icon={<LayoutTemplate />} title={t("adminTemplates.empty")} />
        )}

        {templates && current && (
          <>
            <Alert tone="info">{t("adminTemplates.readOnly")}</Alert>
            <Tabs
              label={t("adminTemplates.title")}
              value={current.report_type}
              onChange={setSelected}
              items={templates.map((tpl) => ({
                value: tpl.report_type,
                label: t(`reportType.${tpl.report_type}` as LabelKey),
                icon: <FileText size={16} aria-hidden />,
                count: tpl.sections.length,
              }))}
            />
            <TemplateView template={current} />
          </>
        )}
      </div>
    </>
  );
}

function TemplateView({ template }: { template: ReportTemplate }) {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          icon={<LayoutTemplate />}
          title={t(`reportType.${template.report_type}` as LabelKey)}
          subtitle={`${template.sections.length} ${t("adminTemplates.sectionCount")}`}
        />
        <RecordList
          columns={2}
          items={[
            { label: t("adminTemplates.printedTitle"), value: template.title },
            { label: t("adminTemplates.generator"), value: <MonoId>{template.generator}</MonoId> },
          ]}
        />
      </Card>

      <Card>
        <CardHeader title={t("adminTemplates.sections")} />
        <ol className="space-y-3">
          {template.sections.map((s, i) => (
            <SectionItem key={s.key} section={s} index={i + 1} />
          ))}
        </ol>
      </Card>
    </div>
  );
}

function SectionItem({ section, index }: { section: TemplateSection; index: number }) {
  const { t, locale } = useT();
  const items: RecordItem[] = [];
  if (section.heading) items.push({ label: t("adminTemplates.heading"), value: section.heading, mono: true, wide: true });
  items.push({
    label: t("adminTemplates.dataFrom"),
    wide: true,
    value: section.sources.length ? (
      <ul className="list-disc space-y-0.5 pl-4">
        {section.sources.map((src) => (
          <li key={src}>{labelOr(t, `adminTemplates.source.${src}`, src)}</li>
        ))}
      </ul>
    ) : null,
  });
  if (section.columns.length)
    items.push({ label: t("adminTemplates.columns"), value: <Chips values={section.columns} />, wide: true });
  if (section.rows.length) items.push({ label: t("adminTemplates.rows"), value: <Chips values={section.rows} />, wide: true });
  if (section.metrics.length)
    items.push({
      label: t("adminTemplates.metrics"),
      wide: true,
      value: <Chips values={section.metrics.map((m) => labelOr(t, `metric.${m}`, m))} />,
    });
  for (const limit of section.limits)
    items.push({
      label: labelOr(t, `adminTemplates.limit.${limit.key}`, limit.key),
      value: <span className="tabular-nums">{withUnit(limit.value, "", locale)}</span>,
    });

  return (
    <li className="rounded-panel border border-line bg-surface-subtle p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          aria-hidden
          className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-xs font-semibold text-brand tabular-nums"
        >
          {index}
        </span>
        <h3 className="text-sm font-semibold text-strong">
          {labelOr(t, `adminTemplates.section.${section.key}`, section.heading ?? section.key)}
        </h3>
        <Badge>{labelOr(t, `adminTemplates.kind.${section.kind}`, section.kind)}</Badge>
        {section.chart && (
          <Badge tone="brand" icon={<BarChart3 size={12} aria-hidden />}>
            {t("adminTemplates.chart")}
          </Badge>
        )}
        {section.optional && <Badge tone="info">{t("adminTemplates.optional")}</Badge>}
      </div>
      <RecordList columns={2} items={items} className="mt-2" />
    </li>
  );
}

function Chips({ values }: { values: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {values.map((v) => (
        <span key={v} className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs text-foreground">
          {v}
        </span>
      ))}
    </span>
  );
}
