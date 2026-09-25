"use client";

import { Check, ExternalLink, PencilLine, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useImperativeHandle, useRef, useState } from "react";

import ConfirmDialog from "@/components/ConfirmDialog";
import PageImage from "@/components/PageImage";
import Alert from "@/components/ui/Alert";
import Badge from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Field";
import RecordList from "@/components/ui/RecordList";
import { Skeleton } from "@/components/ui/Skeleton";
import StatusBadge from "@/components/ui/StatusBadge";
import { api, type DecidedItem, type Fact, type PageData, type ReviewItem } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { type LabelKey, useT } from "@/lib/i18n";
import { currentPath, sourceHref } from "@/lib/sources";

import { DecisionBadge } from "./DecidedList";
import { fill, useFigureText } from "./figureText";

export type ReviewAction = "ACCEPT" | "EDIT" | "REJECT";

/** What the queue's keyboard shortcuts call on the open figure. */
export type ReviewDetailHandle = {
  accept: () => void;
  startCorrect: () => void;
  startReject: () => void;
};

function SourceLink({ fact, document }: { fact: Pick<Fact, "document_id" | "page_no" | "bbox">; document: string }) {
  const { t } = useT();
  const fx = useFigureText();
  return (
    <Link
      href={sourceHref({ document_id: fact.document_id, page: fact.page_no, bbox: fact.bbox }, currentPath())}
      title={t("review.openSource")}
      className="inline-flex items-start gap-1 font-medium text-brand hover:underline"
    >
      <span>{fx.pageRef(document, fact.page_no)}</span>
      <ExternalLink size={14} aria-hidden className="mt-0.5 shrink-0" />
    </Link>
  );
}

/**
 * One flagged figure: the source page with the value boxed, the extracted record, why it was
 * flagged, the conflicting value from another source, and the decision. With `earlier` the figure
 * was already decided: that decision is shown and changing it needs a comment.
 */
export default function ReviewDetail({
  item,
  earlier,
  onDone,
  ref,
}: {
  item: Pick<ReviewItem, "fact" | "document_title" | "issues" | "related"> &
    Partial<Pick<ReviewItem, "worst_severity">>;
  earlier?: Pick<DecidedItem, "action" | "comment" | "decided_by" | "decided_at">;
  /** `saved` is the figure as the server stored it (for a correction, the new value). */
  onDone: (fact: Fact, action: ReviewAction, saved: Fact) => void;
  ref?: React.Ref<ReviewDetailHandle>;
}) {
  const { t, locale } = useT();
  const fx = useFigureText();
  const f = item.fact;
  const [page, setPage] = useState<PageData | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [mode, setMode] = useState<"EDIT" | null>(null);
  const [value, setValue] = useState(f.value_raw);
  const [comment, setComment] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tried, setTried] = useState(false);
  const valueRef = useRef<HTMLInputElement>(null);
  const commentRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api<PageData>(`/documents/${f.document_id}/pages/${f.page_no}`).then(setPage, (e: unknown) =>
      setPageError(errorText(e)),
    );
  }, [f.document_id, f.page_no]);

  useEffect(() => {
    if (mode === "EDIT") valueRef.current?.focus();
  }, [mode]);

  async function submit(action: ReviewAction) {
    if (busy) return;
    if (earlier && !comment.trim()) {
      setTried(true);
      commentRef.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Fact>(`/review/facts/${f.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          new_value: action === "EDIT" ? value.trim() : undefined,
          comment: comment.trim() || undefined,
        }),
      });
      setRejecting(false);
      onDone(f, action, saved);
    } catch (e) {
      setError(errorText(e, t));
      setBusy(false);
    }
  }

  function saveCorrection() {
    setTried(true);
    if (!value.trim() || !comment.trim()) return;
    submit("EDIT");
  }

  useImperativeHandle(ref, () => ({
    accept: () => {
      if (!busy && !rejecting && mode !== "EDIT") submit("ACCEPT");
    },
    startCorrect: () => {
      if (!busy) setMode("EDIT");
    },
    startReject: () => {
      if (!busy) setRejecting(true);
    },
  }));

  const printedUnit = f.unit ?? "–";
  const commentRequired = mode === "EDIT" || !!earlier;
  const commentMissing = tried && commentRequired && !comment.trim();
  const valueMissing = tried && mode === "EDIT" && !value.trim();

  const header = (
    <Card as="div" className="order-0 lg:col-span-2">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            {item.worst_severity && <StatusBadge kind="severity" value={item.worst_severity} />}
            {item.issues.map((i) => (
              <Badge key={i.id} tone="neutral" className="font-mono" title={fx.ruleLabel(i.rule_code)}>
                {i.rule_code}
              </Badge>
            ))}
          </div>
          <h2 className="mt-2 text-base leading-6 font-semibold text-strong">{f.label || fx.metricLabel(f.metric)}</h2>
          <p className="mt-0.5 text-sm text-muted">
            <span className="text-lg font-semibold text-strong tabular-nums">{fx.printed(f)}</span>
            <span className="mx-2 text-disabled" aria-hidden>
              ·
            </span>
            <SourceLink fact={f} document={item.document_title} />
          </p>
        </div>
      </div>
    </Card>
  );

  const decision = (
    <Card className="order-1 lg:order-last" aria-labelledby={`decision-${f.id}`}>
      <CardHeader
        id={`decision-${f.id}`}
        level={3}
        title={t("review.decision")}
        subtitle={t(earlier ? "reviewChangeNeedsComment" : "review.decisionHint")}
      />
      <div className="space-y-4">
        {earlier && (
          <div className="rounded-panel border border-line bg-surface-subtle p-3 text-sm">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-medium text-strong">{t("reviewEarlier")}:</span>
              <DecisionBadge action={earlier.action} />
              <span className="text-muted">
                {earlier.decided_by} · {formatDateTime(earlier.decided_at, locale)}
              </span>
            </p>
            {earlier.comment && <p className="mt-1.5 text-foreground">“{earlier.comment}”</p>}
          </div>
        )}
        {mode === "EDIT" && (
          <Field
            label={t("correctValue")}
            required
            hint={fx.printed(f) ? `${t("asPrinted")}: ${fx.printed(f)}. ${fill(t("review.correctHint"), { unit: printedUnit })}` : undefined}
            error={valueMissing ? t("review.valueRequired") : undefined}
          >
            <Input ref={valueRef} value={value} onChange={(e) => setValue(e.target.value)} inputMode="decimal" />
          </Field>
        )}
        <Field
          label={t("comment")}
          required={commentRequired}
          hint={commentRequired ? undefined : t("review.commentHintAccept")}
          error={commentMissing ? t(earlier ? "reviewChangeNeedsComment" : "commentRequired") : undefined}
        >
          <Textarea ref={commentRef} value={comment} onChange={(e) => setComment(e.target.value)} rows={2} />
        </Field>
        {error && <Alert tone="danger">{error}</Alert>}
        {mode === "EDIT" ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" loading={busy} icon={<Check size={16} aria-hidden />} onClick={saveCorrection}>
              {t("review.saveCorrection")}
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => {
                setMode(null);
                setValue(f.value_raw);
                setTried(false);
              }}
            >
              {t("cancel")}
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="success"
              size="lg"
              loading={busy}
              icon={<Check size={16} aria-hidden />}
              onClick={() => submit("ACCEPT")}
            >
              {t("accept")}
            </Button>
            <Button
              variant="outline"
              size="lg"
              disabled={busy}
              icon={<PencilLine size={16} aria-hidden />}
              onClick={() => setMode("EDIT")}
            >
              {t("reviewEdit")}
            </Button>
            <Button
              variant="danger-outline"
              size="lg"
              disabled={busy}
              icon={<X size={16} aria-hidden />}
              onClick={() => setRejecting(true)}
            >
              {t("reviewReject")}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );

  const record = (
    <Card className="order-3 lg:order-none">
      <CardHeader level={3} title={t("review.thisFigure")} />
      <RecordList
        columns={2}
        items={[
          { label: t("metric"), value: fx.metricLabel(f.metric) },
          { label: t("asPrinted"), value: <span className="tabular-nums">{fx.printed(f)}</span> },
          { label: t("standard"), value: <span className="tabular-nums">{fx.standard(f)}</span> },
          { label: t("who"), value: fx.who(f) },
          { label: t("category"), value: f.category },
          { label: t("period"), value: fx.periodText(f) },
          { label: t("confidence"), value: <span className="tabular-nums">{Math.round(f.confidence * 100)}%</span> },
          { label: t("ui.sourceOf"), value: <SourceLink fact={f} document={item.document_title} />, wide: true },
        ]}
      />
    </Card>
  );

  const reasons = item.issues.length > 0 && (
    <Alert tone="warning" title={t("why")} className="order-4 lg:order-none">
      <ul className="mt-1 space-y-1.5">
        {item.issues.map((i) => (
          <li key={i.id} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-mono text-xs font-semibold">{i.rule_code}</span>
            <span className="text-xs">({t(`sev.${i.severity}` as LabelKey)})</span>
            <span>{i.message}</span>
          </li>
        ))}
      </ul>
    </Alert>
  );

  const other =
    item.related.length > 0 ? (
      <Card className="order-5 lg:order-none">
        <CardHeader level={3} title={t("review.compareTitle")} subtitle={t("review.compareHelp")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-panel border border-line bg-surface-subtle px-4 py-2">
            <p className="pt-2 text-xs font-semibold text-strong">{t("review.thisFigure")}</p>
            <RecordList
              items={[
                { label: t("asPrinted"), value: <span className="tabular-nums">{fx.printed(f)}</span> },
                { label: t("standard"), value: <span className="tabular-nums">{fx.standard(f)}</span> },
                { label: t("period"), value: fx.periodText(f) },
                { label: t("ui.sourceOf"), value: <SourceLink fact={f} document={item.document_title} /> },
              ]}
            />
          </div>
          {item.related.map((r) => (
            <div key={r.id} className="rounded-panel border border-warning-border bg-surface px-4 py-2">
              <p className="pt-2 text-xs font-semibold text-strong">{t("otherSource")}</p>
              <RecordList
                items={[
                  { label: t("asPrinted"), value: <span className="tabular-nums">{fx.printed(r)}</span> },
                  { label: t("standard"), value: <span className="tabular-nums">{fx.standard(r)}</span> },
                  { label: t("period"), value: fx.periodText(r) },
                  { label: t("ui.sourceOf"), value: <SourceLink fact={r} document={r.document_title} /> },
                ]}
              />
            </div>
          ))}
        </div>
      </Card>
    ) : null;

  const pageAlt = fx.pageRef(item.document_title, f.page_no);
  const image = (
    <div className="order-2 space-y-2 lg:sticky lg:top-4 lg:col-start-1 lg:row-start-2 lg:self-start">
      {pageError ? (
        <Alert tone="danger" title={t("review.pageLoadFailed")}>
          {pageError}
        </Alert>
      ) : page ? (
        <PageImage
          imagePath={page.image_url}
          width={page.width}
          height={page.height}
          highlight={f.bbox}
          alt={pageAlt}
        />
      ) : (
        <Skeleton className="aspect-[3/4] w-full rounded-card" />
      )}
    </div>
  );

  return (
    <div className="flex animate-panel-in flex-col gap-4 lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-start">
      {header}
      {/* Below lg these cards join the column above so the decision comes first; at lg they stack on the right. */}
      <div className="contents lg:col-start-2 lg:row-start-2 lg:flex lg:flex-col lg:gap-4">
        {decision}
        {record}
        {reasons}
        {other}
      </div>
      {image}

      {rejecting && (
        <ConfirmDialog
          danger
          title={t("review.rejectTitle")}
          body={t("review.rejectBody")}
          confirmLabel={t("review.rejectConfirm")}
          busy={busy}
          confirmDisabled={!comment.trim()}
          onConfirm={() => submit("REJECT")}
          onCancel={() => setRejecting(false)}
        >
          <Field
            label={t("review.rejectReason")}
            required
            hint={t(earlier ? "reviewChangeNeedsComment" : "commentRequired")}
          >
            <Textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={3} autoFocus />
          </Field>
          {error && <Alert tone="danger" className="mt-3">{error}</Alert>}
        </ConfirmDialog>
      )}
    </div>
  );
}

export function ReviewDetailSkeleton() {
  const { t } = useT();
  return (
    <div role="status" aria-label={t("loading")} className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <Skeleton className="h-28 rounded-card lg:col-span-2" />
      <Skeleton className="aspect-[3/4] w-full rounded-card" />
      <div className="space-y-4">
        <Skeleton className="h-56 rounded-card" />
        <Skeleton className="h-24 rounded-card" />
        <Skeleton className="h-40 rounded-card" />
      </div>
    </div>
  );
}
