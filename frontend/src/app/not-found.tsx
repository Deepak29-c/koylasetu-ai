"use client";

import { FileQuestion } from "lucide-react";

import { ButtonLink } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { useT } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useT();
  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 items-center px-4 py-16">
      <EmptyState
        className="w-full bg-surface"
        icon={<FileQuestion />}
        title={t("ui.notFound")}
        action={
          <ButtonLink href="/" variant="primary">
            {t("ui.goHome")}
          </ButtonLink>
        }
      >
        {t("ui.notFoundBody")}
      </EmptyState>
    </main>
  );
}
