import React from "react";

/**
 * Quantify Badge — small status / category pill.
 * Used for LONG/SHORT signals, strategy tags, live status, etc.
 */
export function Badge({ children, variant = "default", style = {}, ...rest }) {
  const variants = {
    default: { background: "var(--color-surface-raised)", color: "var(--color-text-secondary)", borderColor: "var(--color-border)" },
    success: { background: "var(--color-success-subtle)", color: "var(--color-success)", borderColor: "color-mix(in srgb, var(--color-success) 30%, transparent)" },
    danger:  { background: "var(--color-danger-subtle)",  color: "var(--color-danger)",  borderColor: "color-mix(in srgb, var(--color-danger) 30%, transparent)" },
    warning: { background: "var(--color-warning-subtle)", color: "var(--color-warning)", borderColor: "color-mix(in srgb, var(--color-warning) 30%, transparent)" },
    info:    { background: "var(--color-info-subtle)",    color: "var(--color-info)",    borderColor: "color-mix(in srgb, var(--color-info) 30%, transparent)" },
    accent:  { background: "var(--color-accent-subtle)",  color: "var(--color-accent)",  borderColor: "color-mix(in srgb, var(--color-accent) 30%, transparent)" },
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        paddingTop: 3, paddingBottom: 3, paddingLeft: 9, paddingRight: 9,
        fontFamily: "var(--font-sans)",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.04em",
        borderRadius: "var(--radius-full)",
        border: "1px solid transparent",
        ...variants[variant],
        ...style,
      }}
      {...rest}
    >
      {children}
    </span>
  );
}
