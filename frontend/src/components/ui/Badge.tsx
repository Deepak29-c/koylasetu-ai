import { cn } from "@/lib/cn";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral" | "brand";

const tones: Record<Tone, string> = {
  success: "border-success-border bg-success-bg text-success-fg",
  warning: "border-warning-border bg-warning-bg text-warning-fg",
  danger: "border-danger-border bg-danger-bg text-danger-fg",
  info: "border-info-border bg-info-bg text-info-fg",
  neutral: "border-neutral-border bg-neutral-bg text-neutral-fg",
  brand: "border-brand/15 bg-brand-soft text-brand",
};

const dots: Record<Tone, string> = {
  success: "bg-success",
  warning: "bg-warning-fg",
  danger: "bg-danger",
  info: "bg-info-fg",
  neutral: "bg-neutral-fg",
  brand: "bg-brand",
};

type BadgeProps = {
  tone?: Tone;
  /** A leading dot, so the state never rests on colour alone when there is no icon. */
  dot?: boolean;
  icon?: React.ReactNode;
  size?: "sm" | "md";
  className?: string;
  title?: string;
  children: React.ReactNode;
};

export default function Badge({ tone = "neutral", dot, icon, size = "sm", className, title, children }: BadgeProps) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border font-medium whitespace-nowrap",
        size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm",
        tones[tone],
        className,
      )}
    >
      {dot && <span aria-hidden className={cn("size-1.5 shrink-0 rounded-full", dots[tone])} />}
      {icon}
      <span className="truncate">{children}</span>
    </span>
  );
}
