"use client";

import clsx from "clsx";
import { useId } from "react";

type MetricCardProps = {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean | null; // null = neutral
  size?: "sm" | "md" | "lg";
  className?: string;
};

export function MetricCard({
  label,
  value,
  sub,
  positive,
  size = "md",
  className,
}: MetricCardProps) {
  const valueColor =
    positive === null || positive === undefined
      ? "text-white"
      : positive
      ? "text-emerald-400"
      : "text-red-400";

  return (
    <div
      className={clsx(
        "rounded-xl glass hover-lift p-4 flex flex-col gap-1 animate-fade-in",
        className
      )}
    >
      <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">{label}</p>
      <p
        className={clsx(
          "font-bold tabular-nums",
          valueColor,
          size === "lg" ? "text-3xl" : size === "sm" ? "text-base" : "text-2xl"
        )}
      >
        {value}
      </p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

type SectionProps = {
  children: React.ReactNode;
  className?: string;
};

export function Card({ children, className }: SectionProps) {
  return (
    <div
      className={clsx(
        "rounded-lg glass p-5",
        className
      )}
    >
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
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

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
      className={clsx("inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide", {
        "bg-slate-800 text-slate-400":     variant === "default",
        "bg-emerald-500/15 text-emerald-400": variant === "success",
        "bg-red-500/15 text-red-400":     variant === "danger",
        "bg-amber-500/15 text-amber-400": variant === "warning",
        "bg-blue-500/15 text-blue-400":   variant === "blue",
      }, className)}
    >
      {children}
    </span>
  );
}

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
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed",
        {
          "gradient-accent hover-lift text-white shadow-lg shadow-cyan-500/20 active:scale-95 hover:shadow-lg hover:shadow-cyan-500/40":
            variant === "primary",
          "glass hover:border-cyan-500/30 text-slate-300 hover:text-white":
            variant === "secondary",
          "hover:bg-white/5 text-slate-400 hover:text-white":
            variant === "ghost",
          "bg-red-500/15 hover:bg-red-500/25 text-red-400 border border-red-500/20":
            variant === "danger",
        },
        className
      )}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
        </svg>
      )}
      {children}
    </button>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

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
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-center">
        <label htmlFor={id} className="text-xs text-slate-400">{label}</label>
        <span className="text-xs font-mono font-semibold text-cyan-400">{display}</span>
      </div>
      <input
        id={id}
        aria-valuetext={display}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full bg-slate-700/40 accent-cyan-400 cursor-pointer"
      />
    </div>
  );
}
