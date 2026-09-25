"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { useT } from "@/lib/i18n";

/** Previous / next, "Page n of N" and a box to jump to any page. */
export default function PageNav({
  page,
  total,
  onGo,
}: {
  page: number;
  total: number;
  onGo: (page: number) => void;
}) {
  const { t } = useT();
  return (
    <nav aria-label={t("viewer.pageNav")} className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        icon={<ChevronLeft size={16} aria-hidden />}
        disabled={page <= 1}
        onClick={() => onGo(page - 1)}
      >
        {t("prev")}
      </Button>
      <p aria-live="polite" className="px-1 text-sm text-strong tabular-nums">
        {t("page")} {page} {t("of")} {total}
      </p>
      <Button
        variant="outline"
        size="sm"
        disabled={page >= total}
        onClick={() => onGo(page + 1)}
        className="flex-row-reverse"
        icon={<ChevronRight size={16} aria-hidden />}
      >
        {t("next")}
      </Button>
      {total > 1 && <JumpToPage key={page} page={page} total={total} onGo={onGo} />}
    </nav>
  );
}

function JumpToPage({ page, total, onGo }: { page: number; total: number; onGo: (page: number) => void }) {
  const { t } = useT();
  const [value, setValue] = useState(String(page));
  const n = Number(value);
  const valid = Number.isInteger(n) && n >= 1 && n <= total && n !== page;
  return (
    <form
      className="flex items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onGo(n);
      }}
    >
      <Field label={t("viewer.jumpToPage")} hideLabel>
        <Input
          type="number"
          inputMode="numeric"
          min={1}
          max={total}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-8 w-20 tabular-nums"
        />
      </Field>
      <Button type="submit" variant="secondary" size="sm" disabled={!valid}>
        {t("viewer.go")}
      </Button>
    </form>
  );
}
