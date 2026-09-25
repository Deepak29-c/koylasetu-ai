"use client";

import JobProgress, { advanceByTime, useElapsed } from "@/components/ui/JobProgress";
import { useT } from "@/lib/i18n";

/**
 * Progress while a draft is generated. The request has no step events, so the current
 * step moves on with time and stays on the last step until the server answers.
 */
export default function DraftProgress({
  startedAt,
  steps,
  secondsPerStep,
  detail,
}: {
  startedAt: number;
  steps: string[];
  secondsPerStep: number;
  /** What this generator is doing, in one sentence. */
  detail?: string;
}) {
  const { t } = useT();
  const elapsed = useElapsed(startedAt);
  return (
    <JobProgress
      title={t("drafts.generatingTitle")}
      description={
        <>
          {detail && <span className="block">{detail}</span>}
          <span className="mt-1 block font-medium text-foreground">{t("drafts.leaveSafe")}</span>
        </>
      }
      steps={steps}
      current={advanceByTime(elapsed, steps.length, secondsPerStep)}
      startedAt={startedAt}
    />
  );
}
