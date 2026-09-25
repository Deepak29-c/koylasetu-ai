"use client";

import { useEffect, useRef } from "react";

import { useT } from "@/lib/i18n";

type Props = {
  title: string;
  body: string;
  confirmLabel: string;
  /** Red confirm button for anything the person cannot simply undo. */
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
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
  busy,
  onConfirm,
  onCancel,
}: Props) {
  const { t } = useT();
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md space-y-4 rounded border bg-white p-5 shadow-lg"
      >
        <h2 id="confirm-title" className="text-lg font-semibold">
          {title}
        </h2>
        <p className="text-sm text-gray-700">{body}</p>
        <div className="flex flex-wrap justify-end gap-3">
          <button onClick={onCancel} className="rounded border px-4 py-2 text-sm font-medium">
            {t("cancel")}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            disabled={busy}
            className={`rounded px-4 py-2 text-sm font-medium text-white disabled:opacity-60 ${
              danger ? "bg-red-700" : "bg-brand"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
