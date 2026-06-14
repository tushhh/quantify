import React from "react";

/**
 * Quantify Button — primary action control.
 * Variants map to the brand accent (primary), raised surface (secondary),
 * transparent (ghost), destructive (danger), and inline (link).
 */
export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled = false,
  icon = null,
  type = "button",
  onClick,
  style = {},
  ...rest
}) {
  const sizes = {
    xs: { height: 28, paddingLeft: 10, paddingRight: 10, fontSize: 12, gap: 6 },
    sm: { height: 32, paddingLeft: 12, paddingRight: 12, fontSize: 13, gap: 6 },
    md: { height: 36, paddingLeft: 16, paddingRight: 16, fontSize: 14, gap: 8 },
    lg: { height: 44, paddingLeft: 24, paddingRight: 24, fontSize: 16, gap: 8 },
  };

  const base = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "var(--font-sans)",
    fontWeight: 600,
    borderRadius: "var(--radius-md)",
    border: "1px solid transparent",
    cursor: disabled || loading ? "not-allowed" : "pointer",
    opacity: disabled || loading ? 0.5 : 1,
    transition: "background var(--duration-fast) var(--ease-standard), border-color var(--duration-fast) var(--ease-standard), transform var(--duration-fast) var(--ease-standard)",
    whiteSpace: "nowrap",
    userSelect: "none",
    ...sizes[size],
  };

  const variants = {
    primary: { background: "var(--color-accent)", color: "var(--color-accent-foreground)", boxShadow: "var(--shadow-xs)" },
    secondary: { background: "var(--color-surface-raised)", color: "var(--color-text-primary)", borderColor: "var(--color-border)" },
    ghost: { background: "transparent", color: "var(--color-text-secondary)" },
    danger: { background: "var(--color-danger)", color: "var(--color-bg)" },
    link: { background: "transparent", color: "var(--color-accent)", height: "auto", padding: 0, textDecoration: "none" },
  };

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      style={{ ...base, ...variants[variant], ...style }}
      onMouseDown={(e) => { if (!disabled && !loading && variant !== "link") e.currentTarget.style.transform = "scale(0.98)"; }}
      onMouseUp={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
      {...rest}
    >
      {loading && (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style={{ marginRight: children ? 8 : 0, animation: "qf-spin 0.7s linear infinite" }}>
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
          <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
      )}
      {!loading && icon ? <span style={{ display: "inline-flex", marginRight: children ? 8 : 0 }}>{icon}</span> : null}
      {children}
      <style>{`@keyframes qf-spin { to { transform: rotate(360deg); } }`}</style>
    </button>
  );
}
