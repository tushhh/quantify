import React from "react";

/** Quantify Card — surface container with hairline border + soft shadow. */
export function Card({ children, variant = "default", interactive = false, style = {}, ...rest }) {
  const pad = variant === "compact" ? 16 : 0;
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: pad,
        transition: "border-color var(--duration-base) var(--ease-standard), box-shadow var(--duration-base) var(--ease-standard)",
        ...style,
      }}
      onMouseEnter={interactive ? (e) => { e.currentTarget.style.borderColor = "var(--color-border-bright)"; e.currentTarget.style.boxShadow = "var(--shadow-md)"; } : undefined}
      onMouseLeave={interactive ? (e) => { e.currentTarget.style.borderColor = "var(--color-border)"; e.currentTarget.style.boxShadow = "var(--shadow-sm)"; } : undefined}
      {...rest}
    >
      {children}
    </div>
  );
}

/** Header row with title/subtitle and an optional actions slot. */
export function CardHeader({ title, subtitle, actions, children, style = {}, ...rest }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "18px 20px 14px",
        borderBottom: "1px solid var(--color-border)",
        ...style,
      }}
      {...rest}
    >
      {title || subtitle ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 3, minWidth: 0 }}>
          {title ? <h3 style={{ margin: 0, fontFamily: "var(--font-sans)", fontSize: 16, fontWeight: 600, letterSpacing: "-0.01em", color: "var(--color-text-primary)" }}>{title}</h3> : null}
          {subtitle ? <p style={{ margin: 0, fontSize: 13, color: "var(--color-text-muted)" }}>{subtitle}</p> : null}
        </div>
      ) : children}
      {actions ? <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>{actions}</div> : null}
    </div>
  );
}

/** Padded body region of a card. */
export function CardContent({ children, style = {}, ...rest }) {
  return <div style={{ padding: "18px 20px", ...style }} {...rest}>{children}</div>;
}

/** Footer with top divider for actions. */
export function CardFooter({ children, style = {}, ...rest }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 20px", borderTop: "1px solid var(--color-border)", ...style }} {...rest}>
      {children}
    </div>
  );
}
