"use client";

import Link from "next/link";
import { forwardRef } from "react";

import { cn } from "@/lib/cn";

import Spinner from "./Spinner";

export type ButtonVariant =
  | "primary" // the one main action on a screen
  | "secondary" // white pill, for everything else
  | "outline" // bordered, inside cards and tables
  | "ghost" // toolbar and icon buttons
  | "success" // approve / accept
  | "danger" // reject / deactivate
  | "danger-outline"
  | "link"; // inline text action that is still a button
export type ButtonSize = "sm" | "md" | "lg" | "icon" | "icon-sm";

const base =
  "inline-flex shrink-0 items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap " +
  "transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-100 " +
  "disabled:bg-surface-sunken disabled:text-disabled disabled:shadow-none disabled:border-transparent";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-brand text-white hover:bg-brand-hover active:bg-brand-strong",
  secondary: "bg-surface text-brand shadow-pill hover:bg-brand-tint",
  outline: "border border-line-strong bg-surface text-brand hover:border-brand hover:bg-brand-tint",
  ghost: "text-brand hover:bg-brand-soft",
  success: "bg-success text-white hover:brightness-95",
  danger: "bg-danger text-white hover:brightness-95",
  "danger-outline": "border border-danger-border bg-surface text-danger-fg hover:bg-danger-bg",
  link:
    "h-auto rounded-sm px-0 py-0 font-medium text-brand underline-offset-2 hover:underline " +
    "disabled:bg-transparent",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-9 px-4 text-sm",
  lg: "h-11 px-6 text-sm",
  icon: "size-9 p-0",
  "icon-sm": "size-8 p-0",
};

type CommonProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and disables the button. */
  loading?: boolean;
  icon?: React.ReactNode;
  className?: string;
};

export function buttonClass({
  variant = "secondary",
  size = "md",
  className,
}: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {}) {
  return cn(base, variants[variant], variant !== "link" && sizes[size], className);
}

type ButtonProps = CommonProps & React.ButtonHTMLAttributes<HTMLButtonElement>;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, loading, icon, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass({ variant, size, className })}
      {...rest}
    >
      {loading ? <Spinner size={size === "sm" || size === "icon-sm" ? 14 : 16} /> : icon}
      {children}
    </button>
  );
});

type ButtonLinkProps = CommonProps &
  Omit<React.ComponentProps<typeof Link>, "className"> & { children?: React.ReactNode };

/** A link that looks like a button (navigation, not an action). */
export function ButtonLink({ variant, size, icon, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass({ variant, size, className })} {...rest}>
      {icon}
      {children}
    </Link>
  );
}
