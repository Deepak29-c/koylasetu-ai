"use client";

import { FileQuestion, MessageSquareText, Sparkles } from "lucide-react";
import { useRef, useState } from "react";

import { useMe } from "@/components/AppShell";
import DraftProgress from "@/components/drafts/DraftProgress";
import PartsPreview from "@/components/drafts/PartsPreview";
import PqDraftView from "@/components/drafts/PqDraftView";
import { QuestionImportButton, QuestionImportNotices, useQuestionImport } from "@/components/drafts/QuestionImport";
import { useDraftRequest } from "@/components/drafts/useDraftRequest";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import PageHeader from "@/components/ui/PageHeader";
import { draftPqReply, type PqDraftIn, type PqDraftOut } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { can } from "@/lib/permissions";

const EMPTY: PqDraftIn = {
  house: "LS",
  q_type: "unstarred",
  q_no: "",
  answer_date: "",
  mp_name: "",
  subject: "",
  question_text: "",
  due_date: "",
};

const MIN_QUESTION = 10;

export default function NewPqReplyPage() {
  const me = useMe();
  const { t } = useT();
  const [form, setForm] = useState<PqDraftIn>(EMPTY);
  const [questionError, setQuestionError] = useState<string | null>(null);
  const job = useDraftRequest<PqDraftOut>();
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const questionImport = useQuestionImport(form.question_text, (text) => set("question_text", text));

  const header = (
    <PageHeader
      title={t("newPqReply")}
      description={t("pqHelp")}
      breadcrumbs={[{ label: t("reports"), href: "/reports" }]}
    />
  );

  if (!can(me, "edit_reports")) {
    return (
      <div>
        {header}
        <Alert tone="warning">{t("noPermission")}</Alert>
      </div>
    );
  }

  function set<K extends keyof PqDraftIn>(key: K, value: PqDraftIn[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    if (key === "question_text") setQuestionError(null);
    job.inputChanged();
  }

  function submit() {
    if (form.question_text.trim().length < MIN_QUESTION) {
      setQuestionError(t("drafts.questionRequired"));
      questionRef.current?.focus();
      return;
    }
    void job.run((key) =>
      draftPqReply(
        {
          ...form,
          q_no: form.q_no || null,
          answer_date: form.answer_date || null,
          mp_name: form.mp_name || null,
          subject: form.subject || null,
          due_date: form.due_date || null,
        },
        key,
      ),
    );
  }

  return (
    <div className="space-y-6">
      {header}

      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <fieldset disabled={job.busy} className="grid min-w-0 gap-6 xl:grid-cols-2">
          <legend className="sr-only">{t("pqTitle")}</legend>
          <Card>
            <CardHeader
              title={t("drafts.questionDetails")}
              subtitle={t("drafts.questionDetailsHelp")}
              icon={<FileQuestion />}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("house")}>
                <Select value={form.house} onChange={(e) => set("house", e.target.value as PqDraftIn["house"])}>
                  <option value="LS">{t("house.LS")}</option>
                  <option value="RS">{t("house.RS")}</option>
                </Select>
              </Field>
              <Field label={t("questionType")}>
                <Select value={form.q_type} onChange={(e) => set("q_type", e.target.value as PqDraftIn["q_type"])}>
                  <option value="unstarred">{t("qtype.unstarred")}</option>
                  <option value="starred">{t("qtype.starred")}</option>
                </Select>
              </Field>
              <Field label={t("questionNo")} optional>
                <Input
                  value={form.q_no ?? ""}
                  maxLength={16}
                  inputMode="numeric"
                  className="tabular-nums"
                  onChange={(e) => set("q_no", e.target.value)}
                />
              </Field>
              <Field label={t("answerDate")} optional>
                <Input
                  type="date"
                  value={form.answer_date ?? ""}
                  onChange={(e) => set("answer_date", e.target.value)}
                />
              </Field>
              <Field label={t("pqform.dueDate")} hint={t("pqform.dueDateHint")} optional>
                <Input type="date" value={form.due_date ?? ""} onChange={(e) => set("due_date", e.target.value)} />
              </Field>
              <Field label={t("mpName")} optional>
                <Input value={form.mp_name ?? ""} maxLength={300} onChange={(e) => set("mp_name", e.target.value)} />
              </Field>
              <Field label={t("subject")} optional>
                <Input value={form.subject ?? ""} maxLength={500} onChange={(e) => set("subject", e.target.value)} />
              </Field>
            </div>
          </Card>

          <Card>
            <CardHeader
              title={t("questionText")}
              icon={<MessageSquareText />}
              actions={<QuestionImportButton busy={questionImport.busy} onChoose={(f) => void questionImport.choose(f)} />}
            />
            <QuestionImportNotices state={questionImport} />
            <Field
              label={t("questionText")}
              hideLabel
              required
              hint={t("drafts.questionTextHelp")}
              error={questionError}
            >
              <Textarea
                ref={questionRef}
                rows={10}
                maxLength={20000}
                value={form.question_text}
                placeholder={t("questionTextPlaceholder")}
                onChange={(e) => set("question_text", e.target.value)}
                className="min-h-56"
              />
            </Field>
            <PartsPreview text={form.question_text} />
          </Card>

          <div className="flex flex-wrap items-center gap-3 xl:col-span-2">
            <Button type="submit" variant="primary" size="lg" loading={job.busy} icon={<Sparkles size={16} aria-hidden />}>
              {t("generateDraft")}
            </Button>
            {job.busy && <span className="text-xs text-muted">{t("drafts.formLocked")}</span>}
          </div>
        </fieldset>
      </form>

      {job.busy && job.startedAt !== null && (
        <DraftProgress
          startedAt={job.startedAt}
          secondsPerStep={30}
          detail={t("generating")}
          steps={[
            t("drafts.step.splitParts"),
            t("drafts.step.findSources"),
            t("drafts.step.writeAnswers"),
            t("drafts.step.checkFigures"),
            t("drafts.step.saveDraft"),
          ]}
        />
      )}

      {job.error && (
        <Alert
          tone="danger"
          title={t("drafts.failed")}
          action={
            <Button variant="outline" size="sm" onClick={submit}>
              {t("retry")}
            </Button>
          }
        >
          {job.error}
        </Alert>
      )}

      {job.result && <PqDraftView draft={job.result} />}
    </div>
  );
}
