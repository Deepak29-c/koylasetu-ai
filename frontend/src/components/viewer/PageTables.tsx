"use client";

import { Table as TableIcon } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { Table, TableFrame, TD, TH, THead, TR } from "@/components/ui/Table";
import type { PageData } from "@/lib/api";
import { useT } from "@/lib/i18n";

/** Tables read from the page. The first extracted row is the header row. */
export default function PageTables({ tables }: { tables: PageData["tables"] }) {
  const { t } = useT();
  if (!tables.length) return null;
  return (
    <Card aria-labelledby="page-tables">
      <CardHeader id="page-tables" icon={<TableIcon />} title={t("tablesOnPage")} />
      <div className="space-y-5">
        {tables.map((tb, n) => {
          const [head = [], ...body] = tb.rows_json;
          const width = Math.max(head.length, ...body.map((r) => r.length));
          const title = tb.table_title || `${t("viewer.untitledTable")} ${n + 1}`;
          return (
            <section key={tb.id} className="space-y-2">
              <h3 className="text-sm font-semibold text-strong">{title}</h3>
              <TableFrame className="shadow-none">
                <Table caption={title} className="text-xs">
                  <THead>
                    {Array.from({ length: width }, (_, c) => (
                      <TH key={c}>{head[c] ?? ""}</TH>
                    ))}
                  </THead>
                  <tbody>
                    {body.map((row, r) => (
                      <TR key={r}>
                        {Array.from({ length: width }, (_, c) => (
                          <TD key={c} className="h-auto py-2 whitespace-nowrap tabular-nums">
                            {row[c] ?? ""}
                          </TD>
                        ))}
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </TableFrame>
            </section>
          );
        })}
      </div>
    </Card>
  );
}
