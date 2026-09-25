"use client";

import { ArrowUpRight, CircleCheck, FileText, History, MessageSquareText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { Skeleton } from "@/components/ui/Skeleton";
import Spinner from "@/components/ui/Spinner";
import { SIMILAR_MAX_TEXT, SIMILAR_MIN_TEXT, type SimilarPq, similarPqs } from "@/lib/api-similar";
import { cn } from "@/lib/cn";
import { errorText } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { currentPath, sourceHref } from "@/lib/sources";

const DEBOUNCE_MS = 600;

type Props = {
  /** The question being answered; the panel searches again as it changes. */
  text: string;
  /** A report to leave out of the results (the one on screen). */
  exclude?: string | null;
  limit?: number;
  /** Open results in a new tab, so unsaved input on this page is not lost. */
  newTab?: boolean;
  className?: string;
};

type Found = {
  items: SimilarPq[];
  /** The text these results are for; null until the first search has answered. */
  searched: string | null;
  loading: boolean;
  error: unknown;
};

const NOTHING: Found = { items: [], searched: null, loading: false, error: null };

function searchText(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, SIMILAR_MAX_TEXT);
}

/** Similar past Parliament questions: approved replies and uploaded PQ answers. */
export default function SimilarQuestions({ text, exclude = null, limit = 5, newTab = false, className }: Props) {
  const { t } = useT();
  const query = searchText(text);
  const active = query.length >= SIMILAR_MIN_TEXT;
  const [found, setFound] = useState<Found>(NOTHING);
  const [attempt, setAttempt] = useState(0);
  const latest = useRef(0);
  const now = useRef(false);

  useEffect(() => {
    // Every change makes older requests stale: their answers are dropped when they arrive.
    const mine = ++latest.current;
    if (!active) return;
    const delay = now.current ? 0 : DEBOUNCE_MS;
    now.current = false;
    const timer = setTimeout(() => {
      setFound((f) => ({ ...f, loading: true, error: null }));
      similarPqs(query, { limit, exclude }).then(
        (items) => {
          if (latest.current === mine) setFound({ items, searched: query, loading: false, error: null });
        },
        (error: unknown) => {
          if (latest.current === mine) setFound((f) => ({ ...f, loading: false, error }));
        },
      );
    }, delay);
    return () => clearTimeout(timer);
  }, [query, active, limit, exclude, attempt]);

  function retry() {
    now.current = true;
    setAttempt((n) => n + 1);
  }

  const refreshing = active && found.loading && found.searched !== null;

  let body: React.ReactNode;
  if (!active) {
    body = (
      <EmptyState compact icon={<MessageSquareText />} title={t("similar.startTyping")}>
        {t("similar.startTypingHelp")}
      </EmptyState>
    );
  } else if (found.error && !found.loading) {
    body = (
      <Alert
        tone="danger"
        title={t("similar.failed")}
        action={
          <Button variant="outline" size="sm" onClick={retry}>
            {t("retry")}
          </Button>
        }
      >
        {errorText(found.error, t)}
      </Alert>
    );
  } else if (found.searched === null) {
    body = <ListSkeleton rows={Math.min(limit, 3)} />;
  } else if (found.items.length === 0) {
    body = (
      <EmptyState compact title={t("similar.none")}>
        {t("similar.noneHelp")}
      </EmptyState>
    );
  } else {
    body = (
      <ul aria-label={t("similar.title")} className={cn("space-y-3", refreshing && "opacity-70")}>
        {found.items.map((item) => (
          <SimilarItem key={item.report_id ?? item.chunk_id ?? item.title} item={item} newTab={newTab} />
        ))}
      </ul>
    );
  }

  return (
    <Card className={className} aria-busy={active && found.loading}>
      <CardHeader
        icon={<History />}
        title={t("similar.title")}
        subtitle={t("similar.help")}
        actions={refreshing ? <Spinner className="text-muted" /> : undefined}
      />
      <p role="status" className="sr-only">
        {active && found.loading
          ? t("similar.searching")
          : active && found.searched !== null && !found.error
            ? `${found.items.length} ${t("similar.foundCount")}`
            : ""}
      </p>
      {body}
    </Card>
  );
}

function ListSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="space-y-2 rounded-panel border border-line p-4">
          <Skeleton className="h-5 w-32 rounded-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      ))}
    </div>
  );
}

function SimilarItem({ item, newTab }: { item: SimilarPq; newTab: boolean }) {
  const { t, locale } = useT();
  const approved = item.kind === "approved_reply";
  const meta = [
    item.house ? t(`house.${item.house}` as LabelKey) : null,
    item.q_type ? t(`qtype.${item.q_type}` as LabelKey) : null,
    item.q_no ? `${t("similar.qNo")} ${item.q_no}` : null,
    item.answer_date ? formatDate(item.answer_date, locale) : null,
  ].filter(Boolean);

  let href: string | null = null;
  let label = "";
  if (approved && item.report_id) {
    href = `/reports/${item.report_id}`;
    label = t("similar.openReply");
  } else if (item.document_id && item.page !== null) {
    href = sourceHref({ document_id: item.document_id, page: item.page, chunk_id: item.chunk_id }, currentPath());
    label = `${t("similar.openPage")} (${t("page")} ${item.page})`;
  }

  return (
    <li className="rounded-panel border border-line bg-surface-subtle p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <Badge
          tone={approved ? "success" : "info"}
          icon={approved ? <CircleCheck size={12} aria-hidden /> : <FileText size={12} aria-hidden />}
        >
          {t(`similar.kind.${item.kind}` as LabelKey)}
        </Badge>
        {meta.length > 0 && <span className="text-xs text-muted tabular-nums">{meta.join(" · ")}</span>}
      </div>
      <h3 className="mt-2 text-sm leading-5 font-semibold break-words text-strong">{item.title}</h3>
      {item.document_title && item.document_title !== item.title && (
        <p className="mt-0.5 text-xs break-words text-muted">{item.document_title}</p>
      )}
      {item.snippet && <p className="mt-1.5 text-sm leading-6 break-words text-foreground">{item.snippet}</p>}
      {item.answer && (
        <p className="mt-1.5 text-xs leading-5 break-words text-muted">
          <span className="font-medium text-foreground">{t("drafts.answer")}:</span> {item.answer}
        </p>
      )}
      {href && (
        <ButtonLink
          href={href}
          variant="outline"
          size="sm"
          className="mt-3"
          target={newTab ? "_blank" : undefined}
          rel={newTab ? "noopener" : undefined}
        >
          {label}
          <ArrowUpRight size={14} aria-hidden />
          {newTab && <span className="sr-only">({t("similar.newTab")})</span>}
        </ButtonLink>
      )}
    </li>
  );
}
