"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { createReport, type ReportType } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { type LabelKey, useT } from "@/lib/i18n";

export const REPORT_TYPES: ReportType[] = ["pq_reply", "monthly", "briefing"];

/** A report started from a blank page, for anything the generators do not cover. */
export default function NewReportDrawer({ onClose }: { onClose: () => void }) {
  const { t } = useT();
  const router = useRouter();
  const toast = useToast();
  const [type, setType] = useState<ReportType>("briefing");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const r = await createReport({ report_type: type, title: title.trim(), due_date: due || null });
      toast({ title: t("reports.created"), body: r.title });
      router.push(`/reports/${r.id}`);
    } catch (err) {
      setError(errorText(err, t));
      setBusy(false);
    }
  }

  return (
    <Drawer
      title={t("createReportTitle")}
      description={t("reports.blankHelp")}
      onClose={busy ? () => {} : onClose}
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            {t("cancel")}
          </Button>
          <Button variant="primary" type="submit" form="new-report" loading={busy} disabled={!title.trim()}>
            {busy ? t("creating") : t("createReportButton")}
          </Button>
        </>
      }
    >
      <form id="new-report" onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label={t("reportType")} required>
          <Select value={type} onChange={(e) => setType(e.target.value as ReportType)}>
            {REPORT_TYPES.map((rt) => (
              <option key={rt} value={rt}>
                {t(`reportType.${rt}` as LabelKey)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("title")} required>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500} />
        </Field>
        <Field label={t("dueDate")}>
          <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </Field>
      </form>
    </Drawer>
  );
}
