"use client";

import { FileText } from "lucide-react";
import { useState } from "react";

import Badge from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { formatDate, formatNumber } from "@/lib/format";
import { useT, type LabelKey } from "@/lib/i18n";
import { currentPath, sourceHref } from "@/lib/sources";
import { keywordsInclude, type TopicQuestion } from "@/lib/topics";

const PAGE = 20;

type TopicQuestionsProps = {
  questions: TopicQuestion[];
  word?: string;
};

/** A topic's questions, the most typical first, each linked to the PQ document it came from. */
export default function TopicQuestions({ questions, word }: TopicQuestionsProps) {
  const { t, locale } = useT();
  const [limit, setLimit] = useState(PAGE);
  const from = currentPath();
  const shown = questions.slice(0, limit);

  return (
    <div className="space-y-3">
      <ul className="divide-y divide-line">
        {shown.map((q) => {
          const meta = [
            t(`house.${q.house}` as LabelKey),
            t(`qtype.${q.q_type}` as LabelKey),
            q.q_no ? `${t("topics.qPrefix")} ${q.q_no}` : null,
            q.answer_date ? formatDate(q.answer_date, locale) : null,
          ].filter(Boolean);
          return (
            <li key={q.id} className="py-3 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                <p className="min-w-0 flex-1 text-sm font-medium text-strong">
                  {q.subject || q.question_text.slice(0, 100)}
                </p>
                {q.document_id && (
                  <ButtonLink
                    href={sourceHref({ document_id: q.document_id, page: 1 }, from)}
                    variant="link"
                    className="text-xs"
                    icon={<FileText size={14} aria-hidden />}
                  >
                    {t("docs.openDocument")}
                  </ButtonLink>
                )}
              </div>
              <p className="mt-0.5 text-xs text-muted tabular-nums">{meta.join(" · ")}</p>
              <p className="mt-1 line-clamp-2 text-sm text-foreground">{q.question_text}</p>
              {q.keywords.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  <span className="sr-only">{t("keywords")}:</span>
                  {q.keywords.map((k) => (
                    <Badge key={k} tone={word && keywordsInclude([k], word) ? "brand" : "neutral"}>
                      {k}
                    </Badge>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {questions.length > limit && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
          <p className="text-xs text-muted tabular-nums">
            {formatNumber(shown.length, locale)} / {formatNumber(questions.length, locale)} {t("topics.shown")}
          </p>
          <Button variant="outline" size="sm" onClick={() => setLimit((n) => n + PAGE)}>
            {t("topics.showMore")}
          </Button>
        </div>
      )}
    </div>
  );
}
