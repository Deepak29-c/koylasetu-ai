"use client";

import { type ChipSource, CitationChip } from "@/components/Citation";
import Badge, { type Tone } from "@/components/ui/Badge";
import { Table, TableFrame, TD, TH, THead, TR } from "@/components/ui/Table";
import type { AskResult } from "@/lib/api";
import { type LabelKey, useT } from "@/lib/i18n";

/** Column headers that hold a figure's review state. */
const STATUS_HEADERS = new Set(["status", "fact status", "verification", "verification status", "स्थिति"]);

/** Review states of a figure, keyed by the database value. */
const FACT_STATUS: Record<string, { tone: Tone; label: LabelKey }> = {
  VERIFIED: { tone: "success", label: "ask.factStatus.VERIFIED" },
  EXTRACTED: { tone: "warning", label: "ask.factStatus.EXTRACTED" },
  FLAGGED: { tone: "warning", label: "ask.factStatus.FLAGGED" },
  REJECTED: { tone: "danger", label: "ask.factStatus.REJECTED" },
};

const NUMBER_RE = /^[-+]?\d[\d,]*(\.\d+)?(\s*(%|[A-Za-z]{1,8}))?$/;
const REF_RE = /^\[?[A-Z]\d+\]?$/;

/** Column headers that hold a figure's source reference. */
const SOURCE_HEADERS = new Set(["source", "sources", "स्रोत"]);

type ColumnKind = "status" | "source" | "number" | "text";

/** A source reference without its optional brackets: "[F3]" becomes "F3". */
function refOf(value: string): string {
  return value.replace(/^\[|\]$/g, "");
}

function columnKind(header: string, cells: string[]): ColumnKind {
  const name = header.trim().toLowerCase();
  if (STATUS_HEADERS.has(name)) return "status";
  if (SOURCE_HEADERS.has(name)) return "source";
  const filled = cells.map((c) => (c ?? "").trim()).filter(Boolean);
  if (!filled.length) return "text";
  // Only cited figures have a source entry, so a column of references is recognised by its shape alone.
  if (filled.every((c) => REF_RE.test(c))) return "source";
  if (filled.every((c) => NUMBER_RE.test(c))) return "number";
  return "text";
}

/** Figures behind a numeric answer. Each row links to the table cell it was read from. */
export default function FiguresTable({
  table,
  sources,
  from,
}: {
  table: NonNullable<AskResult["table"]>;
  sources: Map<string, ChipSource>;
  from?: string;
}) {
  const { t } = useT();
  const kinds = table.columns.map((h, i) =>
    columnKind(
      h,
      table.rows.map((r) => r[i]),
    ),
  );

  function cell(value: string, kind: ColumnKind) {
    const v = (value ?? "").trim();
    if (kind === "status") {
      const entry = FACT_STATUS[v.toUpperCase()];
      return entry ? (
        <Badge tone={entry.tone} dot>
          {t(entry.label)}
        </Badge>
      ) : v ? (
        <Badge dot>{v}</Badge>
      ) : (
        "–"
      );
    }
    if (kind === "source") {
      const s = sources.get(refOf(v));
      return s ? <CitationChip source={s} from={from} /> : v || "–";
    }
    return v || "–";
  }

  return (
    <TableFrame className="shadow-none">
      <Table caption={t("ask.figuresTitle")}>
        <THead>
          {table.columns.map((h, i) => (
            <TH key={i} align={kinds[i] === "number" ? "right" : "left"}>
              {h}
            </TH>
          ))}
        </THead>
        <tbody>
          {table.rows.map((row, r) => (
            <TR key={r}>
              {table.columns.map((_, i) => (
                <TD
                  key={i}
                  align={kinds[i] === "number" ? "right" : "left"}
                  className={kinds[i] === "number" ? "font-semibold whitespace-nowrap text-strong" : undefined}
                >
                  {cell(row[i], kinds[i])}
                </TD>
              ))}
            </TR>
          ))}
        </tbody>
      </Table>
    </TableFrame>
  );
}
