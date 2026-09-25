"use client";

import { type ChipSource, CitationChip, TextWithCitations } from "@/components/Citation";

const BARE_IDS = /^[A-Z]\d+(?:\s*,\s*[A-Z]\d+)*$/;

/** A cell that is only source ids ("S1, S3") becomes chips; any other cell keeps its text. */
function Cell({ value, sources, from }: { value: string; sources: Map<string, ChipSource>; from: string }) {
  if (BARE_IDS.test(value.trim())) {
    const ids = value.split(",").map((x) => x.trim());
    if (ids.every((id) => sources.has(id)))
      return (
        <>
          {ids.map((id) => (
            <CitationChip key={id} source={sources.get(id)!} from={from} />
          ))}
        </>
      );
  }
  return <TextWithCitations text={value} sources={sources} from={from} />;
}

/** A generated table (annexure, monthly figures), shown read-only with its source chips. */
export default function ContentTable({
  table,
  sources,
  from,
  caption,
}: {
  table: { columns: string[]; rows: string[][] };
  sources: Map<string, ChipSource>;
  from: string;
  caption?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-panel border border-line">
      <table className="w-full border-separate border-spacing-0 text-left text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {table.columns.map((c, i) => (
              <th
                key={i}
                scope="col"
                className="border-b border-line bg-surface-sunken px-3 py-2 text-xs font-semibold whitespace-nowrap text-muted"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r} className="[&>td]:border-b [&>td]:border-line last:[&>td]:border-b-0">
              {row.map((cell, j) =>
                j === 0 ? (
                  <th key={j} scope="row" className="px-3 py-2 text-left font-medium text-strong">
                    <Cell value={String(cell)} sources={sources} from={from} />
                  </th>
                ) : (
                  <td key={j} className="px-3 py-2 tabular-nums">
                    <Cell value={String(cell)} sources={sources} from={from} />
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
