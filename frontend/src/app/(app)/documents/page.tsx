"use client";

import { CircleAlert, FileSearch, RefreshCw, UploadCloud } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { useMe } from "@/components/AppShell";
import { FileTypeIcon } from "@/components/docs/files";
import ProgressBar from "@/components/docs/ProgressBar";
import Alert from "@/components/ui/Alert";
import { Button, ButtonLink } from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Select } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { TableSkeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import {
  Pagination,
  SearchInput,
  Table,
  TableFrame,
  TableToolbar,
  TD,
  TH,
  THead,
  TR,
  usePaged,
  useSort,
} from "@/components/ui/Table";
import Tabs from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { api, type DocType, type DocumentRow, type DocumentStatus, type UploadResult } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { failureKey, type LabelKey, useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";
import { sourceHref } from "@/lib/sources";

const DOC_TYPES: DocType[] = ["annual_report", "coal_inventory", "monthly_stats", "pq_answer", "other"];
const POLL_MS = 5000;

/** Status tabs. "PROCESSING" covers documents waiting in the queue as well as those being read. */
type StatusTab = "all" | "PROCESSING" | "PROCESSED" | "NEEDS_REVIEW" | "FAILED";
const TAB_STATUSES: Record<Exclude<StatusTab, "all">, DocumentStatus[]> = {
  PROCESSING: ["UPLOADED", "PROCESSING"],
  PROCESSED: ["PROCESSED"],
  NEEDS_REVIEW: ["NEEDS_REVIEW"],
  FAILED: ["FAILED"],
};

function tabFromParam(v: string | null): StatusTab {
  const s = (v ?? "").toUpperCase();
  if (s === "UPLOADED") return "PROCESSING";
  return s in TAB_STATUSES ? (s as StatusTab) : "all";
}

const isActive = (d: DocumentRow) => d.status === "UPLOADED" || d.status === "PROCESSING";
const canOpen = (d: DocumentRow) =>
  (d.status === "PROCESSED" || d.status === "NEEDS_REVIEW") && !!d.page_count && !d.file_missing;
// The API refuses a retry only while a document is being read; the list offers it for the
// states where re-running is the expected next step.
const canRetry = (d: DocumentRow) => d.status === "FAILED" || d.status === "UPLOADED";

type SortKey = "title" | "type" | "fy" | "status" | "created";

export default function DocumentsPage() {
  // useSearchParams needs a Suspense boundary for Next's static render pass.
  return (
    <Suspense fallback={<TableSkeleton />}>
      <DocumentsList />
    </Suspense>
  );
}

function DocumentsList() {
  const me = useMe();
  const { t, locale } = useT();
  const toast = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const statusParam = params.get("status");
  const tab = tabFromParam(statusParam);

  const [docs, setDocs] = useState<DocumentRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [type, setType] = useState<DocType | "">("");
  const [retrying, setRetrying] = useState<Set<string>>(new Set());
  const allowed = can(me, "view_processing");
  const mayUpload = can(me, "upload_documents");

  const load = useCallback(
    () =>
      api<DocumentRow[]>("/documents").then(
        (rows) => {
          setDocs(rows);
          setError(null);
        },
        (e: unknown) => setError(errorText(e)),
      ),
    [],
  );

  useEffect(() => {
    if (allowed) load();
  }, [allowed, load]);

  // Poll only while something is still being read and the tab is in view.
  const polling = !!docs?.some(isActive);
  useEffect(() => {
    if (!allowed || !polling) return;
    let timer: number | undefined;
    const start = () => {
      if (timer === undefined && document.visibilityState === "visible") timer = window.setInterval(load, POLL_MS);
    };
    const stop = () => {
      if (timer !== undefined) window.clearInterval(timer);
      timer = undefined;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        load();
        start();
      } else stop();
    };
    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [allowed, polling, load]);

  // Search and type narrow the list first; the status tabs count within that.
  const narrowed = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (docs ?? []).filter(
      (d) =>
        (!type || d.doc_type === type) &&
        (!q || d.title.toLowerCase().includes(q) || d.original_filename.toLowerCase().includes(q)),
    );
  }, [docs, query, type]);

  const counts = useMemo(() => {
    const c = { all: narrowed.length, PROCESSING: 0, PROCESSED: 0, NEEDS_REVIEW: 0, FAILED: 0 };
    for (const d of narrowed) {
      for (const [k, statuses] of Object.entries(TAB_STATUSES)) {
        if (statuses.includes(d.status)) c[k as keyof typeof TAB_STATUSES] += 1;
      }
    }
    return c;
  }, [narrowed]);

  const filtered = useMemo(
    () => (tab === "all" ? narrowed : narrowed.filter((d) => TAB_STATUSES[tab].includes(d.status))),
    [narrowed, tab],
  );

  const { sorted, header } = useSort<DocumentRow, SortKey>(
    filtered,
    (d, key) =>
      key === "title"
        ? d.title.toLowerCase()
        : key === "type"
          ? t(`doc.${d.doc_type}` as LabelKey)
          : key === "fy"
            ? d.fy
            : key === "status"
              ? t(`status.${d.status}` as LabelKey)
              : d.created_at,
    { key: "created", dir: "desc" },
  );
  const paged = usePaged(sorted, 25);

  if (!allowed) {
    return (
      <>
        <PageHeader title={t("documents")} />
        <Alert tone="warning">{t("noPermission")}</Alert>
      </>
    );
  }

  const from = statusParam ? `${pathname}?status=${encodeURIComponent(statusParam)}` : pathname;
  const filtersOn = tab !== "all" || !!type || !!query.trim();

  function setTab(next: StatusTab) {
    const q = new URLSearchParams(params.toString());
    if (next === "all") q.delete("status");
    else q.set("status", next);
    const s = q.toString();
    router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
    paged.setPage(1);
  }

  function clearFilters() {
    setQuery("");
    setType("");
    setTab("all");
  }

  async function retry(d: DocumentRow) {
    if (retrying.has(d.id)) return;
    setRetrying((s) => new Set(s).add(d.id));
    try {
      const res = await api<UploadResult>(`/documents/${d.id}/retry`, { method: "POST" });
      toast(
        res.queued
          ? { tone: "success", title: t("docs.retryQueued"), body: d.title }
          : { tone: "info", title: t("notQueued"), body: d.title },
      );
      await load();
    } catch (e) {
      toast({ tone: "danger", title: t("docs.retryFailed"), body: errorText(e, t) });
    } finally {
      setRetrying((s) => {
        const n = new Set(s);
        n.delete(d.id);
        return n;
      });
    }
  }

  const uploadAction = mayUpload ? (
    <ButtonLink href="/upload" variant="primary" icon={<UploadCloud size={16} aria-hidden />}>
      {t("uploadTitle")}
    </ButtonLink>
  ) : null;

  const tabs = (
    <Tabs<StatusTab>
      label={t("docs.statusFilter")}
      value={tab}
      onChange={setTab}
      items={[
        { value: "all", label: t("ui.all"), count: counts.all },
        { value: "PROCESSING", label: t("status.PROCESSING"), count: counts.PROCESSING },
        { value: "PROCESSED", label: t("docs.tabProcessed"), count: counts.PROCESSED },
        { value: "NEEDS_REVIEW", label: t("status.NEEDS_REVIEW"), count: counts.NEEDS_REVIEW },
        { value: "FAILED", label: t("status.FAILED"), count: counts.FAILED },
      ]}
    />
  );

  const titleCell = (d: DocumentRow) => (
    <div className="min-w-0">
      {canOpen(d) ? (
        <Link
          href={sourceHref({ document_id: d.id, page: 1 }, from)}
          className="font-medium text-brand hover:underline"
        >
          {d.title}
        </Link>
      ) : (
        <span className="font-medium text-strong">{d.title}</span>
      )}
      {d.failure_reason && (
        <p className="mt-0.5 flex items-start gap-1 text-xs text-danger-fg">
          <CircleAlert size={13} aria-hidden className="mt-px shrink-0" />
          <span className="break-words">
            <span className="sr-only">{t("ui.error")}: </span>
            {/* A translated reason, never the raw exception or a server path. */}
            {(() => {
              const key = failureKey(d.failure_reason);
              return key ? t(key) : d.failure_message;
            })()}
          </span>
        </p>
      )}
    </div>
  );

  const pagesCell = (d: DocumentRow) => {
    if (!d.page_count) return <span className="text-subtle">–</span>;
    const text = `${d.pages_done} / ${d.page_count}`;
    if (!isActive(d)) return <span className="tabular-nums">{d.page_count}</span>;
    return (
      <div className="flex min-w-24 items-center gap-2">
        <ProgressBar
          size="sm"
          value={d.pages_done / d.page_count}
          label={`${t("docs.pagesRead")}: ${d.title}`}
          valueText={text}
          className="w-16"
        />
        <span className="text-xs text-muted tabular-nums">{text}</span>
      </div>
    );
  };

  const retryButton = (d: DocumentRow) =>
    mayUpload && canRetry(d) ? (
      <Button
        variant="outline"
        size="sm"
        loading={retrying.has(d.id)}
        onClick={() => retry(d)}
        icon={<RefreshCw size={14} aria-hidden />}
        aria-label={`${t("retry")}: ${d.title}`}
      >
        {t("retry")}
      </Button>
    ) : null;

  return (
    <div className="space-y-6">
      <PageHeader title={t("documents")} description={t("docs.listDescription")} actions={uploadAction} />

      {error && (
        <Alert
          tone="danger"
          title={t("docs.loadFailed")}
          action={
            <Button variant="outline" size="sm" onClick={() => load()}>
              {t("dash.tryAgain")}
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {docs === null && !error && (
        <TableFrame>
          <TableSkeleton columns={6} />
        </TableFrame>
      )}

      {docs !== null && docs.length === 0 && (
        <EmptyState icon={<UploadCloud />} title={t("noDocuments")} action={uploadAction}>
          {t("docs.emptyHelp")}
        </EmptyState>
      )}

      {docs !== null && docs.length > 0 && (
        <TableFrame>
          <TableToolbar
            count={filtered.length}
            total={docs.length}
            filters={
              polling ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-muted" aria-live="polite">
                  <RefreshCw size={12} aria-hidden className="text-brand" />
                  {t("docs.autoRefresh")}
                </span>
              ) : undefined
            }
            search={
              <SearchInput
                value={query}
                onChange={(v) => {
                  setQuery(v);
                  paged.setPage(1);
                }}
                placeholder={t("docs.searchTitle")}
              />
            }
            actions={
              <div className="w-full sm:w-48">
                <Select
                  aria-label={t("docType")}
                  value={type}
                  onChange={(e) => {
                    setType(e.target.value as DocType | "");
                    paged.setPage(1);
                  }}
                  className="h-9 rounded-full"
                >
                  <option value="">{t("docs.allTypes")}</option>
                  {DOC_TYPES.map((d) => (
                    <option key={d} value={d}>
                      {t(`doc.${d}` as LabelKey)}
                    </option>
                  ))}
                </Select>
              </div>
            }
          />
          <div className="px-5 pb-3">{tabs}</div>

          {filtered.length === 0 ? (
            <div className="px-5 pb-5">
              <EmptyState
                compact
                icon={<FileSearch />}
                title={t("docs.noMatch")}
                action={
                  filtersOn ? (
                    <Button variant="outline" size="sm" onClick={clearFilters}>
                      {t("ui.clearFilters")}
                    </Button>
                  ) : undefined
                }
              >
                {t("docs.noMatchHelp")}
              </EmptyState>
            </div>
          ) : (
            <>
              <div className="hidden sm:block">
                <Table caption={t("docs.caption")} maxHeight="none">
                  <THead>
                    <TH sort={header("title")}>{t("title")}</TH>
                    <TH sort={header("type")}>{t("type")}</TH>
                    <TH sort={header("fy")}>{t("fyShort")}</TH>
                    <TH sort={header("status")}>{t("status")}</TH>
                    <TH>{t("pages")}</TH>
                    <TH sort={header("created")}>{t("uploadedOn")}</TH>
                    <TH align="right">
                      <span className="sr-only">{t("actions")}</span>
                    </TH>
                  </THead>
                  <tbody>
                    {paged.rows.map((d) => (
                      <TR key={d.id}>
                        <TD className="max-w-md">
                          <div className="flex items-start gap-2.5">
                            <FileTypeIcon
                              name={d.original_filename}
                              size={18}
                              className="mt-0.5 shrink-0 text-subtle"
                            />
                            {titleCell(d)}
                          </div>
                        </TD>
                        <TD className="whitespace-nowrap">{t(`doc.${d.doc_type}` as LabelKey)}</TD>
                        <TD className="whitespace-nowrap">{d.fy ?? <span className="text-subtle">–</span>}</TD>
                        <TD>
                          <StatusBadge kind="document" value={d.status} />
                        </TD>
                        <TD>{pagesCell(d)}</TD>
                        <TD className="whitespace-nowrap text-muted">{formatDateTime(d.created_at, locale)}</TD>
                        <TD align="right">{retryButton(d)}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </div>

              <ul className="divide-y divide-line border-t border-line sm:hidden">
                {paged.rows.map((d) => (
                  <li key={d.id} className="space-y-2 px-5 py-4">
                    <div className="flex items-start justify-between gap-3">
                      {titleCell(d)}
                      <StatusBadge kind="document" value={d.status} />
                    </div>
                    <p className="text-xs text-muted">
                      {t(`doc.${d.doc_type}` as LabelKey)}
                      {d.fy ? ` · ${d.fy}` : ""} · {formatDateTime(d.created_at, locale)}
                    </p>
                    {(!!d.page_count || (mayUpload && canRetry(d))) && (
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 text-xs">
                          {d.page_count ? (
                            <>
                              <span className="text-muted">{t("pages")}:</span>
                              {pagesCell(d)}
                            </>
                          ) : null}
                        </div>
                        {retryButton(d)}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
              <Pagination
                page={paged.page}
                pageCount={paged.pageCount}
                onPage={paged.setPage}
                from={paged.from}
                to={paged.to}
                total={paged.total}
              />
            </>
          )}
        </TableFrame>
      )}
    </div>
  );
}
