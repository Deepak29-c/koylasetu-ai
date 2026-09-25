"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Traps Tab inside `ref` while mounted, closes on Escape, and gives focus back to the
 * element that opened it when it closes.
 */
export function useFocusTrap(ref: React.RefObject<HTMLElement | null>, onClose: () => void, initial?: React.RefObject<HTMLElement | null>) {
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  // Read during the first render: by the time effects run, an autoFocus field inside has
  // already taken focus, and that field is not what should get focus back on close.
  const [opener] = useState(() => (typeof document === "undefined" ? null : (document.activeElement as HTMLElement | null)));

  useEffect(() => {
    const node = ref.current;
    if (!node?.contains(document.activeElement)) {
      (initial?.current ?? node?.querySelector<HTMLElement>(FOCUSABLE) ?? node)?.focus();
    }
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !node) return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      opener?.focus?.();
    };
    // Runs once per open; `initial` and `ref` are stable refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}

type DialogProps = {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  tone?: "default" | "danger" | "success";
  onClose: () => void;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg";
  initialFocus?: React.RefObject<HTMLElement | null>;
};

export default function Dialog({
  title,
  description,
  icon,
  tone = "default",
  onClose,
  children,
  footer,
  size = "md",
  initialFocus,
}: DialogProps) {
  const { t } = useT();
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descId = useId();
  useFocusTrap(ref, onClose, initialFocus);

  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-scrim p-4 backdrop-blur-[3px]" onMouseDown={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        onMouseDown={(e) => e.stopPropagation()}
        className={cn(
          "relative max-h-[90vh] w-full animate-panel-in overflow-y-auto rounded-card bg-surface p-6 shadow-float sm:p-7",
          size === "sm" ? "max-w-md" : size === "md" ? "max-w-lg" : "max-w-2xl",
        )}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={t("ui.close")}
          className="absolute top-4 right-4 rounded-full p-1.5 text-subtle hover:bg-surface-sunken hover:text-strong"
        >
          <X size={18} aria-hidden />
        </button>
        {icon && (
          <span
            aria-hidden
            className={cn(
              "mb-4 grid size-12 place-items-center rounded-full [&_svg]:size-6",
              tone === "danger" ? "bg-danger-bg text-danger" : tone === "success" ? "bg-success-bg text-success" : "bg-brand-soft text-brand",
            )}
          >
            {icon}
          </span>
        )}
        <h2 id={titleId} className="pr-8 text-lg leading-7 font-semibold text-strong">
          {title}
        </h2>
        {description && (
          <p id={descId} className="mt-2 text-sm leading-relaxed text-muted">
            {description}
          </p>
        )}
        {children && <div className="mt-4">{children}</div>}
        {footer && <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
