import { clsx } from "clsx";
import { HTMLAttributes } from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "accent";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border-[var(--color-border)]",
  success: "bg-[var(--color-success-subtle)] text-[var(--color-success)] border-transparent",
  warning: "bg-[var(--color-warning-subtle)] text-[var(--color-warning)] border-transparent",
  danger:  "bg-[var(--color-danger-subtle)] text-[var(--color-danger)] border-transparent",
  accent:  "bg-[var(--color-accent-subtle)] text-[var(--color-accent)] border-transparent",
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full border",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}
