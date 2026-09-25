"use client";

import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "lucide-react";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

type AlertTone = "info" | "success" | "warning" | "danger";

const styles: Record<AlertTone, string> = {
  info: "border-info-border bg-info-bg text-info-fg",
  success: "border-success-border bg-success-bg text-success-fg",
  warning: "border-warning-border bg-warning-bg text-warning-fg",
  danger: "border-danger-border bg-danger-bg text-danger-fg",
};

const icons: Record<AlertTone, typeof Info> = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  danger: CircleAlert,
};

type AlertProps = {
  tone?: AlertTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  /** A button or link at the end, e.g. "Try again". */
  action?: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
};

/**
 * An inline message. Danger alerts are announced at once (role="alert"); the others are
 * announced politely when they appear.
 */
export default function Alert({ tone = "info", title, children, action, onDismiss, className }: AlertProps) {
  const { t } = useT();
  const Icon = icons[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("flex items-start gap-3 rounded-panel border px-4 py-3 text-sm", styles[tone], className)}
    >
      <Icon size={18} aria-hidden className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1 space-y-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="break-words [&_a]:font-medium [&_a]:underline">{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={t("ui.dismiss")}
          className="-m-1 shrink-0 rounded-full p-1 opacity-70 hover:opacity-100"
        >
          <X size={16} aria-hidden />
        </button>
      )}
    </div>
  );
}
