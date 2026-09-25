"use client";

import { FileUp } from "lucide-react";
import { useRef, useState } from "react";

import ConfirmDialog from "@/components/ConfirmDialog";
import Alert from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { importQuestionText, type PqQuestionTextOut } from "@/lib/api-pqform";
import { errorText } from "@/lib/errors";
import { useT } from "@/lib/i18n";

const ACCEPT =
  ".pdf,.docx,.txt,application/pdf,text/plain," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

/** The "Import from file" button of the question box. */
export function QuestionImportButton({
  busy,
  onChoose,
}: {
  busy: boolean;
  onChoose: (file: File) => void;
}) {
  const { t } = useT();
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          // Cleared so the same file can be chosen again after an edit.
          e.target.value = "";
          if (file) onChoose(file);
        }}
      />
      <Button
        variant="outline"
        size="sm"
        loading={busy}
        icon={<FileUp size={14} aria-hidden />}
        title={t("pqform.importHint")}
        onClick={() => input.current?.click()}
      >
        {t("pqform.import")}
      </Button>
    </>
  );
}

/**
 * Reading a question out of a PDF, Word or text file into the question box. Text already in
 * the box is only replaced after the person confirms.
 */
export function useQuestionImport(current: string, fill: (text: string) => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<PqQuestionTextOut | null>(null);
  const [filled, setFilled] = useState<PqQuestionTextOut | null>(null);

  function apply(read: PqQuestionTextOut) {
    fill(read.text);
    setFilled(read);
    setPending(null);
  }

  async function choose(file: File) {
    setBusy(true);
    setError(null);
    setFilled(null);
    try {
      const read = await importQuestionText(file);
      if (current.trim()) setPending(read);
      else apply(read);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return {
    busy,
    choose,
    error,
    pending,
    filled,
    apply,
    cancel: () => setPending(null),
    dismiss: () => {
      setError(null);
      setFilled(null);
    },
  };
}

export function QuestionImportNotices({ state }: { state: ReturnType<typeof useQuestionImport> }) {
  const { t } = useT();
  return (
    <>
      {state.error !== null && (
        <Alert tone="danger" title={t("pqform.importFailed")} onDismiss={state.dismiss} className="mb-4">
          {errorText(state.error, t)}
        </Alert>
      )}
      {state.filled && (
        <Alert tone={state.filled.truncated ? "warning" : "info"} onDismiss={state.dismiss} className="mb-4">
          {t("pqform.imported").replace("{file}", state.filled.filename)}
          {state.filled.truncated && <> {t("pqform.importTruncated")}</>}
        </Alert>
      )}
      {state.pending && (
        <ConfirmDialog
          title={t("pqform.replaceTitle")}
          body={t("pqform.replaceBody").replace("{file}", state.pending.filename)}
          confirmLabel={t("pqform.replace")}
          onConfirm={() => state.pending && state.apply(state.pending)}
          onCancel={state.cancel}
        />
      )}
    </>
  );
}
