"use client";

import { TriangleAlert } from "lucide-react";

import { type ChipSource, SourcesList, TextWithCitations } from "@/components/Citation";
import Badge from "@/components/ui/Badge";
import { Field, Textarea } from "@/components/ui/Field";
import type { DraftSection, PqBlock, ReportContent } from "@/lib/api";
import { useT } from "@/lib/i18n";

import ContentTable from "./ContentTable";
import { type EditMode, knownNumbers, normaliseNumber, sectionHasText, unlinkedNumbers } from "./content";

const NUMBER_SPLIT = /([0-9०-९]+(?:[,.][0-9०-९]+)*)/g;

/** Figures per block / section that the generated text did not have. */
export function unlinkedByItem(generated: ReportContent, mode: EditMode, edits: string[]): string[][] {
  return edits.map((e, i) => unlinkedNumbers(e, knownNumbers(generated, mode, i)));
}

/** Text with source chips, and hand-typed figures marked as not linked to any source. */
function Preview({
  text,
  unlinked,
  sources,
  from,
}: {
  text: string;
  unlinked: string[];
  sources: Map<string, ChipSource>;
  from: string;
}) {
  const { t } = useT();
  const marked = new Set(unlinked);
  return (
    <TextWithCitations
      text={text}
      sources={sources}
      from={from}
      renderText={(piece, key) => (
        <span key={key}>
          {piece.split(NUMBER_SPLIT).map((p, i) =>
            i % 2 === 1 && marked.has(normaliseNumber(p)) ? (
              <mark
                key={i}
                title={t("reports.unlinkedNumber")}
                className="rounded-sm border-b-2 border-danger bg-danger-bg px-0.5 font-semibold text-danger-fg"
              >
                {p}
                <span className="sr-only"> ({t("reports.unlinkedNumber")})</span>
              </mark>
            ) : (
              p
            ),
          )}
        </span>
      )}
    />
  );
}

function UnlinkedBadge({ count }: { count: number }) {
  const { t } = useT();
  if (count === 0) return null;
  return (
    <Badge tone="danger" icon={<TriangleAlert size={12} aria-hidden />}>
      {count} {t("reports.unlinkedCount")}
    </Badge>
  );
}

function PreviewBox({ children }: { children: React.ReactNode }) {
  const { t } = useT();
  return (
    <div className="rounded-control bg-surface-subtle px-3 py-2.5">
      <p className="mb-1 text-[11px] font-semibold text-subtle">{t("reports.preview")}</p>
      <div className="text-sm leading-7 break-words text-foreground">{children}</div>
    </div>
  );
}

type ItemProps = {
  index: number;
  value: string;
  unlinked: string[];
  editable: boolean;
  onChange: (index: number, value: string) => void;
  sources: Map<string, ChipSource>;
  from: string;
};

function BlockItem({ block, ...p }: ItemProps & { block: PqBlock }) {
  const { t } = useT();
  const label = block.part ? `(${block.part})` : t("reports.reply");
  return (
    <article className="space-y-3 rounded-panel border border-line p-4">
      <header className="flex flex-wrap items-start gap-2">
        <span className="grid h-7 min-w-7 shrink-0 place-items-center rounded-full bg-brand-soft px-2 text-xs font-semibold text-brand">
          {label}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-strong">{t("reports.part")} {label}</h3>
          {block.question && <p className="mt-0.5 text-sm text-muted">{block.question}</p>}
        </div>
        {block.not_found && <Badge tone="warning" dot>{t("partNotFound")}</Badge>}
        <UnlinkedBadge count={p.unlinked.length} />
      </header>
      {p.editable && (
        <Field label={`${t("reports.answerFor")} ${label}`}>
          <Textarea value={p.value} onChange={(e) => p.onChange(p.index, e.target.value)} rows={Math.min(12, Math.max(3, Math.ceil(p.value.length / 90)))} />
        </Field>
      )}
      <PreviewBox>
        <Preview text={p.value} unlinked={p.unlinked} sources={p.sources} from={p.from} />
      </PreviewBox>
      {block.note && <p className="text-xs text-muted">{block.note}</p>}
      {block.removed_numbers?.length > 0 && (
        <p className="text-xs text-danger-fg">
          {t("removedFigures")}: {block.removed_numbers.join(", ")}
        </p>
      )}
      {block.table && (
        <div className="space-y-1.5">
          {block.annexure && (
            <p className="text-xs font-semibold text-muted">
              {t("inAnnexure")} {block.annexure}
            </p>
          )}
          <ContentTable table={block.table} sources={p.sources} from={p.from} caption={block.annexure ?? label} />
        </div>
      )}
    </article>
  );
}

function SectionItem({ section, generated, ...p }: ItemProps & { section: DraftSection; generated?: DraftSection }) {
  const { t } = useT();
  // A section cleared and saved keeps its box, so it can be filled again.
  const hasText = sectionHasText(section) || sectionHasText(generated) || !section.table;
  const heading = section.heading || t("reports.section");
  const lines = p.value.split("\n").filter((l) => l.trim());
  return (
    <article className="space-y-3 rounded-panel border border-line p-4">
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="min-w-0 flex-1 text-sm font-semibold text-strong">{heading}</h3>
        <UnlinkedBadge count={p.unlinked.length} />
      </header>
      {hasText && p.editable && (
        <Field label={`${t("reports.linesFor")} ${heading}`} hint={t("reports.linesHint")}>
          <Textarea value={p.value} onChange={(e) => p.onChange(p.index, e.target.value)} rows={Math.min(14, Math.max(3, lines.length + 1))} />
        </Field>
      )}
      {hasText && (
        <PreviewBox>
          {section.bullets ? (
            <ul className="list-disc space-y-1 pl-5">
              {lines.map((l, i) => (
                <li key={i}>
                  <Preview text={l.replace(/^\s*[•*-]\s+/, "")} unlinked={p.unlinked} sources={p.sources} from={p.from} />
                </li>
              ))}
            </ul>
          ) : (
            lines.map((l, i) => (
              <p key={i}>
                <Preview text={l} unlinked={p.unlinked} sources={p.sources} from={p.from} />
              </p>
            ))
          )}
        </PreviewBox>
      )}
      {section.removed_numbers?.length > 0 && (
        <p className="text-xs text-danger-fg">
          {t("removedFigures")}: {section.removed_numbers.join(", ")}
        </p>
      )}
      {section.table && <ContentTable table={section.table} sources={p.sources} from={p.from} caption={heading} />}
      {(section.notes ?? []).map((n, i) => (
        <p key={i} className="text-xs text-muted">
          {n}
        </p>
      ))}
    </article>
  );
}

/**
 * The report body, edited piece by piece: one box per PQ answer part or report section, so
 * the generated structure (parts, tables, sources) is never flattened into plain text.
 */
export default function ReportEditor({
  content,
  generated,
  mode,
  edits,
  unlinked,
  editable,
  onChange,
  sources,
  from,
}: {
  content: ReportContent;
  /** The first version, as the generator made it. */
  generated: ReportContent;
  mode: EditMode;
  edits: string[];
  unlinked: string[][];
  editable: boolean;
  onChange: (index: number, value: string) => void;
  sources: Map<string, ChipSource>;
  from: string;
}) {
  const { t } = useT();
  const common = { editable, onChange, sources, from };

  if (mode === "text")
    return (
      <Field label={t("reportContent")} hideLabel>
        <Textarea
          value={edits[0] ?? ""}
          onChange={(e) => onChange(0, e.target.value)}
          disabled={!editable}
          rows={16}
          className="font-mono text-[13px]"
        />
      </Field>
    );

  return (
    <div className="space-y-4">
      {mode === "sections" && (content.title || content.subtitle) && (
        <div className="text-center">
          {content.title && <p className="font-semibold text-strong">{content.title}</p>}
          {content.subtitle && <p className="text-sm text-muted">{content.subtitle}</p>}
        </div>
      )}
      {mode === "blocks" && content.header?.subject && (
        <p className="text-sm text-muted">
          <span className="font-semibold text-strong">{t("subject")}:</span> {content.header.subject}
        </p>
      )}
      {mode === "blocks"
        ? (content.blocks ?? []).map((b, i) => (
            <BlockItem key={b.id ?? i} block={b} index={i} value={edits[i] ?? ""} unlinked={unlinked[i] ?? []} {...common} />
          ))
        : (content.sections ?? []).map((s, i) => (
            <SectionItem
              key={s.id ?? i}
              section={s}
              generated={generated.sections?.[i]}
              index={i}
              value={edits[i] ?? ""}
              unlinked={unlinked[i] ?? []}
              {...common}
            />
          ))}
      <SourcesList sources={[...sources.values()]} from={from} />
    </div>
  );
}
