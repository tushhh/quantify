"use client";

import clsx from "clsx";

// ── MetricCard ────────────────────────────────────────────────────────────────

type MetricCardProps = {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean | null;
  size?: "sm" | "md" | "lg";
  className?: string;
};

export function MetricCard({ label, value, sub, positive, size = "md", className }: MetricCardProps) {
  const valueColor =
    positive === null || positive === undefined
      ? "text-[var(--color-text-primary)]"
      : positive
      ? "text-[var(--color-success)]"
      : "text-[var(--color-danger)]";


  return (
    <div className={clsx("card flex flex-col justify-center", className)}>
      <p className="text-xs text-[var(--color-text-secondary)] mb-1">{label}</p>
      <p className={clsx("font-mono leading-tight tabular-nums", valueColor,
        size === "lg" ? "text-[25px]" : size === "sm" ? "text-base" : "text-xl"
      )}>
        {value}
      </p>
      {sub && <p className="text-xs text-[var(--color-text-muted)] mt-1">{sub}</p>}
    </div>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────────

export function Card({
  children,
  className,
  variant = "default",
}: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "compact";
}) {
  return (
    <div className={clsx("card", variant === "compact" && "card-compact", className)}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  children,
  density = "default",
  className,
}: {
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
  density?: "default" | "compact";
  className?: string;
}) {
  const spacing = density === "compact" ? "mb-3 pb-2.5" : "mb-4 pb-3";
  return (
    <div className={clsx("flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-b border-[var(--border)]", spacing, className)}>
      {title ? (
        <div className="space-y-1">
          <h2 className="text-sm font-medium text-[var(--color-text-primary)]">{title}</h2>
          {subtitle && <p className="text-xs text-[var(--color-text-secondary)]">{subtitle}</p>}
        </div>
      ) : null}
      {children}
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "danger" | "warning" | "blue";
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center px-1.5 py-0.5 rounded-[var(--radius-sm)] text-xs font-medium border",
        {
          "bg-[var(--color-surface)]/10 text-[var(--color-text-dim)] border-[var(--color-border-subtle)]": variant === "default",
          "bg-[var(--color-success)]/10 text-[var(--color-success)] border-[var(--color-success)]/25":       variant === "success",
          "bg-[var(--color-danger)]/10 text-[var(--color-danger)] border-[var(--color-danger)]/20":    variant === "danger",
          "bg-[var(--color-warning)]/10 text-[var(--color-warning)] border-[var(--color-warning)]/20":                variant === "warning",
          "bg-[var(--color-info)]/10 text-[var(--color-info)] border-[var(--color-info)]/20":    variant === "blue",
        },
        className
      )}
    >
      {children}
    </span>
  );
}

// ── Button ───────────────────────────────────────────────────────────────────

export function Button({
  children,
  onClick,
  disabled,
  loading,
  variant = "primary",
  className,
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  className?: string;
  type?: "button" | "submit";
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed",
        {
          "btn-primary": variant === "primary",
          "btn-secondary": variant === "secondary",
          "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] rounded-[var(--radius-sm)] h-9 px-3 text-sm font-medium":
            variant === "ghost",
          "bg-transparent hover:bg-[var(--color-danger)]/10 text-[var(--color-danger)] border border-[var(--color-danger)] rounded-[var(--radius-sm)] h-9 px-4 text-sm font-medium":
            variant === "danger",
        },
        className
      )}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      )}
      {children}
    </button>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton rounded-[var(--radius-sm)]", className)} />;
}

// ── Slider ───────────────────────────────────────────────────────────────────

export function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  format,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
}) {
  const display = format ? format(value) : String(value);
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex justify-between items-center">
        <label className="text-xs text-[var(--color-text-secondary)]">{label}</label>
        <span className="font-mono text-sm text-[var(--color-text-primary)]">{display}</span>
      </div>
      <div className="relative h-1 rounded-full bg-[var(--color-surface-raised)]">
        <div
          className="absolute top-0 left-0 h-full rounded-full bg-[var(--color-accent)]"
          style={{ width: `${pct}%` }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          style={{ zIndex: 1 }}
        />
      </div>
    </div>
  );
}

// ── Alert ─────────────────────────────────────────────────────────────────────

export function Alert({
  children,
  variant = "info",
  className,
}: {
  children: React.ReactNode;
  variant?: "info" | "success" | "danger" | "warning";
  className?: string;
}) {
  const styles = {
    info:    "bg-[var(--color-accent-subtle)] border-[var(--color-accent)]/40",
    success: "bg-[var(--color-success-subtle)] border-[var(--color-success)]/40",
    danger:  "bg-[var(--color-danger-subtle)] border-[var(--color-danger)]/40",
    warning: "bg-[var(--color-warning-subtle)] border-[var(--color-warning)]/40",
  };
  return (
    <div role="status" className={clsx("flex items-start gap-3 px-4 py-3 rounded-[var(--radius-lg)] border text-sm leading-relaxed text-[var(--color-text-primary)]", styles[variant], className)}>
      {children}
    </div>
  );
}
