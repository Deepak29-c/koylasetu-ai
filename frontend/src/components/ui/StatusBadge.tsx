"use client";

import { type LabelKey, useT } from "@/lib/i18n";
import { STATUS_MAPS, type StatusKind } from "@/lib/status";

import Badge, { type Tone } from "./Badge";

type Props<K extends StatusKind> = {
  kind: K;
  value: keyof (typeof STATUS_MAPS)[K];
  size?: "sm" | "md";
  className?: string;
};

export default function StatusBadge<K extends StatusKind>({ kind, value, size, className }: Props<K>) {
  const { t } = useT();
  const map = STATUS_MAPS[kind] as Record<string, { tone: Tone; label: LabelKey }>;
  const entry = map[value as string];
  if (!entry) return <Badge size={size}>{String(value)}</Badge>;
  return (
    <Badge tone={entry.tone} dot size={size} className={className}>
      {t(entry.label)}
    </Badge>
  );
}
