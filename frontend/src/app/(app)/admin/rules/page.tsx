"use client";

import { ClipboardCheck, ListChecks, Lock } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { labelOr, withUnit } from "@/components/admin/labels";
import { useMe } from "@/components/AppShell";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import PageHeader from "@/components/ui/PageHeader";
import { MonoId } from "@/components/ui/RecordList";
import { Skeleton, TableSkeleton } from "@/components/ui/Skeleton";
import Stat from "@/components/ui/Stat";
import StatusBadge from "@/components/ui/StatusBadge";
import { TD, TH, THead, TR, Table, TableFrame, TableToolbar } from "@/components/ui/Table";
import { type AdminRule, listAdminRules } from "@/lib/api-admin";
import { errorText } from "@/lib/errors";
import { formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

export default function AdminRulesPage() {
  const me = useMe();
  const { t, locale } = useT();
  const allowed = can(me, "manage_admin");
  const [rules, setRules] = useState<AdminRule[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    return listAdminRules()
      .then(
        (r) => {
          setRules(r);
          setError(null);
        },
        (e: unknown) => setError(e),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!allowed) return;
    // Fetch on mount; the state updates happen after the request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
  }, [allowed, load]);

  const header = (
    <PageHeader
      title={t("adminRules.title")}
      description={t("adminRules.description")}
      breadcrumbs={[{ label: t("nav.admin") }]}
    />
  );

  if (!allowed)
    return (
      <>
        {header}
        <EmptyState icon={<Lock />} title={t("noPermission")} />
      </>
    );

  const openTotal = rules?.reduce((sum, r) => sum + r.open_issues, 0) ?? 0;

  return (
    <>
      {header}
      <div className="space-y-6">
        {error !== null && (
          <Alert
            tone="danger"
            title={t("adminRules.loadFailed")}
            action={
              <Button variant="danger-outline" size="sm" loading={loading} onClick={load}>
                {t("retry")}
              </Button>
            }
          >
            {errorText(error, t)}
          </Alert>
        )}

        {!rules && error === null && (
          <div role="status" aria-label={t("loading")} className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <Skeleton className="h-20 rounded-card" />
              <Skeleton className="h-20 rounded-card" />
            </div>
            <TableSkeleton rows={8} columns={5} />
          </div>
        )}

        {rules && rules.length === 0 && <EmptyState icon={<ListChecks />} title={t("adminRules.empty")} />}

        {rules && rules.length > 0 && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <Stat
                label={t("adminRules.rulesCount")}
                value={formatNumber(rules.length, locale)}
                icon={<ListChecks />}
              />
              <Stat
                label={t("adminRules.openTotal")}
                value={formatNumber(openTotal, locale)}
                icon={<ClipboardCheck />}
                tone={openTotal ? "warning" : "success"}
                href={can(me, "review_facts") ? "/review" : undefined}
                note={can(me, "review_facts") ? t("adminRules.openReview") : undefined}
              />
            </div>

            <Alert tone="info">{t("adminRules.readOnly")}</Alert>

            <TableFrame>
              <TableToolbar title={t("adminRules.title")} count={rules.length} />
              <Table caption={t("adminRules.title")}>
                <THead>
                  <TH>{t("adminRules.colCode")}</TH>
                  <TH>{t("adminRules.colRule")}</TH>
                  <TH>{t("adminRules.colSeverity")}</TH>
                  <TH>{t("adminRules.colThresholds")}</TH>
                  <TH align="right">{t("adminRules.colOpen")}</TH>
                </THead>
                <tbody>
                  {rules.map((r) => (
                    <RuleRow key={r.code} rule={r} canReview={can(me, "review_facts")} />
                  ))}
                </tbody>
              </Table>
            </TableFrame>
          </>
        )}
      </div>
    </>
  );
}

function RuleRow({ rule, canReview }: { rule: AdminRule; canReview: boolean }) {
  const { t, locale } = useT();
  const count = formatNumber(rule.open_issues, locale);
  return (
    <TR>
      <TD className="align-top">
        <MonoId>{rule.code}</MonoId>
      </TD>
      <TD className="min-w-72 align-top">
        <p className="font-medium text-strong">{labelOr(t, `adminRules.name.${rule.code}`, rule.name)}</p>
        <p className="mt-0.5 max-w-xl text-xs text-muted">{labelOr(t, `adminRules.checks.${rule.code}`, rule.checks)}</p>
        {rule.uses_other_documents && (
          <Badge tone="info" className="mt-1.5">
            {t("adminRules.otherDocuments")}
          </Badge>
        )}
      </TD>
      <TD className="align-top">
        <div className="flex flex-wrap gap-1.5">
          {rule.severities.map((s) => (
            <StatusBadge key={s} kind="severity" value={s} />
          ))}
        </div>
      </TD>
      <TD className="min-w-56 align-top">
        {rule.thresholds.length === 0 ? (
          <span className="text-xs text-subtle">{t("adminRules.noThreshold")}</span>
        ) : (
          <ul className="space-y-1 text-xs">
            {rule.thresholds.map((th) => (
              <li key={th.key}>
                <span className="text-muted">{labelOr(t, `adminRules.threshold.${th.key}`, th.key)}: </span>
                <span className="font-medium text-strong tabular-nums">{withUnit(th.value, th.unit, locale)}</span>
              </li>
            ))}
          </ul>
        )}
      </TD>
      <TD align="right" className="align-top">
        {canReview && rule.open_issues > 0 ? (
          <Link
            href="/review"
            className="font-semibold text-brand hover:underline"
            aria-label={`${count} ${t("adminRules.colOpen")} (${rule.code}): ${t("adminRules.openReview")}`}
          >
            {count}
          </Link>
        ) : (
          <span className="text-strong">{count}</span>
        )}
      </TD>
    </TR>
  );
}
