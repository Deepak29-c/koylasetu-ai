"use client";

import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

type ToastTone = "success" | "danger" | "info";
type ToastInput = { tone?: ToastTone; title: string; body?: string; action?: { label: string; onClick: () => void } };
type ToastItem = ToastInput & { id: number };

const ToastContext = createContext<((t: ToastInput) => void) | null>(null);

const accent: Record<ToastTone, string> = {
  success: "before:bg-success",
  danger: "before:bg-danger",
  info: "before:bg-brand",
};
const iconColor: Record<ToastTone, string> = {
  success: "text-success",
  danger: "text-danger",
  info: "text-brand",
};
const icons = { success: CircleCheck, danger: CircleAlert, info: Info };

/**
 * Short confirmations for actions whose result is not visible where the person is looking
 * (approved a report, created a user, queued a retry). Errors about a form stay next to
 * the form as an <Alert>.
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);

  const push = useCallback(
    (input: ToastInput) => {
      const id = nextId.current++;
      setItems((xs) => [...xs.slice(-3), { tone: "success", ...input, id }]);
      window.setTimeout(() => dismiss(id), input.tone === "danger" ? 9000 : 5000);
    },
    [dismiss],
  );

  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport items={items} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastViewport({ items, onDismiss }: { items: ToastItem[]; onDismiss: (id: number) => void }) {
  const { t } = useT();
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed top-4 right-4 left-4 z-[70] flex flex-col items-end gap-2 sm:left-auto sm:w-[26rem]"
    >
      {items.map((it) => {
        const tone = it.tone ?? "success";
        const Icon = icons[tone];
        return (
          <div
            key={it.id}
            role={tone === "danger" ? "alert" : "status"}
            className={cn(
              "pointer-events-auto relative flex w-full animate-toast-in items-start gap-3 overflow-hidden rounded-control bg-surface py-3 pr-3 pl-5 shadow-pop",
              "before:absolute before:inset-y-0 before:left-0 before:w-1",
              accent[tone],
            )}
          >
            <Icon size={20} aria-hidden className={cn("mt-px shrink-0", iconColor[tone])} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-strong">{it.title}</p>
              {it.body && <p className="mt-0.5 text-xs text-muted">{it.body}</p>}
              {it.action && (
                <button
                  type="button"
                  onClick={() => {
                    it.action?.onClick();
                    onDismiss(it.id);
                  }}
                  className="mt-2 rounded-full border border-line-strong px-3 py-1 text-xs font-semibold text-brand hover:bg-brand-tint"
                >
                  {it.action.label}
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={() => onDismiss(it.id)}
              aria-label={t("ui.dismiss")}
              className="shrink-0 rounded-full p-1 text-subtle hover:bg-surface-sunken hover:text-strong"
            >
              <X size={16} aria-hidden />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function useToast() {
  const push = useContext(ToastContext);
  if (!push) throw new Error("useToast() used outside ToastProvider");
  return push;
}
