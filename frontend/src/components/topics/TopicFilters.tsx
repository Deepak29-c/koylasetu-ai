"use client";

import { FilterX, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { useT, type LabelKey } from "@/lib/i18n";
import type { WordCloudFilters } from "@/lib/topics";

export const SUBSIDIARIES = ["ECL", "BCCL", "CCL", "NCL", "WCL", "SECL", "MCL", "NEC", "CMPDI", "SCCL"];
const SOURCES = ["questions", "documents", "all"];
const SESSIONS = ["budget", "monsoon", "winter"];

export const DEFAULT_FILTERS: WordCloudFilters = { source: "questions" };

/** A year field is valid when empty or a four-digit year in the range the API accepts. */
export function yearError(value: string | undefined): LabelKey | null {
  if (!value) return null;
  if (!/^\d{4}$/.test(value)) return "topics.yearInvalid";
  const n = Number(value);
  return n < 1950 || n > 2100 ? "topics.yearInvalid" : null;
}

/** Errors for the two year fields, including a range that runs backwards. */
export function yearErrors(f: WordCloudFilters): { from: LabelKey | null; to: LabelKey | null } {
  const from = yearError(f.from);
  const to = yearError(f.to);
  if (!from && !to && f.from && f.to && Number(f.from) > Number(f.to)) {
    return { from: null, to: "topics.yearOrder" };
  }
  return { from, to };
}

export function isDefault(f: WordCloudFilters): boolean {
  return (
    (f.source ?? "questions") === "questions" && !f.house && !f.session && !f.subsidiary && !f.from && !f.to
  );
}

type TopicFiltersProps = {
  value: WordCloudFilters;
  onChange: (next: WordCloudFilters) => void;
};

export default function TopicFilters({ value, onChange }: TopicFiltersProps) {
  const { t } = useT();
  const errors = yearErrors(value);
  // A half-typed year is not flagged until the person leaves the field.
  const [editing, setEditing] = useState<"from" | "to" | null>(null);
  const shown = (key: "from" | "to") => {
    const e = errors[key];
    if (!e) return undefined;
    return editing === key && (value[key]?.length ?? 0) < 4 ? undefined : t(e);
  };

  function set(key: keyof WordCloudFilters, v: string) {
    onChange({ ...value, [key]: v || undefined });
  }

  return (
    <Card>
      <CardHeader
        title={t("ui.filters")}
        subtitle={t("topics.filtersHint")}
        icon={<SlidersHorizontal />}
        actions={
          <Button
            variant="ghost"
            size="sm"
            icon={<FilterX size={14} aria-hidden />}
            disabled={isDefault(value)}
            onClick={() => onChange(DEFAULT_FILTERS)}
          >
            {t("ui.clearFilters")}
          </Button>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <Field label={t("textSource")}>
          <Select value={value.source ?? "questions"} onChange={(e) => set("source", e.target.value)}>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {t(`source.${s}` as LabelKey)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("house")}>
          <Select value={value.house ?? ""} onChange={(e) => set("house", e.target.value)}>
            <option value="">{t("allHouses")}</option>
            <option value="LS">{t("house.LS")}</option>
            <option value="RS">{t("house.RS")}</option>
          </Select>
        </Field>
        <Field label={t("session")}>
          <Select value={value.session ?? ""} onChange={(e) => set("session", e.target.value)}>
            <option value="">{t("allSessions")}</option>
            {SESSIONS.map((s) => (
              <option key={s} value={s}>
                {t(`session.${s}` as LabelKey)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("subsidiary")}>
          <Select value={value.subsidiary ?? ""} onChange={(e) => set("subsidiary", e.target.value)}>
            <option value="">{t("allSubsidiaries")}</option>
            {SUBSIDIARIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("yearFrom")} error={shown("from")}>
          <Input
            type="text"
            inputMode="numeric"
            maxLength={4}
            placeholder="2019"
            autoComplete="off"
            value={value.from ?? ""}
            onChange={(e) => set("from", e.target.value.replace(/\D/g, ""))}
            onFocus={() => setEditing("from")}
            onBlur={() => setEditing(null)}
            className="tabular-nums"
          />
        </Field>
        <Field label={t("yearTo")} error={shown("to")}>
          <Input
            type="text"
            inputMode="numeric"
            maxLength={4}
            placeholder="2025"
            autoComplete="off"
            value={value.to ?? ""}
            onChange={(e) => set("to", e.target.value.replace(/\D/g, ""))}
            onFocus={() => setEditing("to")}
            onBlur={() => setEditing(null)}
            className="tabular-nums"
          />
        </Field>
      </div>
    </Card>
  );
}
