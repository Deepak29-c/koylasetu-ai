"use client";

import { Info } from "lucide-react";

import { type ChipSource, SourcesList, TextWithCitations } from "@/components/Citation";
import DraftBanner from "@/components/drafts/DraftBanner";
import DraftTable from "@/components/drafts/DraftTable";
import RemovedFigures from "@/components/drafts/RemovedFigures";
import WarningsList from "@/components/drafts/WarningsList";
import Alert from "@/components/ui/Alert";
import { Card, CardHeader } from "@/components/ui/Card";
import type { DraftSection, ReportDraftOut } from "@/lib/api";
import { useT } from "@/lib/i18n";

function SectionCard({
  section,
  sources,
  from,
}: {
  section: DraftSection;
  sources: Map<string, ChipSource>;
  from: string;
}) {
  return (
    <Card as={section.heading ? "section" : "div"} className="space-y-3">
      {section.heading && <CardHeader title={section.heading} level={3} className="mb-1" />}
      {section.lines.length > 0 &&
        (section.bullets ? (
          <ul className="list-disc space-y-1.5 pl-5 leading-7 marker:text-subtle">
            {section.lines.map((line, i) => (
              <li key={i}>
                <TextWithCitations text={line} sources={sources} from={from} />
              </li>
            ))}
          </ul>
        ) : (
          <div className="space-y-2">
            {section.lines.map((line, i) => (
              <p key={i} className="leading-7">
                <TextWithCitations text={line} sources={sources} from={from} />
              </p>
            ))}
          </div>
        ))}
      <RemovedFigures numbers={section.removed_numbers} />
      {section.table && (
        <DraftTable table={section.table} sources={sources} from={from} caption={section.heading ?? undefined} />
      )}
      {section.notes.length > 0 && (
        <ul className="space-y-1 text-xs text-muted">
          {section.notes.map((n, i) => (
            <li key={i} className="flex items-start gap-2">
              <Info size={14} aria-hidden className="mt-0.5 shrink-0" />
              <span>{n}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** A generated monthly report / briefing note: saved banner, sections, tables, source chips, downloads. */
export default function ReportDraftView({ draft, filePrefix }: { draft: ReportDraftOut; filePrefix: string }) {
  const { t } = useT();
  const content = draft.report.content_json;
  const sourceList: ChipSource[] = content.sources ?? [];
  const sources = new Map(sourceList.map((s) => [s.id, s]));
  // The draft is already saved, so Back from a source returns to its report page, not an empty form.
  const from = `/reports/${draft.report.id}`;

  return (
    <div className="space-y-6">
      <DraftBanner reportId={draft.report.id} filePrefix={filePrefix} />
      {content.remarks_by === "rule" && (
        <Alert tone="info" title={t("drafts.remarksByRuleTitle")}>
          {t("remarksByRule")}
        </Alert>
      )}
      <WarningsList warnings={content.warnings} />

      <section aria-labelledby="report-draft-title" className="space-y-4">
        <Card className="text-center">
          <h2 id="report-draft-title" className="text-lg font-semibold text-strong">
            {content.title || draft.report.title || t("drafts.draftTitle")}
          </h2>
          {content.subtitle && <p className="mt-1 text-sm text-muted">{content.subtitle}</p>}
        </Card>
        {(content.sections ?? []).map((s) => (
          <SectionCard key={s.id} section={s} sources={sources} from={from} />
        ))}
      </section>

      <SourcesList sources={sourceList} from={from} />
    </div>
  );
}
