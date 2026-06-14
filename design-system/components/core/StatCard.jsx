import React from "react";

/** Quantify StatCard — a labelled metric with optional delta and icon. */
export function StatCard({ label, value, change, changeLabel = "vs last period", icon = null, style = {}, ...rest }) {
  const hasChange = change !== undefined && change !== null;
  const positive = hasChange && change >= 0;
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "18px 20px",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 16,
        ...style,
      }}
      {...rest}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-muted)" }}>{label}</span>
        <span style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--color-text-primary)", fontVariantNumeric: "tabular-nums" }}>{value}</span>
        {hasChange ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12, fontWeight: 600, color: positive ? "var(--color-success)" : "var(--color-danger)" }}>
            <span aria-hidden="true">{positive ? "▲" : "▼"}</span>
            {positive ? "+" : ""}{change}% <span style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>{changeLabel}</span>
          </span>
        ) : null}
      </div>
      {icon ? (
        <div style={{ display: "inline-flex", padding: 10, borderRadius: "var(--radius-md)", background: "var(--color-accent-subtle)", color: "var(--color-accent)" }}>{icon}</div>
      ) : null}
    </div>
  );
}
