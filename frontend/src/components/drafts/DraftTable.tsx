"use client";

import { type ChipSource, CitationChip, TextWithCitations } from "@/components/Citation";
import { Table, TD, TH, THead, TR } from "@/components/ui/Table";
import { cn } from "@/lib/cn";

export type DraftTableData = { columns: string[]; rows: string[][] };

/** Header names of a source column, in the languages the drafts are written in. */
const SOURCE_HEADERS = new Set(["source", "sources", "source(s)", "स्रोत"]);
const MARKER = /^\[?\s*[A-Z]\d+\s*\]?$/;
const NUMERIC = /^[\s\d.,%+\-–−()]+$/;
/** How the generators write a figure that was not found. */
const EMPTY_CELLS = new Set(["", "-", "–", "—"]);

/** The source ids in a cell made only of markers ("S1, S2" or "[S1] [S2]"), else null. */
function markerIds(cell: string): string[] | null {
  const tokens = cell.split(/[\s,;]+/).filter(Boolean);
  if (!tokens.length || !tokens.every((tok) => MARKER.test(tok))) return null;
  return tokens.map((tok) => tok.replace(/[[\]\s]/g, ""));
}

/** A source column: its header says so, or every filled cell is only markers of known sources. */
function isSourceColumn(table: DraftTableData, col: number, sources: Map<string, ChipSource>): boolean {
  const header = (table.columns[col] ?? "").trim().toLowerCase();
  if (SOURCE_HEADERS.has(header)) return true;
  const cells = table.rows.map((r) => (r[col] ?? "").trim()).filter((c) => !EMPTY_CELLS.has(c));
  return cells.length > 0 && cells.every((c) => markerIds(c)?.every((id) => sources.has(id)));
}

function isNumeric(cell: string): boolean {
  return /\d/.test(cell) && NUMERIC.test(cell);
}

/**
 * A table in a draft. Cells that are only source markers (and every cell of a source
 * column) become citation chips; figures are right-aligned.
 */
export default function DraftTable({
  table,
  sources,
  from,
  caption,
}: {
  table: DraftTableData;
  sources: Map<string, ChipSource>;
  from?: string;
  caption?: string;
}) {
  const sourceCols = new Set(table.columns.map((_, i) => i).filter((i) => isSourceColumn(table, i, sources)));
  // A figure column: every filled cell is a number, so its header aligns right too.
  const numericCols = new Set(
    table.columns
      .map((_, i) => i)
      .filter((i) => {
        if (sourceCols.has(i)) return false;
        const cells = table.rows.map((r) => (r[i] ?? "").trim()).filter((c) => !EMPTY_CELLS.has(c));
        return cells.length > 0 && cells.every(isNumeric);
      }),
  );

  function cellContent(cell: string, col: number) {
    const ids = markerIds(cell.trim());
    // Outside a source column, a short code like "A1" is only a marker when it names a source.
    if (ids && (sourceCols.has(col) || ids.every((id) => sources.has(id)))) {
      return (
        <span className="inline-flex flex-wrap gap-1">
          {ids.map((id, k) => {
            const s = sources.get(id);
            return s ? (
              <CitationChip key={`${id}-${k}`} source={s} from={from} />
            ) : (
              <span key={`${id}-${k}`} className="font-mono text-xs">
                {id}
              </span>
            );
          })}
        </span>
      );
    }
    if (sourceCols.has(col) && EMPTY_CELLS.has(cell.trim())) {
      return <span className="text-subtle">{cell || "–"}</span>;
    }
    return <TextWithCitations text={cell} sources={sources} from={from} />;
  }

  return (
    <div className="overflow-hidden rounded-panel border border-line bg-surface">
      <Table caption={caption}>
        <THead>
          {table.columns.map((c, i) => (
            <TH key={i} align={numericCols.has(i) ? "right" : "left"}>
              {c}
            </TH>
          ))}
        </THead>
        <tbody>
          {table.rows.map((row, i) => (
            <TR key={i}>
              {table.columns.map((_, j) => {
                const cell = row[j] ?? "";
                const numeric = numericCols.has(j) || (!sourceCols.has(j) && j > 0 && isNumeric(cell.trim()));
                return (
                  <TD key={j} align={numeric ? "right" : "left"} className={cn(j === 0 && "font-medium text-strong")}>
                    {cellContent(cell, j)}
                  </TD>
                );
              })}
            </TR>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
