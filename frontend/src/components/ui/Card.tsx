import { cn } from "@/lib/cn";

type CardProps = React.HTMLAttributes<HTMLElement> & {
  as?: "section" | "div" | "article" | "aside";
  padded?: boolean;
};

/** A white panel on the grey canvas. */
export function Card({ as: Tag = "section", padded = true, className, ...rest }: CardProps) {
  return (
    <Tag
      className={cn("ks-card rounded-card border border-line bg-surface shadow-card", padded && "p-5 sm:p-6", className)}
      {...rest}
    />
  );
}

type CardHeaderProps = {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  /** An icon shown in a round badge before the title. */
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  /** Heading level; section headings inside a page are h2 by default. */
  level?: 2 | 3;
  id?: string;
};

export function CardHeader({ title, subtitle, icon, actions, className, level = 2, id }: CardHeaderProps) {
  const H = level === 2 ? "h2" : "h3";
  return (
    <div className={cn("mb-4 flex flex-wrap items-start gap-3", className)}>
      {icon && (
        <span
          aria-hidden
          className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-soft text-brand [&_svg]:size-[18px]"
        >
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <H id={id} className="text-base leading-6 font-semibold text-strong">
          {title}
        </H>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
