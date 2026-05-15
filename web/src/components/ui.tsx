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
      ? "text-emerald-400"
      : "text-red-400";

  const accentBar =
    positive === true
      ? "bg-emerald-500"
      : positive === false
      ? "bg-red-500"
      : "bg-blue-500";

  return (
    <div className={clsx("rounded-xl glass hover-lift p-4 flex flex-col gap-1.5 relative overflow-hidden animate-fade-in", className)}>
      <div className={clsx("absolute top-0 left-0 w-full h-[2px]", accentBar, "opacity-60")} />
      <p className="text-[10px] text-slate-400 font-semibold uppercase tracking-widest leading-none">{label}</p>
      <p className={clsx("font-bold tabular-nums leading-none mt-0.5", valueColor,
        size === "lg" ? "text-2xl" : size === "sm" ? "text-base" : "text-xl"
      )}>
        {value}
      </p>
      {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Card ─────────────────────────────────────────────────────────────────────

export function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={clsx("rounded-xl glass p-5", className)}>
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
    <div className="flex items-center justify-between mb-4">
      <div>
        <h2 className="text-sm font-bold text-white tracking-tight">{title}</h2>
        {subtitle && <p className="text-[11px] text-slate-500 mt-0.5">{subtitle}</p>}
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
        "inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide",
        {
          "bg-slate-800 text-slate-400 border border-slate-700":              variant === "default",
          "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20":  variant === "success",
          "bg-red-500/15 text-red-400 border border-red-500/20":              variant === "danger",
          "bg-amber-500/15 text-amber-400 border border-amber-500/20":        variant === "warning",
          "bg-blue-500/15 text-blue-400 border border-blue-500/20":           variant === "blue",
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
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold",
        "transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]",
        {
          "bg-blue-600 hover:bg-blue-500 text-white shadow-sm shadow-blue-900/30":
            variant === "primary",
          "bg-[var(--surface-raised)] border border-[var(--border)] hover:border-[var(--border-bright)] text-slate-200 hover:text-white":
            variant === "secondary",
          "hover:bg-[var(--surface-raised)] text-slate-400 hover:text-white":
            variant === "ghost",
          "bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20":
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
  return <div className={clsx("skeleton", className)} />;
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
        <label className="text-xs text-slate-400">{label}</label>
        <span className="text-xs font-mono font-bold text-blue-400 tabular-nums">{display}</span>
      </div>
      <div className="relative h-1.5 rounded-full bg-slate-700/60">
        <div
          className="absolute top-0 left-0 h-full rounded-full bg-blue-500/60"
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
    info:    "bg-blue-500/10 border-blue-500/30 text-blue-300",
    success: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
    danger:  "bg-red-500/10 border-red-500/30 text-red-300",
    warning: "bg-amber-500/10 border-amber-500/30 text-amber-300",
  };
  return (
    <div className={clsx("flex items-start gap-2.5 p-3.5 rounded-xl border text-xs leading-relaxed animate-fade-in", styles[variant], className)}>
      {children}
    </div>
  );
}
