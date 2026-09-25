"use client";

import { TriangleAlert } from "lucide-react";
import { useEffect } from "react";

import { Button, ButtonLink } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { useT } from "@/lib/i18n";

export default function SignedInError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  const { t } = useT();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <EmptyState
      icon={<TriangleAlert />}
      title={t("ui.somethingWrong")}
      action={
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="primary" onClick={() => retry()}>
            {t("retry")}
          </Button>
          <ButtonLink href="/" variant="outline">
            {t("ui.goHome")}
          </ButtonLink>
        </div>
      }
    >
      <p className="break-words">{error.message}</p>
    </EmptyState>
  );
}
