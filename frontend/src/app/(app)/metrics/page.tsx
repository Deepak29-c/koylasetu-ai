"use client";

import { Lock, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useMe } from "@/components/AppShell";
import BenchmarkSection from "@/components/metrics/BenchmarkSection";
import UsageSection from "@/components/metrics/UsageSection";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { getMetrics, type MetricsOut } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

function MetricsSkeleton() {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="space-y-6">
      {[5, 6].map((tiles, i) => (
        <div key={i} className="space-y-4 rounded-card border border-line bg-surface p-5 shadow-card sm:p-6">
          <Skeleton className="h-6 w-48" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: tiles }, (_, j) => (
              <Skeleton key={j} className="h-24 rounded-card" />
            ))}
          </div>
          <Skeleton className="h-32 rounded-panel" />
        </div>
      ))}
    </div>
  );
}

export default function MetricsPage() {
  const me = useMe();
  const { t } = useT();
  const allowed = can(me, "view_metrics");
  const [data, setData] = useState<MetricsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    return getMetrics()
      .then(
        (m) => {
          setData(m);
          setError(null);
        },
        (e) => setError(errorText(e)),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!allowed) return;
    // Fetch on mount; the state updates happen after the request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [allowed, load]);

  if (!allowed)
    return (
      <>
        <PageHeader title={t("nav.metrics")} />
        <EmptyState icon={<Lock />} title={t("noPermission")} />
      </>
    );

  return (
    <>
      <PageHeader
        title={t("nav.metrics")}
        description={t("metrics.description")}
        actions={
          data && (
            <Button variant="secondary" icon={<RefreshCw size={16} aria-hidden />} loading={loading} onClick={load}>
              {t("metrics.refresh")}
            </Button>
          )
        }
      />
      <div className="space-y-6">
        {error && (
          <Alert
            tone="danger"
            title={t("metrics.loadFailed")}
            action={
              <Button variant="danger-outline" size="sm" loading={loading} onClick={load}>
                {t("retry")}
              </Button>
            }
          >
            {error}
          </Alert>
        )}
        {!data && !error && <MetricsSkeleton />}
        {data && (
          <>
            <BenchmarkSection benchmark={data.benchmark} />
            <UsageSection data={data} />
          </>
        )}
      </div>
    </>
  );
}
