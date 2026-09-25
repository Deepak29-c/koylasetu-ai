"use client";

import { ChevronDown } from "lucide-react";
import { createContext, forwardRef, useContext, useId } from "react";

import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n";

/** Shared look of every text control. */
export const controlClass =
  "block w-full rounded-control border border-line-strong bg-surface px-3 text-sm text-foreground " +
  "placeholder:text-subtle transition-[border-color,box-shadow] duration-150 " +
  "hover:border-muted focus:border-brand focus:outline-none focus:ring-[3px] focus:ring-brand/15 " +
  "disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-disabled " +
  "aria-[invalid=true]:border-danger aria-[invalid=true]:ring-danger/15";

type FieldCtx = { id: string; describedBy?: string; invalid: boolean; required?: boolean };
const FieldContext = createContext<FieldCtx | null>(null);

type FieldProps = {
  label: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  optional?: boolean;
  className?: string;
  /** Visually hide the label (it stays available to screen readers). */
  hideLabel?: boolean;
  children: React.ReactNode;
};

/**
 * A label, the control, a hint and an error, wired together: the control inside gets the
 * id, aria-describedby and aria-invalid automatically.
 */
export function Field({ label, hint, error, required, optional, className, hideLabel, children }: FieldProps) {
  const { t } = useT();
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <FieldContext.Provider value={{ id, describedBy, invalid: !!error, required }}>
      <div className={cn("space-y-1.5", className)}>
        <label htmlFor={id} className={cn("block text-xs font-semibold text-strong", hideLabel && "sr-only")}>
          {label}
          {required && (
            <span className="ml-0.5 text-danger" aria-hidden>
              *
            </span>
          )}
          {optional && <span className="ml-1 font-normal text-subtle">({t("ui.optional")})</span>}
        </label>
        {children}
        {hint && !error && (
          <p id={hintId} className="text-xs text-subtle">
            {hint}
          </p>
        )}
        {error && (
          <p id={errorId} role="alert" className="text-xs font-medium text-danger-fg">
            {error}
          </p>
        )}
      </div>
    </FieldContext.Provider>
  );
}

function useFieldProps<T extends { id?: string; "aria-describedby"?: string; required?: boolean }>(props: T) {
  const ctx = useContext(FieldContext);
  if (!ctx) return props;
  return {
    ...props,
    id: props.id ?? ctx.id,
    "aria-describedby": props["aria-describedby"] ?? ctx.describedBy,
    "aria-invalid": ctx.invalid || undefined,
    required: props.required ?? ctx.required,
  };
}

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(controlClass, "h-10", className)} {...useFieldProps(props)} />;
  },
);

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, rows = 4, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        rows={rows}
        className={cn(controlClass, "resize-y py-2.5 leading-relaxed", className)}
        {...useFieldProps(props)}
      />
    );
  },
);

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  function Select({ className, children, ...props }, ref) {
    return (
      <div className="relative">
        <select
          ref={ref}
          className={cn(controlClass, "h-10 appearance-none pr-9", className)}
          {...useFieldProps(props)}
        >
          {children}
        </select>
        <ChevronDown
          size={16}
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-subtle"
        />
      </div>
    );
  },
);

type CheckboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: React.ReactNode;
  description?: React.ReactNode;
};

export function Checkbox({ label, description, className, ...props }: CheckboxProps) {
  const id = useId();
  return (
    <div className={cn("flex items-start gap-2.5", className)}>
      <input
        id={props.id ?? id}
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 cursor-pointer rounded accent-brand disabled:cursor-not-allowed"
        {...props}
      />
      <label htmlFor={props.id ?? id} className="cursor-pointer text-sm leading-snug">
        {label}
        {description && <span className="block text-xs text-subtle">{description}</span>}
      </label>
    </div>
  );
}

/** A group of checkboxes or radios with a visible legend. */
export function Fieldset({
  legend,
  hint,
  error,
  className,
  children,
}: {
  legend: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <fieldset className={cn("space-y-2", className)}>
      <legend className="mb-1.5 text-xs font-semibold text-strong">{legend}</legend>
      {hint && <p className="text-xs text-subtle">{hint}</p>}
      {children}
      {error && (
        <p role="alert" className="text-xs font-medium text-danger-fg">
          {error}
        </p>
      )}
    </fieldset>
  );
}
