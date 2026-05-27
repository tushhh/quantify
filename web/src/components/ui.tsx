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

  const accentBar =
    positive === true
      ? "bg-[var(--color-cta)]"
      : positive === false
      ? "bg-[var(--color-danger)]"
      : "bg-[var(--color-info)]";

  return (
    <div className={clsx("card p-4 flex flex-col gap-1.5 animate-fade-in", className)}>
      <div className={clsx("absolute top-0 left-0 w-full h-[3px]", accentBar)} />
      <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest leading-none">{label}</p>
      <p className={clsx("font-bold tabular-nums leading-none mt-0.5", valueColor,
        size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-xl"
      )}>
        {value}
      </p>
      {sub && <p className="text-[10px] text-slate-500 mt-0.5 font-mono">{sub}</p>}
    </div>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────────

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("card", className)}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4 border-b border-[var(--border)] pb-2">
      <div>
        <h2 className="text-sm font-bold text-white tracking-[0.1em] uppercase font-heading">{title}</h2>
        {subtitle && <p className="text-[10px] text-[var(--color-cta)] mt-0.5 font-mono">{subtitle}</p>}
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
        "inline-flex items-center px-2 py-0.5 rounded-none border text-[10px] font-bold uppercase tracking-widest font-mono",
        {
          "bg-black text-slate-400 border-slate-700":                          variant === "default",
          "bg-black text-[var(--color-cta)] border-[var(--color-cta)]":        variant === "success",
          "bg-black text-[var(--color-danger)] border-[var(--color-danger)]":  variant === "danger",
          "bg-black text-amber-400 border-amber-500":                          variant === "warning",
          "bg-black text-[var(--color-info)] border-[var(--color-info)]":      variant === "blue",
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
          "hover:bg-[var(--border)] text-slate-400 hover:text-white rounded-none px-4 py-2 text-sm font-bold transition-all uppercase tracking-widest":
            variant === "ghost",
          "bg-transparent hover:bg-[var(--color-danger)] text-[var(--color-danger)] hover:text-black border border-[var(--color-danger)] rounded-none px-4 py-2 text-sm font-bold transition-all uppercase tracking-widest":
            variant === "danger",
        },
        className
      )}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      )}
      {children}
    </button>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton rounded-none", className)} />;
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
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-center">
        <label className="text-xs font-bold text-slate-500 uppercase tracking-widest">{label}</label>
        <span className="text-xs font-mono font-bold text-[var(--color-cta)] tabular-nums">{display}</span>
      </div>
      <div className="relative h-2 rounded-none bg-[var(--border)]">
        <div
          className="absolute top-0 left-0 h-full rounded-none bg-[var(--color-cta)]"
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
    info:    "bg-black border-[var(--color-info)] text-[var(--color-info)]",
    success: "bg-black border-[var(--color-cta)] text-[var(--color-cta)]",
    danger:  "bg-black border-[var(--color-danger)] text-[var(--color-danger)]",
    warning: "bg-black border-amber-500 text-amber-500",
  };
  return (
    <div className={clsx("flex items-start gap-2.5 p-3.5 rounded-none border-[2px] font-mono text-xs leading-relaxed animate-fade-in", styles[variant], className)}>
      {children}
    </div>
  );
}
