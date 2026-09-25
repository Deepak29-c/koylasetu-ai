"use client";

import { MessageSquareText, Send } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Textarea } from "@/components/ui/Field";
import { useT } from "@/lib/i18n";

/** A short question box that hands the question to the Ask page (?q=). */
export default function QuickAsk() {
  const { t } = useT();
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const tooShort = question.trim().length < 3;

  function submit() {
    if (tooShort) return;
    router.push(`/ask?q=${encodeURIComponent(question.trim())}`);
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader icon={<MessageSquareText />} title={t("dash.quickAskTitle")} subtitle={t("dash.quickAskHelp")} />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex flex-1 flex-col gap-3"
      >
        <Field label={t("home.yourQuestion")} hint={t("home.ctrlEnterHint")}>
          <Textarea
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={t("askPlaceholder")}
          />
        </Field>
        <div className="mt-auto flex justify-end">
          <Button type="submit" variant="primary" disabled={tooShort} icon={<Send size={16} aria-hidden />}>
            {t("askButton")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
