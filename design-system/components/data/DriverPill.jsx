import React from "react";

/**
 * DriverPill — a single feature driver behind an ML prediction.
 * Shows the feature name (mono), its z-score, and a direction arrow:
 * ▲ green when higher-is-favorable, ▼ red when lower-is-favorable.
 */
export function DriverPill({ feature, zscore, direction = "higher", style = {}, ...rest }) {
  const up = direction === "higher";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 9px",
        borderRadius: "var(--radius-full)",
        border: "1px solid var(--color-border)",
        background: "var(--color-surface-raised)",
        fontSize: 11,
        color: "var(--color-text-muted)",
        ...style,
      }}
      {...rest}
    >
      <span aria-hidden="true" style={{ color: up ? "var(--color-success)" : "var(--color-danger)", fontSize: 9 }}>{up ? "▲" : "▼"}</span>
      <span style={{ fontFamily: "var(--font-mono)", color: "var(--color-text-secondary)" }}>{feature}</span>
      {zscore !== undefined && zscore !== null ? (
        <span style={{ fontFamily: "var(--font-mono)" }}>z={Number(zscore).toFixed(2)}</span>
      ) : null}
    </span>
  );
}
