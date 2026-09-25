"use client";

import { CircleCheck, TriangleAlert } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/Button";
import Dialog from "@/components/ui/Dialog";
import { useT } from "@/lib/i18n";

type Props = {
  title: string;
  body: string;
  confirmLabel: string;
  /** Red confirm button for anything the person cannot simply undo. */
  danger?: boolean;
  /** Green confirm button for a positive decision (approve, accept). */
  positive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  /** Extra content between the message and the buttons (e.g. a reason field). */
  children?: React.ReactNode;
  /** Disable the confirm button (e.g. until a required reason is typed). */
  confirmDisabled?: boolean;
};

/**
 * The app's one confirmation dialog. Use it for any action a person cannot take back
 * in the next click — submitting a report for approval, deactivating an account.
 *
 * Deliberately not `window.confirm`: that can't be translated and can't say which
 * record it is about.
 */
export default function ConfirmDialog({
  title,
  body,
  confirmLabel,
  danger,
  positive,
  busy,
  onConfirm,
  onCancel,
  children,
  confirmDisabled,
}: Props) {
  const { t } = useT();
  const confirmRef = useRef<HTMLButtonElement>(null);
  const tone = danger ? "danger" : positive ? "success" : "default";

  return (
    <Dialog
      size="sm"
      title={title}
      description={body}
      tone={tone}
      icon={danger ? <TriangleAlert /> : positive ? <CircleCheck /> : undefined}
      onClose={busy ? () => {} : onCancel}
      initialFocus={children ? undefined : confirmRef}
      footer={
        <>
          <Button variant="outline" onClick={onCancel} disabled={busy}>
            {t("cancel")}
          </Button>
          <Button
            ref={confirmRef}
            variant={danger ? "danger" : positive ? "success" : "primary"}
            onClick={onConfirm}
            loading={busy}
            disabled={confirmDisabled}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
    </Dialog>
  );
}
