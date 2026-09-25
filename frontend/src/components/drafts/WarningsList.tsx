"use client";

import Alert from "@/components/ui/Alert";
import { useT } from "@/lib/i18n";

/** The generator's warnings about a draft, in one alert. Nothing when there are none. */
export default function WarningsList({ warnings }: { warnings?: string[] | null }) {
  const { t } = useT();
  if (!warnings?.length) return null;
  return (
    <Alert tone="warning" title={t("drafts.warnings")}>
      {warnings.length === 1 ? (
        <p>{warnings[0]}</p>
      ) : (
        <ul className="list-disc space-y-1 pl-5">
          {warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}
    </Alert>
  );
}
