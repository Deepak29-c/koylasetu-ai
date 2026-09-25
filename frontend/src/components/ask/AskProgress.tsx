"use client";

import JobProgress, { advanceByTime, useElapsed } from "@/components/ui/JobProgress";
import { useT } from "@/lib/i18n";

/** Waiting for an answer. The server sends no step events, so the steps move on with time. */
export default function AskProgress({ startedAt }: { startedAt: number }) {
  const { t } = useT();
  const elapsed = useElapsed(startedAt);
  const steps = [t("ask.stepSearch"), t("ask.stepFigures"), t("ask.stepWrite")];
  return (
    <JobProgress
      title={t("ask.progressTitle")}
      description={t("ask.progressHelp")}
      steps={steps}
      current={advanceByTime(elapsed, steps.length, 4)}
      startedAt={startedAt}
    />
  );
}
