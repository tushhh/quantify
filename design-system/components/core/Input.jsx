import React from "react";

/** Quantify text Input with optional label, hint and error. */
export function Input({ label, hint, error, prefix, id, style = {}, ...rest }) {
  const uid = React.useId();
  const inputId = id || (label ? `${label.toLowerCase().replace(/\s+/g, "-")}-${uid}` : uid);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%" }}>
      {label ? (
        <label htmlFor={inputId} style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)" }}>{label}</label>
      ) : null}
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        {prefix ? (
          <span style={{ position: "absolute", left: 12, color: "var(--color-text-muted)", fontFamily: "var(--font-mono)", fontSize: 13, pointerEvents: "none" }}>{prefix}</span>
        ) : null}
        <input
          id={inputId}
          style={{
            height: 36,
            width: "100%",
            background: "var(--color-surface-raised)",
            border: `1px solid ${error ? "var(--color-danger)" : "var(--color-border)"}`,
            borderRadius: "var(--radius-md)",
            color: "var(--color-text-primary)",
            fontFamily: "var(--font-sans)",
            fontSize: 14,
            padding: prefix ? "0 12px 0 26px" : "0 12px",
            outline: "none",
            transition: "border-color var(--duration-fast) var(--ease-standard), box-shadow var(--duration-fast) var(--ease-standard)",
            ...style,
          }}
          onFocus={(e) => { e.currentTarget.style.borderColor = error ? "var(--color-danger)" : "var(--color-accent)"; e.currentTarget.style.boxShadow = `0 0 0 3px ${error ? "var(--color-danger-subtle)" : "var(--color-accent-subtle)"}`; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = error ? "var(--color-danger)" : "var(--color-border)"; e.currentTarget.style.boxShadow = "none"; }}
          {...rest}
        />
      </div>
      {error ? <p style={{ margin: 0, fontSize: 12, color: "var(--color-danger)" }}>{error}</p>
        : hint ? <p style={{ margin: 0, fontSize: 12, color: "var(--color-text-muted)" }}>{hint}</p> : null}
    </div>
  );
}
