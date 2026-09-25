"use client";

import { X } from "lucide-react";
import { useId, useRef } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

import { useFocusTrap } from "./Dialog";

type DrawerProps = {
  title: React.ReactNode;
  /** Small uppercase line above the title. */
  eyebrow?: React.ReactNode;
  description?: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  wide?: boolean;
};

/** A floating side panel for forms and details that should not leave the page. */
export default function Drawer({ title, eyebrow, description, onClose, children, footer, wide }: DrawerProps) {
  const { t } = useT();
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(ref, onClose);

  return createPortal(
    <div className="fixed inset-0 z-[60] bg-scrim backdrop-blur-[3px]" onMouseDown={onClose}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(e) => e.stopPropagation()}
        className={cn(
          "absolute inset-y-2 right-2 flex animate-drawer-in flex-col overflow-hidden rounded-card bg-surface shadow-float sm:inset-y-6 sm:right-4",
          wide ? "w-[min(720px,calc(100vw-1rem))]" : "w-[min(540px,calc(100vw-1rem))]",
        )}
      >
        <div className="flex items-start gap-3 border-b border-line bg-surface-subtle px-4 py-4 sm:px-6 sm:py-5">
          <div className="min-w-0 flex-1">
            {eyebrow && <p className="text-[11px] font-bold tracking-[0.08em] text-brand uppercase">{eyebrow}</p>}
            <h2 id={titleId} className="text-lg font-semibold text-strong">
              {title}
            </h2>
            {description && <p className="mt-1 text-xs text-muted">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("ui.close")}
            className="grid size-9 place-items-center rounded-full bg-surface text-muted shadow-pill hover:text-strong"
          >
            <X size={18} aria-hidden />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-4 py-3 sm:px-6 sm:py-4">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
