"use client";

import { Check, PencilLine, X } from "lucide-react";
import { useEffect, useRef } from "react";

import Badge, { type Tone } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import type { DecidedItem } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";

import { useFigureText } from "./figureText";

type Decision = DecidedItem["action"];

const DECISION: Record<Decision, { label: LabelKey; tone: Tone; Icon: typeof Check }> = {
  ACCEPT: { label: "reviewActionAccept", tone: "success", Icon: Check },
  EDIT: { label: "reviewActionEdit", tone: "info", Icon: PencilLine },
  REJECT: { label: "reviewActionReject", tone: "danger", Icon: X },
};

/** The decision a reviewer took on a figure: accepted, corrected or rejected. */
export function DecisionBadge({ action }: { action: Decision }) {
  const { t } = useT();
  const { label, tone, Icon } = DECISION[action];
  return (
    <Badge tone={tone} icon={<Icon size={12} aria-hidden />}>
      {t(label)}
    </Badge>
  );
}

/** Figures that already have a decision, latest first, so a mistake can be changed. */
export default function DecidedList({
  items,
  selectedId,
  onSelect,
  footer,
}: {
  items: DecidedItem[];
  selectedId: string | null;
  onSelect: (factId: string) => void;
  footer?: React.ReactNode;
}) {
  const { t, locale } = useT();
  const fx = useFigureText();
  const listRef = useRef<HTMLUListElement>(null);

  // Keep the selected card in view when the selection moves by keyboard.
  useEffect(() => {
    if (!selectedId) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-fact="${CSS.escape(selectedId)}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  return (
    <Card padded={false} className="flex flex-col xl:min-h-0 xl:flex-1">
      <div className="border-b border-line p-4">
        <CardHeader
          className="mb-0"
          title={t("reviewTabDecided")}
          actions={<span className="text-xs font-medium text-muted tabular-nums">{items.length}</span>}
        />
      </div>
      <ul
        ref={listRef}
        aria-label={t("reviewTabDecided")}
        className="scroll-quiet max-h-[40vh] space-y-2 overflow-y-auto p-3 xl:max-h-none xl:min-h-0 xl:flex-1"
      >
        {items.map((item) => {
          const f = item.fact;
          const active = f.id === selectedId;
          return (
            <li key={f.id} data-fact={f.id}>
              <button
                type="button"
                onClick={() => onSelect(f.id)}
                aria-current={active ? "true" : undefined}
                className={cn(
                  "block w-full rounded-panel border p-3 text-left transition-colors",
                  active
                    ? "border-brand bg-brand-tint ring-2 ring-brand/20"
                    : "border-line bg-surface hover:border-brand/40 hover:bg-brand-tint",
                )}
              >
                <span className="flex flex-wrap items-center gap-1.5">
                  <DecisionBadge action={item.action} />
                  <span className="text-sm font-semibold text-strong tabular-nums">{fx.printed(f)}</span>
                </span>
                <span className="mt-2 block text-sm font-medium text-strong">{f.label || fx.metricLabel(f.metric)}</span>
                <span className="mt-1 block truncate text-xs text-subtle">
                  {fx.pageRef(item.document_title, f.page_no)}
                </span>
                <span className="mt-0.5 block truncate text-xs text-subtle">
                  {item.decided_by} · {formatDateTime(item.decided_at, locale)}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      {footer && <div className="border-t border-line px-4 py-3 xl:[@media(max-height:1000px)]:hidden">{footer}</div>}
    </Card>
  );
}
