"use client";

import { Download, FileText } from "lucide-react";
import { useState } from "react";

import { useMe } from "@/components/AppShell";
import Alert from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import { exportReport } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

type Format = "docx" | "pdf";

/** "Draft saved" with a link to the report and, for those allowed, DOCX / PDF downloads. */
export default function DraftBanner({ reportId, filePrefix }: { reportId: string; filePrefix?: string }) {
  const me = useMe();
  const { t } = useT();
  const [downloading, setDownloading] = useState<Format | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canExport = can(me, "export_reports");

  async function download(format: Format) {
    setDownloading(format);
    setError(null);
    try {
      await exportReport(reportId, format, filePrefix);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="space-y-3">
      <Alert tone="success" title={t("drafts.saved")}>
        <p>{t("draftReady")}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <ButtonLink
            href={`/reports/${reportId}`}
            variant="primary"
            className="font-semibold! no-underline!"
            icon={<FileText size={16} aria-hidden />}
          >
            {t("openReport")}
          </ButtonLink>
          {canExport && (
            <>
              <Button
                variant="outline"
                icon={<Download size={16} aria-hidden />}
                loading={downloading === "docx"}
                disabled={downloading !== null}
                onClick={() => download("docx")}
              >
                {t("downloadDocx")}
              </Button>
              <Button
                variant="outline"
                icon={<Download size={16} aria-hidden />}
                loading={downloading === "pdf"}
                disabled={downloading !== null}
                onClick={() => download("pdf")}
              >
                {t("downloadPdf")}
              </Button>
            </>
          )}
        </div>
      </Alert>
      {error && (
        <Alert tone="danger" title={t("drafts.downloadFailed")} onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}
    </div>
  );
}
