"use client";

import { type ChipSource, TextWithCitations } from "@/components/Citation";
import type { AskResult } from "@/lib/api";
import { useT } from "@/lib/i18n";

function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Answer text with source markers as chips. Numbers that are not in the sources are marked
 * in red and underlined, with a spoken note, so the warning never rests on colour alone.
 */
export default function AnswerText({
  result,
  sources,
  from,
}: {
  result: AskResult;
  sources: Map<string, ChipSource>;
  from?: string;
}) {
  const { t } = useT();
  const unmatched = result.unmatched_numbers.filter(Boolean);
  const redRe = unmatched.length
    ? new RegExp(`(?<![\\d.,])(${unmatched.map(escapeRegex).join("|")})(?![\\d])`, "g")
    : null;

  return (
    <p className="text-[15px] leading-7 whitespace-pre-wrap text-foreground">
      <TextWithCitations
        text={result.answer}
        sources={sources}
        from={from}
        renderText={(piece, key) =>
          redRe ? (
            <span key={key}>
              {piece.split(redRe).map((bit, j) =>
                unmatched.includes(bit) ? (
                  <mark
                    key={j}
                    className="rounded-sm bg-danger-bg px-0.5 font-semibold text-danger-fg underline decoration-danger decoration-2 underline-offset-2"
                  >
                    {bit}
                    <span className="sr-only"> ({t("unmatched")})</span>
                  </mark>
                ) : (
                  bit
                ),
              )}
            </span>
          ) : (
            <span key={key}>{piece}</span>
          )
        }
      />
    </p>
  );
}
