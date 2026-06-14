import React from "react";

/** Quantify Alert — inline status banner for info / success / danger / warning. */
export function Alert({ children, variant = "info", title, icon = null, style = {}, ...rest }) {
  const map = {
    info:    { fg: "var(--color-info)",    bg: "var(--color-info-subtle)",    glyph: "ⓘ" },
    success: { fg: "var(--color-success)", bg: "var(--color-success-subtle)", glyph: "✓" },
    danger:  { fg: "var(--color-danger)",  bg: "var(--color-danger-subtle)",  glyph: "!" },
    warning: { fg: "var(--color-warning)", bg: "var(--color-warning-subtle)", glyph: "△" },
  };
  const v = map[variant];
  return (
    <div
      role="status"
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "12px 14px",
        borderRadius: "var(--radius-md)",
        border: `1px solid color-mix(in srgb, ${v.fg} 28%, transparent)`,
        background: v.bg,
        fontFamily: "var(--font-sans)",
        fontSize: 13,
        lineHeight: 1.5,
        color: "var(--color-text-secondary)",
        ...style,
      }}
      {...rest}
    >
      <span style={{ flexShrink: 0, width: 20, height: 20, borderRadius: "var(--radius-full)", display: "inline-flex", alignItems: "center", justifyContent: "center", background: `color-mix(in srgb, ${v.fg} 18%, transparent)`, color: v.fg, fontSize: 12, fontWeight: 700 }}>
        {icon || v.glyph}
      </span>
      <div style={{ minWidth: 0 }}>
        {title ? <div style={{ fontWeight: 600, color: v.fg, marginBottom: 2 }}>{title}</div> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}
