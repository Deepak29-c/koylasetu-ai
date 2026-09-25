"use client";

import { Info } from "lucide-react";

import { type ChipSource, SourcesList, TextWithCitations } from "@/components/Citation";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { PqBlock, PqDraftOut } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

import DraftBanner from "./DraftBanner";
import DraftTable from "./DraftTable";
import RemovedFigures from "./RemovedFigures";
import WarningsList from "./WarningsList";

function BlockCard({ block, sources, from }: { block: PqBlock; sources: Map<string, ChipSource>; from: string }) {
  const { t } = useT();
  return (
    <Card as="article" className="space-y-4">
      <div className="flex items-start gap-3">
        {block.part && (
          <Badge tone="brand" size="md" className="mt-0.5 shrink-0">
            <span className="sr-only">{t("drafts.part")} </span>({block.part})
          </Badge>
        )}
        <h3 className="min-w-0 flex-1 text-sm leading-6 font-semibold whitespace-pre-wrap text-strong">
          {block.question}
        </h3>
      </div>

      {block.not_found && (
        <Alert tone="warning" title={t("partNotFound")}>
          {t("drafts.notFoundHelp")}
        </Alert>
      )}

      {block.text && (
        <div className="rounded-panel border border-line bg-surface-subtle px-4 py-3">
          <p className="mb-1 text-xs font-semibold text-muted">{t("drafts.answer")}</p>
          <p className={block.not_found ? "leading-7 whitespace-pre-wrap text-muted" : "leading-7 whitespace-pre-wrap"}>
            <TextWithCitations text={block.text} sources={sources} from={from} />
          </p>
        </div>
      )}

      {block.note && (
        <p className="flex items-start gap-2 text-xs text-muted">
          <Info size={14} aria-hidden className="mt-0.5 shrink-0" />
          <span>
            <span className="font-semibold">{t("drafts.note")}:</span> {block.note}
          </span>
        </p>
      )}

      <RemovedFigures numbers={block.removed_numbers} />

      {block.table && (
        <div className="space-y-2">
          {block.annexure && (
            <Badge tone="info" dot>
              {t("inAnnexure")} {block.annexure}
            </Badge>
          )}
          <DraftTable
            table={block.table}
            sources={sources}
            from={from}
            caption={block.annexure ?? `${t("drafts.table")}${block.part ? ` (${block.part})` : ""}`}
          />
        </div>
      )}
    </Card>
  );
}

/** A generated PQ reply: saved banner, warnings, one card per part, and the sources. */
export default function PqDraftView({ draft }: { draft: PqDraftOut }) {
  const { t } = useT();
  const content = draft.report.content_json;
  const blocks = content.blocks ?? [];
  const sourceList: ChipSource[] = content.sources ?? [];
  const sources = new Map(sourceList.map((s) => [s.id, s]));
  // The draft is already saved, so Back from a source returns to its report page, not an empty form.
  const from = `/reports/${draft.report.id}`;

  return (
    <div className="space-y-6">
      <DraftBanner reportId={draft.report.id} filePrefix="pq-reply" />
      <WarningsList warnings={content.warnings} />

      <section aria-labelledby="pq-reply-parts" className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="pq-reply-parts" className="text-base font-semibold text-strong">
            {t("drafts.replyParts")}
          </h2>
          <Badge tone="neutral" dot>
            {t("splitBy")}: {t(`split.${draft.split_method}` as LabelKey)}
          </Badge>
        </div>
        {blocks.length === 0 ? (
          <Alert tone="warning" title={t("partNotFound")}>
            {t("drafts.notFoundHelp")}
          </Alert>
        ) : (
          blocks.map((b) => <BlockCard key={b.id} block={b} sources={sources} from={from} />)
        )}
      </section>

      <SourcesList sources={sourceList} from={from} />
    </div>
  );
}
