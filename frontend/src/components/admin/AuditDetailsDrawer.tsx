"use client";

import { ArrowUpRight } from "lucide-react";

import { Button, ButtonLink } from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { CardHeader } from "@/components/ui/Card";
import Drawer from "@/components/ui/Drawer";
import RecordList, { type RecordItem } from "@/components/ui/RecordList";
import type { AuditLogRow } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useT } from "@/lib/i18n";

import { actionLabel, actionTone, entityHref, entityLabel, humanise } from "./audit";

function DetailValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <>–</>;
  if (typeof value === "object") {
    return (
      <pre className="mt-1 max-h-72 overflow-auto rounded-control bg-surface-sunken p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-foreground">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <>{String(value)}</>;
}

/** One audit entry as label/value panels: who, what, when, then whatever details were recorded. */
export default function AuditDetailsDrawer({ row, onClose }: { row: AuditLogRow; onClose: () => void }) {
  const { t, locale } = useT();
  const href = entityHref(row);
  const details = row.details_json ? Object.entries(row.details_json) : [];

  const summary: RecordItem[] = [
    { label: t("auditWhen"), value: formatDateTime(row.created_at, locale) },
    {
      label: t("auditWho"),
      value: row.user ? (
        <>
          <span className="block font-medium">{row.user.name}</span>
          <span className="block text-xs text-muted">{row.user.email}</span>
        </>
      ) : (
        t("auditSystem")
      ),
    },
    {
      label: t("auditAction"),
      value: (
        <Badge tone={actionTone(row.action)} dot>
          {actionLabel(t, row.action)}
        </Badge>
      ),
    },
    { label: t("audit.entity"), value: row.entity ? entityLabel(t, row.entity) : null },
    { label: t("audit.entityId"), value: row.entity_id, mono: true },
    { label: t("auditIp"), value: row.ip, mono: true },
    { label: t("audit.entryId"), value: row.id, mono: true, wide: true },
  ];

  return (
    <Drawer
      title={actionLabel(t, row.action)}
      eyebrow={t("audit.detailsTitle")}
      description={formatDateTime(row.created_at, locale)}
      onClose={onClose}
      footer={
        <>
          {href && (
            <ButtonLink href={href} variant="outline" icon={<ArrowUpRight size={16} aria-hidden />}>
              {t("audit.open")}
            </ButtonLink>
          )}
          <Button variant="primary" onClick={onClose}>
            {t("ui.close")}
          </Button>
        </>
      }
    >
      <div className="space-y-6">
        <section>
          <CardHeader title={t("audit.recordTitle")} level={3} className="mb-1" />
          <RecordList items={summary} columns={2} />
        </section>
        <section>
          <CardHeader title={t("audit.extraDetails")} level={3} className="mb-1" />
          {details.length > 0 ? (
            <RecordList
              items={details.map(([key, value]) => ({
                label: humanise(key),
                value: <DetailValue value={value} />,
                mono: typeof value !== "object" || value === null,
              }))}
            />
          ) : (
            <p className="text-sm text-muted">{t("audit.noExtraDetails")}</p>
          )}
        </section>
      </div>
    </Drawer>
  );
}
