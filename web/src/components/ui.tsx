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
      ? "text-white"
      : positive
      ? "text-[var(--color-cta)]"
      : "text-[var(--color-danger)]";

  const accentGlow =
    positive === true
      ? "from-[var(--color-cta)]"
      : positive === false
      ? "from-[var(--color-danger)]"
      : "from-[var(--color-info)]";

  return (
    <div className={clsx("card flex flex-col justify-center animate-fade-in relative overflow-hidden group", className)}>
      <div className={clsx("absolute -top-10 -left-10 w-32 h-32 bg-gradient-to-br to-transparent opacity-[0.03] group-hover:opacity-[0.08] transition-opacity duration-700 blur-2xl rounded-full", accentGlow)} />
      <p className="text-xs text-[var(--color-text-dim)] font-medium tracking-widest uppercase mb-2">{label}</p>
      <p className={clsx("font-heading leading-tight", valueColor,
        size === "lg" ? "text-4xl" : size === "sm" ? "text-xl" : "text-3xl"
      )}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-[var(--color-text-dim)] mt-2 opacity-80">{sub}</p>}
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
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
  density?: "default" | "compact";
}) {
  const spacing = density === "compact" ? "mb-3 pb-3" : "mb-4 pb-3";
  return (
    <div className={clsx("flex flex-col md:flex-row md:items-end md:justify-between gap-3 border-b border-[var(--border)]", spacing)}>
      <div className="space-y-1">
        <h2 className="text-xl md:text-2xl font-heading text-white font-medium tracking-wide">{title}</h2>
        {subtitle && <p className="text-sm text-[var(--color-text-dim)]">{subtitle}</p>}
      </div>
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
        "inline-flex items-center px-3 py-1 rounded-full text-[11px] font-semibold tracking-wider uppercase border backdrop-blur-md",
        {
          "bg-[rgba(255,255,255,0.03)] text-[var(--color-text-dim)] border-[rgba(255,255,255,0.1)]": variant === "default",
          "bg-[rgba(212,175,55,0.05)] text-[var(--color-cta)] border-[rgba(212,175,55,0.2)]":       variant === "success",
          "bg-[rgba(224,122,95,0.05)] text-[var(--color-danger)] border-[rgba(224,122,95,0.2)]":    variant === "danger",
          "bg-[rgba(245,158,11,0.05)] text-amber-500 border-[rgba(245,158,11,0.2)]":                variant === "warning",
          "bg-[rgba(129,161,193,0.05)] text-[var(--color-info)] border-[rgba(129,161,193,0.2)]":    variant === "blue",
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
          "hover:bg-[rgba(255,255,255,0.03)] text-[var(--color-text-dim)] hover:text-white rounded-full px-6 py-3 text-sm font-medium transition-all duration-300":
            variant === "ghost",
          "bg-transparent hover:bg-[rgba(224,122,95,0.1)] text-[var(--color-danger)] border border-[var(--color-danger)] rounded-full px-6 py-3 text-sm font-medium transition-all duration-300":
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
  return <div className={clsx("skeleton rounded-2xl", className)} />;
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
    <div className="flex flex-col gap-3">
      <div className="flex justify-between items-center">
        <label className="text-xs font-medium text-[var(--color-text-dim)] uppercase tracking-wider">{label}</label>
        <span className="text-sm font-medium text-[var(--color-cta)]">{display}</span>
      </div>
      <div className="relative h-1.5 rounded-full bg-[rgba(255,255,255,0.05)]">
        <div
          className="absolute top-0 left-0 h-full rounded-full bg-[var(--color-cta)] shadow-[0_0_10px_var(--color-cta)]"
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
    info:    "bg-[rgba(129,161,193,0.05)] border-[var(--color-info)] text-[var(--color-info)]",
    success: "bg-[rgba(212,175,55,0.05)] border-[var(--color-cta)] text-[var(--color-cta)]",
    danger:  "bg-[rgba(224,122,95,0.05)] border-[var(--color-danger)] text-[var(--color-danger)]",
    warning: "bg-[rgba(212,175,55,0.05)] border-[var(--color-cta)] text-[var(--color-cta)]",
  };
  return (
    <div className={clsx("flex items-start gap-4 p-5 rounded-2xl border text-sm leading-relaxed animate-fade-in shadow-xl backdrop-blur-md", styles[variant], className)}>
      {children}
    </div>
  );
}
