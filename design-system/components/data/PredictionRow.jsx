import React from "react";
import { Badge } from "../core/Badge.jsx";
import { DriverPill } from "./DriverPill.jsx";

/**
 * PredictionRow — a single ranked ML signal as it appears in the
 * "Today's Picks" / screener list: rank, ticker, side badge, predicted
 * return, driver pills, and a tabular strength score.
 */
export function PredictionRow({ rank, symbol, side = "long", predictedReturnPct = 0, strength = 0, drivers = [], onClick, style = {}, ...rest }) {
  const positiveRet = predictedReturnPct >= 0;
  const positiveStr = strength >= 0;
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "grid",
        gridTemplateColumns: "40px 1fr auto auto",
        alignItems: "center",
        gap: 16,
        width: "100%",
        textAlign: "left",
        padding: "14px 18px",
        background: "transparent",
        border: "none",
        borderBottom: "1px solid var(--color-border)",
        cursor: onClick ? "pointer" : "default",
        fontFamily: "var(--font-sans)",
        transition: "background var(--duration-fast) var(--ease-standard)",
        ...style,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--color-surface-raised)"; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
      {...rest}
    >
      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text-muted)" }}>
        #{String(rank).padStart(2, "0")}
      </span>

      <span style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 0 }}>
        <span style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)", letterSpacing: "-0.01em" }}>{symbol}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: positiveRet ? "var(--color-success)" : "var(--color-danger)" }}>
            {positiveRet ? "+" : ""}{Number(predictedReturnPct).toFixed(2)}% 1d
          </span>
        </span>
        {drivers && drivers.length ? (
          <span style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {drivers.slice(0, 3).map((d, i) => (
              <DriverPill key={i} feature={d.feature} zscore={d.zscore} direction={d.direction} />
            ))}
          </span>
        ) : null}
      </span>

      <Badge variant={side === "long" ? "success" : "danger"}>{String(side).toUpperCase()}</Badge>

      <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 14, fontVariantNumeric: "tabular-nums", color: positiveStr ? "var(--color-success)" : "var(--color-danger)", textAlign: "right", minWidth: 64 }}>
        {positiveStr ? "+" : ""}{Number(strength).toFixed(3)}
      </span>
    </button>
  );
}
