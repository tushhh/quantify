/* @ds-bundle: {"format":3,"namespace":"QuantifyDesignSystem_90f900","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"CardHeader","sourcePath":"components/core/Card.jsx"},{"name":"CardContent","sourcePath":"components/core/Card.jsx"},{"name":"CardFooter","sourcePath":"components/core/Card.jsx"},{"name":"Input","sourcePath":"components/core/Input.jsx"},{"name":"StatCard","sourcePath":"components/core/StatCard.jsx"},{"name":"DriverPill","sourcePath":"components/data/DriverPill.jsx"},{"name":"PredictionRow","sourcePath":"components/data/PredictionRow.jsx"},{"name":"Alert","sourcePath":"components/feedback/Alert.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"87d2db9e32ca","components/core/Button.jsx":"21966a5a9a46","components/core/Card.jsx":"2ad6c5ddb5ed","components/core/Input.jsx":"0c2602791683","components/core/StatCard.jsx":"7b7183d788e8","components/data/DriverPill.jsx":"c8e97fbce7c1","components/data/PredictionRow.jsx":"ecccab60da1c","components/feedback/Alert.jsx":"cd6c846b41db","ui_kits/web/data.js":"2293d7d1a6de","ui_kits/web/kit.jsx":"bf0c5339dda7","ui_kits/web/screens.jsx":"0b888dedcb06"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.QuantifyDesignSystem_90f900 = window.QuantifyDesignSystem_90f900 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Quantify Badge — small status / category pill.
 * Used for LONG/SHORT signals, strategy tags, live status, etc.
 */
function Badge({
  children,
  variant = "default",
  style = {},
  ...rest
}) {
  const variants = {
    default: {
      background: "var(--color-surface-raised)",
      color: "var(--color-text-secondary)",
      borderColor: "var(--color-border)"
    },
    success: {
      background: "var(--color-success-subtle)",
      color: "var(--color-success)",
      borderColor: "color-mix(in srgb, var(--color-success) 30%, transparent)"
    },
    danger: {
      background: "var(--color-danger-subtle)",
      color: "var(--color-danger)",
      borderColor: "color-mix(in srgb, var(--color-danger) 30%, transparent)"
    },
    warning: {
      background: "var(--color-warning-subtle)",
      color: "var(--color-warning)",
      borderColor: "color-mix(in srgb, var(--color-warning) 30%, transparent)"
    },
    info: {
      background: "var(--color-info-subtle)",
      color: "var(--color-info)",
      borderColor: "color-mix(in srgb, var(--color-info) 30%, transparent)"
    },
    accent: {
      background: "var(--color-accent-subtle)",
      color: "var(--color-accent)",
      borderColor: "color-mix(in srgb, var(--color-accent) 30%, transparent)"
    }
  };
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 5,
      padding: "3px 9px",
      fontFamily: "var(--font-sans)",
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: "0.04em",
      borderRadius: "var(--radius-full)",
      border: "1px solid transparent",
      ...variants[variant],
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Quantify Button — primary action control.
 * Variants map to the brand accent (primary), raised surface (secondary),
 * transparent (ghost), destructive (danger), and inline (link).
 */
function Button({
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
    xs: {
      height: 28,
      padding: "0 10px",
      fontSize: 12,
      gap: 6
    },
    sm: {
      height: 32,
      padding: "0 12px",
      fontSize: 13,
      gap: 6
    },
    md: {
      height: 36,
      padding: "0 16px",
      fontSize: 14,
      gap: 8
    },
    lg: {
      height: 44,
      padding: "0 24px",
      fontSize: 16,
      gap: 8
    }
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
    ...sizes[size]
  };
  const variants = {
    primary: {
      background: "var(--color-accent)",
      color: "var(--color-accent-foreground)",
      boxShadow: "var(--shadow-xs)"
    },
    secondary: {
      background: "var(--color-surface-raised)",
      color: "var(--color-text-primary)",
      borderColor: "var(--color-border)"
    },
    ghost: {
      background: "transparent",
      color: "var(--color-text-secondary)"
    },
    danger: {
      background: "var(--color-danger)",
      color: "#1a0608"
    },
    link: {
      background: "transparent",
      color: "var(--color-accent)",
      height: "auto",
      padding: 0,
      textDecoration: "none"
    }
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled || loading,
    onClick: onClick,
    style: {
      ...base,
      ...variants[variant],
      ...style
    },
    onMouseDown: e => {
      if (!disabled && !loading && variant !== "link") e.currentTarget.style.transform = "scale(0.98)";
    },
    onMouseUp: e => {
      e.currentTarget.style.transform = "scale(1)";
    },
    onMouseLeave: e => {
      e.currentTarget.style.transform = "scale(1)";
    }
  }, rest), loading && /*#__PURE__*/React.createElement("svg", {
    width: "15",
    height: "15",
    viewBox: "0 0 24 24",
    fill: "none",
    style: {
      marginRight: 8,
      animation: "qf-spin 0.7s linear infinite"
    }
  }, /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "10",
    stroke: "currentColor",
    strokeWidth: "3",
    opacity: "0.25"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M4 12a8 8 0 018-8",
    stroke: "currentColor",
    strokeWidth: "3",
    strokeLinecap: "round"
  })), !loading && icon ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      marginRight: children ? 8 : 0
    }
  }, icon) : null, children, /*#__PURE__*/React.createElement("style", null, `@keyframes qf-spin { to { transform: rotate(360deg); } }`));
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Quantify Card — surface container with hairline border + soft shadow. */
function Card({
  children,
  variant = "default",
  interactive = false,
  style = {},
  ...rest
}) {
  const pad = variant === "compact" ? 16 : 0;
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: "var(--color-surface)",
      border: "1px solid var(--color-border)",
      borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-sm)",
      padding: pad,
      transition: "border-color var(--duration-base) var(--ease-standard), box-shadow var(--duration-base) var(--ease-standard)",
      ...style
    },
    onMouseEnter: interactive ? e => {
      e.currentTarget.style.borderColor = "var(--color-border-bright)";
      e.currentTarget.style.boxShadow = "var(--shadow-md)";
    } : undefined,
    onMouseLeave: interactive ? e => {
      e.currentTarget.style.borderColor = "var(--color-border)";
      e.currentTarget.style.boxShadow = "var(--shadow-sm)";
    } : undefined
  }, rest), children);
}

/** Header row with title/subtitle and an optional actions slot. */
function CardHeader({
  title,
  subtitle,
  actions,
  children,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
      padding: "18px 20px 14px",
      borderBottom: "1px solid var(--color-border)",
      ...style
    }
  }, rest), title || subtitle ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 3,
      minWidth: 0
    }
  }, title ? /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontFamily: "var(--font-sans)",
      fontSize: 16,
      fontWeight: 600,
      letterSpacing: "-0.01em",
      color: "var(--color-text-primary)"
    }
  }, title) : null, subtitle ? /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 13,
      color: "var(--color-text-muted)"
    }
  }, subtitle) : null) : children, actions ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      flexShrink: 0
    }
  }, actions) : null);
}

/** Padded body region of a card. */
function CardContent({
  children,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      padding: "18px 20px",
      ...style
    }
  }, rest), children);
}

/** Footer with top divider for actions. */
function CardFooter({
  children,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "14px 20px",
      borderTop: "1px solid var(--color-border)",
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card, CardHeader, CardContent, CardFooter });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Quantify text Input with optional label, hint and error. */
function Input({
  label,
  hint,
  error,
  prefix,
  id,
  style = {},
  ...rest
}) {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      width: "100%"
    }
  }, label ? /*#__PURE__*/React.createElement("label", {
    htmlFor: inputId,
    style: {
      fontSize: 13,
      fontWeight: 500,
      color: "var(--color-text-primary)"
    }
  }, label) : null, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      alignItems: "center"
    }
  }, prefix ? /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      left: 12,
      color: "var(--color-text-muted)",
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      pointerEvents: "none"
    }
  }, prefix) : null, /*#__PURE__*/React.createElement("input", _extends({
    id: inputId,
    style: {
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
      ...style
    },
    onFocus: e => {
      e.currentTarget.style.borderColor = error ? "var(--color-danger)" : "var(--color-accent)";
      e.currentTarget.style.boxShadow = `0 0 0 3px ${error ? "var(--color-danger-subtle)" : "var(--color-accent-subtle)"}`;
    },
    onBlur: e => {
      e.currentTarget.style.borderColor = error ? "var(--color-danger)" : "var(--color-border)";
      e.currentTarget.style.boxShadow = "none";
    }
  }, rest))), error ? /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 12,
      color: "var(--color-danger)"
    }
  }, error) : hint ? /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: 12,
      color: "var(--color-text-muted)"
    }
  }, hint) : null);
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Input.jsx", error: String((e && e.message) || e) }); }

// components/core/StatCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Quantify StatCard — a labelled metric with optional delta and icon. */
function StatCard({
  label,
  value,
  change,
  changeLabel = "vs last period",
  icon = null,
  style = {},
  ...rest
}) {
  const hasChange = change !== undefined && change !== null;
  const positive = hasChange && change >= 0;
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: "var(--color-surface)",
      border: "1px solid var(--color-border)",
      borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-sm)",
      padding: "18px 20px",
      display: "flex",
      alignItems: "flex-start",
      justifyContent: "space-between",
      gap: 16,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 4,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      fontWeight: 500,
      color: "var(--color-text-muted)"
    }
  }, label), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 26,
      fontWeight: 700,
      letterSpacing: "-0.02em",
      color: "var(--color-text-primary)",
      fontVariantNumeric: "tabular-nums"
    }
  }, value), hasChange ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 4,
      fontSize: 12,
      fontWeight: 600,
      color: positive ? "var(--color-success)" : "var(--color-danger)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true"
  }, positive ? "▲" : "▼"), positive ? "+" : "", change, "% ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--color-text-muted)",
      fontWeight: 500
    }
  }, changeLabel)) : null), icon ? /*#__PURE__*/React.createElement("div", {
    style: {
      display: "inline-flex",
      padding: 10,
      borderRadius: "var(--radius-md)",
      background: "var(--color-accent-subtle)",
      color: "var(--color-accent)"
    }
  }, icon) : null);
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/data/DriverPill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * DriverPill — a single feature driver behind an ML prediction.
 * Shows the feature name (mono), its z-score, and a direction arrow:
 * ▲ green when higher-is-favorable, ▼ red when lower-is-favorable.
 */
function DriverPill({
  feature,
  zscore,
  direction = "higher",
  style = {},
  ...rest
}) {
  const up = direction === "higher";
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: "4px 9px",
      borderRadius: "var(--radius-full)",
      border: "1px solid var(--color-border)",
      background: "var(--color-surface-raised)",
      fontSize: 11,
      color: "var(--color-text-muted)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    "aria-hidden": "true",
    style: {
      color: up ? "var(--color-success)" : "var(--color-danger)",
      fontSize: 9
    }
  }, up ? "▲" : "▼"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      color: "var(--color-text-secondary)"
    }
  }, feature), zscore !== undefined && zscore !== null ? /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)"
    }
  }, "z=", Number(zscore).toFixed(2)) : null);
}
Object.assign(__ds_scope, { DriverPill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/DriverPill.jsx", error: String((e && e.message) || e) }); }

// components/data/PredictionRow.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * PredictionRow — a single ranked ML signal as it appears in the
 * "Today's Picks" / screener list: rank, ticker, side badge, predicted
 * return, driver pills, and a tabular strength score.
 */
function PredictionRow({
  rank,
  symbol,
  side = "long",
  predictedReturnPct = 0,
  strength = 0,
  drivers = [],
  onClick,
  style = {},
  ...rest
}) {
  const positiveRet = predictedReturnPct >= 0;
  const positiveStr = strength >= 0;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    onClick: onClick,
    style: {
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
      ...style
    },
    onMouseEnter: e => {
      e.currentTarget.style.background = "var(--color-surface-raised)";
    },
    onMouseLeave: e => {
      e.currentTarget.style.background = "transparent";
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--color-text-muted)"
    }
  }, "#", String(rank).padStart(2, "0")), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 16,
      fontWeight: 700,
      color: "var(--color-text-primary)",
      letterSpacing: "-0.01em"
    }
  }, symbol), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      color: positiveRet ? "var(--color-success)" : "var(--color-danger)"
    }
  }, positiveRet ? "+" : "", Number(predictedReturnPct).toFixed(2), "% 1d")), drivers && drivers.length ? /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      flexWrap: "wrap",
      gap: 6
    }
  }, drivers.slice(0, 3).map((d, i) => /*#__PURE__*/React.createElement(__ds_scope.DriverPill, {
    key: i,
    feature: d.feature,
    zscore: d.zscore,
    direction: d.direction
  }))) : null), /*#__PURE__*/React.createElement(__ds_scope.Badge, {
    variant: side === "long" ? "success" : "danger"
  }, String(side).toUpperCase()), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontWeight: 700,
      fontSize: 14,
      fontVariantNumeric: "tabular-nums",
      color: positiveStr ? "var(--color-success)" : "var(--color-danger)",
      textAlign: "right",
      minWidth: 64
    }
  }, positiveStr ? "+" : "", Number(strength).toFixed(3)));
}
Object.assign(__ds_scope, { PredictionRow });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/PredictionRow.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Alert.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/** Quantify Alert — inline status banner for info / success / danger / warning. */
function Alert({
  children,
  variant = "info",
  title,
  icon = null,
  style = {},
  ...rest
}) {
  const map = {
    info: {
      fg: "var(--color-info)",
      bg: "var(--color-info-subtle)",
      glyph: "ⓘ"
    },
    success: {
      fg: "var(--color-success)",
      bg: "var(--color-success-subtle)",
      glyph: "✓"
    },
    danger: {
      fg: "var(--color-danger)",
      bg: "var(--color-danger-subtle)",
      glyph: "!"
    },
    warning: {
      fg: "var(--color-warning)",
      bg: "var(--color-warning-subtle)",
      glyph: "△"
    }
  };
  const v = map[variant];
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "status",
    style: {
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
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      flexShrink: 0,
      width: 20,
      height: 20,
      borderRadius: "var(--radius-full)",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      background: `color-mix(in srgb, ${v.fg} 18%, transparent)`,
      color: v.fg,
      fontSize: 12,
      fontWeight: 700
    }
  }, icon || v.glyph), /*#__PURE__*/React.createElement("div", {
    style: {
      minWidth: 0
    }
  }, title ? /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: v.fg,
      marginBottom: 2
    }
  }, title) : null, /*#__PURE__*/React.createElement("div", null, children)));
}
Object.assign(__ds_scope, { Alert });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Alert.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/data.js
try { (() => {
// Mock data for the Quantify web UI kit. Attached to window.QKIT.
window.QKIT = {
  universe: [{
    symbol: "NVDA",
    name: "NVIDIA Corporation"
  }, {
    symbol: "AAPL",
    name: "Apple Inc."
  }, {
    symbol: "MSFT",
    name: "Microsoft Corporation"
  }, {
    symbol: "AMD",
    name: "Advanced Micro Devices"
  }, {
    symbol: "TSLA",
    name: "Tesla, Inc."
  }, {
    symbol: "META",
    name: "Meta Platforms, Inc."
  }, {
    symbol: "INTC",
    name: "Intel Corporation"
  }, {
    symbol: "JPM",
    name: "JPMorgan Chase & Co."
  }],
  predictions: [{
    rank: 1,
    symbol: "NVDA",
    side: "long",
    predictedReturnPct: 2.41,
    strength: 0.182,
    drivers: [{
      feature: "mom_12_1",
      zscore: 2.07,
      direction: "higher"
    }, {
      feature: "rsi_14",
      zscore: 1.21,
      direction: "higher"
    }, {
      feature: "vol_regime",
      zscore: 0.84,
      direction: "higher"
    }]
  }, {
    rank: 2,
    symbol: "AVGO",
    side: "long",
    predictedReturnPct: 1.88,
    strength: 0.147,
    drivers: [{
      feature: "ev_ebitda",
      zscore: 1.6,
      direction: "higher"
    }, {
      feature: "mom_6_1",
      zscore: 1.3,
      direction: "higher"
    }]
  }, {
    rank: 3,
    symbol: "AAPL",
    side: "long",
    predictedReturnPct: 1.06,
    strength: 0.094,
    drivers: [{
      feature: "vol_20",
      zscore: -1.4,
      direction: "lower"
    }, {
      feature: "roe",
      zscore: 1.1,
      direction: "higher"
    }]
  }, {
    rank: 4,
    symbol: "JPM",
    side: "long",
    predictedReturnPct: 0.72,
    strength: 0.061,
    drivers: [{
      feature: "value_pb",
      zscore: 1.2,
      direction: "higher"
    }, {
      feature: "quality",
      zscore: 0.8,
      direction: "higher"
    }]
  }, {
    rank: 5,
    symbol: "INTC",
    side: "short",
    predictedReturnPct: -1.73,
    strength: -0.121,
    drivers: [{
      feature: "trend_adx",
      zscore: -1.9,
      direction: "lower"
    }, {
      feature: "roe",
      zscore: -1.1,
      direction: "lower"
    }]
  }, {
    rank: 6,
    symbol: "PYPL",
    side: "short",
    predictedReturnPct: -2.14,
    strength: -0.158,
    drivers: [{
      feature: "mom_12_1",
      zscore: -2.2,
      direction: "lower"
    }, {
      feature: "margin",
      zscore: -1.3,
      direction: "lower"
    }]
  }],
  trades: [{
    id: 1,
    symbol: "MSFT",
    shares: 12,
    buy_price: 402.10,
    current: 421.55,
    hold_days: 21,
    dip: 0.10,
    in: "Jun 2",
    out: "Jun 23"
  }, {
    id: 2,
    symbol: "AMD",
    shares: 40,
    buy_price: 168.30,
    current: 159.04,
    hold_days: 14,
    dip: 0.08,
    in: "Jun 6",
    out: "Jun 20",
    alert: "PRICE DROP — 5.5% vs entry (threshold 8.0%)"
  }],
  strategies: [{
    name: "Trend Following",
    alloc: 15,
    sharpe: 1.21,
    idea: "EMA 50/200 crossover, ADX-filtered, ATR stops"
  }, {
    name: "Cross-Sectional Momentum",
    alloc: 20,
    sharpe: 1.64,
    idea: "Long top-quintile / short bottom by 12-1m returns"
  }, {
    name: "Pairs Mean Reversion",
    alloc: 20,
    sharpe: 0.98,
    idea: "Engle-Granger cointegration, z-score entry/exit"
  }, {
    name: "Quality Value",
    alloc: 20,
    sharpe: 1.07,
    idea: "Composite rank on value + quality metrics"
  }, {
    name: "ML Return Predictor",
    alloc: 15,
    sharpe: 1.84,
    idea: "LightGBM + XGBoost + CatBoost ensemble"
  }, {
    name: "Volatility Regime",
    alloc: 10,
    sharpe: 0.76,
    idea: "VIX regime detection re-weights the book"
  }],
  equityCurve: [100, 101.2, 100.6, 102.4, 103.9, 103.1, 105.6, 107.2, 106.4, 108.9, 110.3, 109.1, 111.8, 113.4, 112.6, 115.2, 117.9, 116.4, 119.1, 121.8, 120.4, 123.2, 124.8, 126.1],
  benchCurve: [100, 100.4, 100.9, 101.2, 101.0, 101.8, 102.3, 102.0, 102.9, 103.6, 103.2, 104.1, 104.8, 104.5, 105.4, 106.1, 105.7, 106.8, 107.5, 107.1, 108.0, 108.6, 108.2, 109.0]
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/data.js", error: String((e && e.message) || e) }); }

// ui_kits/web/kit.jsx
try { (() => {
/* Quantify UI kit — shared chrome (icons, sidebar, topbar, sparkline).
   DS primitives (Button, Card, Badge, …) come from the compiled bundle
   via window.QuantifyDesignSystem_90f900. These are kit-only composites. */

const {
  useEffect,
  useRef,
  useState
} = React;

// ── Lucide icon (CDN UMD via data-lucide + createIcons) ──────────────
function Icon({
  name,
  size = 18,
  color = "currentColor",
  strokeWidth = 2,
  style = {}
}) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && window.lucide) {
      ref.current.innerHTML = "";
      const el = document.createElement("i");
      el.setAttribute("data-lucide", name);
      ref.current.appendChild(el);
      try {
        window.lucide.createIcons({
          attrs: {
            width: size,
            height: size,
            "stroke-width": strokeWidth
          },
          nameAttr: "data-lucide"
        });
      } catch (e) {}
    }
  }, [name, size, strokeWidth]);
  return /*#__PURE__*/React.createElement("span", {
    ref: ref,
    style: {
      display: "inline-flex",
      color,
      width: size,
      height: size,
      ...style
    }
  });
}

// ── Sparkline (equity vs benchmark) ──────────────────────────────────
function Sparkline({
  data,
  bench,
  width = 520,
  height = 120,
  stroke = "var(--color-accent)"
}) {
  const all = bench ? data.concat(bench) : data;
  const min = Math.min(...all),
    max = Math.max(...all);
  const x = (i, arr) => i / (arr.length - 1) * width;
  const y = v => height - (v - min) / (max - min || 1) * (height - 8) - 4;
  const path = arr => arr.map((v, i) => `${i ? "L" : "M"}${x(i, arr).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${path(data)} L${width},${height} L0,${height} Z`;
  return /*#__PURE__*/React.createElement("svg", {
    width: "100%",
    viewBox: `0 0 ${width} ${height}`,
    preserveAspectRatio: "none",
    style: {
      display: "block"
    }
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("linearGradient", {
    id: "qkfill",
    x1: "0",
    y1: "0",
    x2: "0",
    y2: "1"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0%",
    stopColor: "var(--color-accent)",
    stopOpacity: "0.22"
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "100%",
    stopColor: "var(--color-accent)",
    stopOpacity: "0"
  }))), /*#__PURE__*/React.createElement("path", {
    d: area,
    fill: "url(#qkfill)"
  }), bench && /*#__PURE__*/React.createElement("path", {
    d: path(bench),
    fill: "none",
    stroke: "var(--color-text-muted)",
    strokeWidth: "1.5",
    strokeDasharray: "4 4",
    opacity: "0.6"
  }), /*#__PURE__*/React.createElement("path", {
    d: path(data),
    fill: "none",
    stroke: stroke,
    strokeWidth: "2.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }));
}

// ── Sidebar ──────────────────────────────────────────────────────────
function Sidebar({
  active,
  onNav
}) {
  const groups = [{
    label: "Main",
    items: [{
      id: "dashboard",
      label: "Dashboard",
      icon: "layout-dashboard"
    }, {
      id: "predict",
      label: "Predict",
      icon: "activity"
    }]
  }, {
    label: "Research",
    items: [{
      id: "backtest",
      label: "Backtest",
      icon: "bar-chart-2"
    }, {
      id: "strategies",
      label: "Strategies",
      icon: "layers"
    }]
  }];
  const Item = ({
    it
  }) => {
    const on = active === it.id;
    return /*#__PURE__*/React.createElement("button", {
      onClick: () => onNav(it.id),
      style: {
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "9px 12px",
        width: "100%",
        borderRadius: "var(--radius-md)",
        border: "none",
        cursor: "pointer",
        fontSize: 14,
        fontFamily: "var(--font-sans)",
        background: on ? "var(--color-accent-subtle)" : "transparent",
        color: on ? "var(--color-accent)" : "var(--color-text-secondary)",
        fontWeight: on ? 600 : 500,
        transition: "background var(--duration-fast) var(--ease-standard)"
      },
      onMouseEnter: e => {
        if (!on) e.currentTarget.style.background = "var(--color-surface-raised)";
      },
      onMouseLeave: e => {
        if (!on) e.currentTarget.style.background = "transparent";
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: it.icon,
      size: 17
    }), " ", it.label);
  };
  return /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 240,
      flexShrink: 0,
      background: "var(--color-surface)",
      borderRight: "1px solid var(--color-border)",
      display: "flex",
      flexDirection: "column",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "16px 18px",
      display: "flex",
      alignItems: "center",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      width: 56,
      height: 56,
      borderRadius: "50%",
      background: "radial-gradient(circle, rgba(47,141,186,0.38), rgba(47,141,186,0) 70%)"
    }
  }), /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-emblem.png",
    height: "34",
    alt: "Quantify",
    style: {
      display: "block",
      position: "relative"
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 14,
      fontWeight: 600,
      color: "var(--color-text-primary)"
    }
  }, "Quantify"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--color-text-muted)"
    }
  }, "ML Trading"))), /*#__PURE__*/React.createElement("nav", {
    style: {
      padding: "8px 12px",
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, groups.map(g => /*#__PURE__*/React.createElement("div", {
    key: g.label
  }, /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "0 0 4px",
      padding: "0 12px",
      fontSize: 10,
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: "0.16em",
      color: "var(--color-text-muted)"
    }
  }, g.label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 2
    }
  }, g.items.map(it => /*#__PURE__*/React.createElement(Item, {
    key: it.id,
    it: it
  }))))))), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "12px",
      borderTop: "1px solid var(--color-border)"
    }
  }, /*#__PURE__*/React.createElement(Item, {
    it: {
      id: "account",
      label: "Account",
      icon: "user-circle"
    }
  })));
}

// ── Topbar ───────────────────────────────────────────────────────────
function Topbar({
  title,
  onLogout
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      height: 56,
      flexShrink: 0,
      padding: "0 24px",
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      background: "color-mix(in srgb, var(--color-surface) 80%, transparent)",
      backdropFilter: "blur(8px)",
      borderBottom: "1px solid var(--color-border)",
      position: "sticky",
      top: 0,
      zIndex: 10
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      margin: 0,
      fontSize: 15,
      fontWeight: 600,
      color: "var(--color-text-primary)"
    }
  }, title), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      fontSize: 12,
      color: "var(--color-success)",
      fontWeight: 600
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: "var(--color-success)"
    }
  }), " Live + Paper"), /*#__PURE__*/React.createElement("button", {
    title: "Notifications",
    style: {
      background: "transparent",
      border: "none",
      cursor: "pointer",
      color: "var(--color-text-secondary)",
      display: "inline-flex",
      padding: 6,
      borderRadius: "var(--radius-md)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bell",
    size: 18
  })), /*#__PURE__*/React.createElement("button", {
    onClick: onLogout,
    title: "Account",
    style: {
      width: 34,
      height: 34,
      borderRadius: "50%",
      background: "var(--color-surface-raised)",
      border: "1px solid var(--color-border)",
      cursor: "pointer",
      color: "var(--color-text-secondary)",
      fontWeight: 600,
      fontSize: 13
    }
  }, "U")));
}
Object.assign(window, {
  Icon,
  Sparkline,
  Sidebar,
  Topbar
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/kit.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web/screens.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Quantify UI kit — screens. Composes DS bundle primitives + kit chrome. */
const DS = window.QuantifyDesignSystem_90f900;
const {
  Button,
  Badge,
  Card,
  CardHeader,
  CardContent,
  CardFooter,
  Input,
  StatCard,
  Alert,
  PredictionRow,
  DriverPill
} = DS;
const {
  Icon,
  Sparkline,
  Sidebar,
  Topbar
} = window;
const {
  useState
} = React;
const Q = window.QKIT;
const money = v => "$" + Math.abs(v).toLocaleString("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});
const pct = v => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)}%`;
const overline = {
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.22em",
  color: "var(--color-accent)"
};

// ── Login ────────────────────────────────────────────────────────────
function LoginScreen({
  onLogin
}) {
  const [show, setShow] = useState(false);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: "100%",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      top: 40,
      left: "50%",
      transform: "translateX(-50%)",
      width: 560,
      height: 360,
      background: "var(--color-accent)",
      opacity: 0.14,
      filter: "blur(120px)",
      borderRadius: "50%",
      pointerEvents: "none"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      width: "100%",
      maxWidth: 400
    }
  }, /*#__PURE__*/React.createElement(Card, {
    style: {
      padding: 32
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "center",
      marginBottom: 22
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      alignItems: "center",
      justifyContent: "center"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      width: 130,
      height: 130,
      borderRadius: "50%",
      background: "radial-gradient(circle, rgba(47,141,186,0.32), rgba(47,141,186,0) 70%)"
    }
  }), /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-emblem.png",
    height: "76",
    alt: "Quantify",
    style: {
      display: "block",
      position: "relative"
    }
  }))), /*#__PURE__*/React.createElement("h1", {
    style: {
      margin: 0,
      textAlign: "center",
      fontSize: 24,
      fontWeight: 800,
      color: "var(--color-text-primary)",
      letterSpacing: "-0.02em"
    }
  }, "Welcome back"), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "6px 0 26px",
      textAlign: "center",
      fontSize: 14,
      color: "var(--color-text-muted)"
    }
  }, "Log in to your trading home"), /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      onLogin();
    },
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Username",
    placeholder: "Enter your username",
    defaultValue: "tushar"
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Password",
    type: show ? "text" : "password",
    placeholder: "Enter your password",
    defaultValue: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022",
    hint: show ? "Showing password" : "Click Log In to continue"
  }), /*#__PURE__*/React.createElement(Button, {
    type: "submit",
    size: "lg",
    style: {
      width: "100%",
      marginTop: 4
    }
  }, "Log In")), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "18px 0 0",
      textAlign: "center",
      fontSize: 13,
      color: "var(--color-text-muted)"
    }
  }, "No account? ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--color-accent)",
      fontWeight: 500,
      cursor: "pointer"
    }
  }, "Sign up free")))));
}

// ── Trade / position card ────────────────────────────────────────────
function PositionCard({
  t
}) {
  const pnlAbs = (t.current - t.buy_price) * t.shares;
  const pnlPct = (t.current - t.buy_price) / t.buy_price;
  const gain = pnlAbs >= 0;
  const col = gain ? "var(--color-success)" : "var(--color-danger)";
  return /*#__PURE__*/React.createElement(Card, {
    variant: "compact",
    style: {
      position: "relative",
      overflow: "hidden",
      padding: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      height: 2,
      background: t.alert ? "var(--color-danger)" : col
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "flex-start"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 17,
      fontWeight: 800,
      color: "var(--color-text-primary)"
    }
  }, t.symbol), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 13,
      color: "var(--color-text-secondary)"
    }
  }, money(t.current)), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      fontWeight: 700,
      color: col
    }
  }, pct(pnlPct * 100))), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: "var(--color-text-muted)",
      marginTop: 2
    }
  }, t.shares, " shares @ ", money(t.buy_price))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      alignItems: "flex-end",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 14,
      fontWeight: 700,
      color: col
    }
  }, gain ? "+" : "−", money(pnlAbs)), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "xs"
  }, "Close"))), t.alert && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12
    }
  }, /*#__PURE__*/React.createElement(Alert, {
    variant: "danger"
  }, t.alert)), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 12,
      paddingTop: 12,
      borderTop: "1px solid var(--color-border)",
      display: "grid",
      gridTemplateColumns: "repeat(4,1fr)",
      gap: 6,
      fontSize: 10,
      textTransform: "uppercase",
      letterSpacing: "0.06em",
      color: "var(--color-text-muted)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "In ", t.in), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "center"
    }
  }, "Hold ", t.hold_days, "d"), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "center"
    }
  }, "Dip ", (t.dip * 100).toFixed(0), "%"), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "right",
      color: "var(--color-success)"
    }
  }, "Out ", t.out))));
}

// ── Dashboard ────────────────────────────────────────────────────────
function DashboardScreen({
  onPrefill
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(4,1fr)",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(StatCard, {
    label: "Portfolio Value",
    value: "$128,406",
    change: 3.1
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Open P&L",
    value: "+$1,842",
    change: 1.4,
    changeLabel: "today"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Sharpe (ML)",
    value: "1.84",
    change: 6.2,
    changeLabel: "vs benchmark"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Open Positions",
    value: "2"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.5fr 1fr",
      gap: 20,
      alignItems: "start"
    }
  }, /*#__PURE__*/React.createElement(Card, {
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(CardHeader, {
    title: "Today's ML Picks",
    subtitle: "5-day horizon \xB7 ensemble committee",
    actions: /*#__PURE__*/React.createElement(Badge, {
      variant: "accent"
    }, "LightGBM \xB7 XGB \xB7 CatBoost")
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "40px 1fr auto auto",
      gap: 16,
      padding: "9px 18px",
      fontSize: 10,
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: "0.08em",
      color: "var(--color-text-muted)",
      borderBottom: "1px solid var(--color-border)",
      background: "var(--color-surface-raised)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "Rank"), /*#__PURE__*/React.createElement("span", null, "Symbol"), /*#__PURE__*/React.createElement("span", null, "Signal"), /*#__PURE__*/React.createElement("span", {
    style: {
      textAlign: "right"
    }
  }, "Strength")), Q.predictions.map(p => /*#__PURE__*/React.createElement(PredictionRow, _extends({
    key: p.symbol
  }, p, {
    onClick: () => onPrefill(p.symbol)
  }))), /*#__PURE__*/React.createElement(CardFooter, {
    style: {
      justifyContent: "flex-start"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "info",
    size: 13,
    color: "var(--color-text-muted)"
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 12,
      color: "var(--color-text-muted)"
    }
  }, "Click any row to pre-fill the trade form \xB7 predictions, not advice."))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "shield",
    size: 18,
    color: "var(--color-accent)"
  }), /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontSize: 16,
      fontWeight: 700,
      color: "var(--color-text-primary)"
    }
  }, "Active Portfolio")), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "sm",
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "refresh-cw",
      size: 13
    })
  }, "Refresh")), Q.trades.map(t => /*#__PURE__*/React.createElement(PositionCard, {
    key: t.id,
    t: t
  })), /*#__PURE__*/React.createElement(LogTradeCard, {
    prefill: onPrefill.value
  }))));
}
function LogTradeCard() {
  const [symbol, setSymbol] = useState("");
  const [done, setDone] = useState(false);
  return /*#__PURE__*/React.createElement(Card, {
    variant: "compact"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      marginBottom: 14,
      color: "var(--color-accent)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "plus",
    size: 15
  }), " ", /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 11,
      fontWeight: 700,
      textTransform: "uppercase",
      letterSpacing: "0.08em"
    }
  }, "Log a new trade")), /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      setDone(true);
    },
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.2fr 1fr 1fr",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Symbol",
    placeholder: "AAPL",
    value: symbol,
    onChange: e => {
      setSymbol(e.target.value.toUpperCase());
      setDone(false);
    }
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Shares",
    placeholder: "10"
  }), /*#__PURE__*/React.createElement(Input, {
    label: "Buy",
    prefix: "$",
    placeholder: "150"
  })), done ? /*#__PURE__*/React.createElement(Alert, {
    variant: "success",
    title: "Trade logged"
  }, "Telegram alert activated if connected.") : /*#__PURE__*/React.createElement(Button, {
    type: "submit",
    style: {
      width: "100%"
    }
  }, "Log Trade & Activate Alerts")));
}

// ── Predict ──────────────────────────────────────────────────────────
function PredictScreen() {
  const [query, setQuery] = useState("");
  const top = Q.predictions.filter(p => p.side === "long").slice(0, 3);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 20
    }
  }, /*#__PURE__*/React.createElement(Card, {
    variant: "compact",
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    style: {
      ...overline,
      margin: 0
    }
  }, "Ad-hoc prediction"), /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: "6px 0 0",
      fontSize: 18,
      fontWeight: 700,
      color: "var(--color-text-primary)"
    }
  }, "Run the ML ensemble on any ticker")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10,
      alignItems: "flex-end"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Symbol",
    placeholder: "e.g. GME",
    prefix: "",
    value: query,
    onChange: e => setQuery(e.target.value.toUpperCase())
  })), /*#__PURE__*/React.createElement(Button, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "sparkles",
      size: 15
    })
  }, "Predict")), /*#__PURE__*/React.createElement(Alert, {
    variant: "info"
  }, "Fetches 3y of daily prices, computes features, runs the pre-trained ensemble. Cached 4h.")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    style: {
      ...overline,
      marginBottom: 10
    }
  }, "Top conviction \xB7 long"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 14
    }
  }, top.map((p, i) => /*#__PURE__*/React.createElement(Card, {
    key: p.symbol,
    variant: "compact",
    interactive: true,
    style: {
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: "absolute",
      top: -40,
      right: -30,
      width: 110,
      height: 110,
      borderRadius: "50%",
      background: "var(--color-accent)",
      opacity: 0.1,
      filter: "blur(30px)"
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10,
      textTransform: "uppercase",
      letterSpacing: "0.1em",
      color: "var(--color-text-muted)"
    }
  }, "Rank ", String(i + 1).padStart(2, "0")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginTop: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 20,
      fontWeight: 800,
      color: "var(--color-text-primary)"
    }
  }, p.symbol), /*#__PURE__*/React.createElement(Badge, {
    variant: "success"
  }, "LONG")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--color-success)",
      marginTop: 8
    }
  }, pct(p.predictedReturnPct), " 1d"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexWrap: "wrap",
      gap: 6,
      marginTop: 12
    }
  }, p.drivers.slice(0, 2).map((d, j) => /*#__PURE__*/React.createElement(DriverPill, _extends({
    key: j
  }, d)))))))), /*#__PURE__*/React.createElement(Card, {
    style: {
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(CardHeader, {
    title: "All signals",
    subtitle: "Ranked by model strength",
    actions: /*#__PURE__*/React.createElement(Badge, {
      variant: "info"
    }, "S&P 500 cache")
  }), Q.predictions.map(p => /*#__PURE__*/React.createElement(PredictionRow, _extends({
    key: p.symbol
  }, p, {
    onClick: () => {}
  })))));
}

// ── Backtest ─────────────────────────────────────────────────────────
function BacktestScreen() {
  const [strategy, setStrategy] = useState("ML Return Predictor");
  const [ran, setRan] = useState(true);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "320px 1fr",
      gap: 20,
      alignItems: "start"
    }
  }, /*#__PURE__*/React.createElement(Card, {
    variant: "compact",
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
    style: {
      ...overline,
      margin: 0
    }
  }, "Configure"), /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: "6px 0 0",
      fontSize: 17,
      fontWeight: 700,
      color: "var(--color-text-primary)"
    }
  }, "Backtest Lab")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 13,
      fontWeight: 500,
      color: "var(--color-text-primary)"
    }
  }, "Strategy"), Q.strategies.map(s => /*#__PURE__*/React.createElement("button", {
    key: s.name,
    onClick: () => {
      setStrategy(s.name);
      setRan(false);
    },
    style: {
      textAlign: "left",
      padding: "9px 12px",
      borderRadius: "var(--radius-md)",
      cursor: "pointer",
      fontSize: 13,
      border: `1px solid ${strategy === s.name ? "var(--color-accent)" : "var(--color-border)"}`,
      background: strategy === s.name ? "var(--color-accent-subtle)" : "var(--color-surface-raised)",
      color: strategy === s.name ? "var(--color-accent)" : "var(--color-text-secondary)",
      fontWeight: strategy === s.name ? 600 : 500
    }
  }, s.name))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "Start",
    defaultValue: "2022-01-01"
  }), /*#__PURE__*/React.createElement(Input, {
    label: "End",
    defaultValue: "2024-01-01"
  })), /*#__PURE__*/React.createElement(Input, {
    label: "Capital",
    prefix: "$",
    defaultValue: "100,000"
  }), /*#__PURE__*/React.createElement(Button, {
    onClick: () => setRan(true),
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "play",
      size: 14
    })
  }, "Run Backtest")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(4,1fr)",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement(StatCard, {
    label: "Total Return",
    value: "+26.1%",
    change: 26.1
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Sharpe",
    value: "1.84"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Max Drawdown",
    value: "\u22128.4%"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Win Rate",
    value: "58%"
  })), /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement(CardHeader, {
    title: `Equity curve — ${strategy}`,
    subtitle: "Strategy vs SPY benchmark",
    actions: ran ? /*#__PURE__*/React.createElement(Badge, {
      variant: "success"
    }, "Complete") : /*#__PURE__*/React.createElement(Badge, {
      variant: "warning"
    }, "Stale")
  }), /*#__PURE__*/React.createElement(CardContent, null, /*#__PURE__*/React.createElement(Sparkline, {
    data: Q.equityCurve,
    bench: Q.benchCurve
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 18,
      marginTop: 12,
      fontSize: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      color: "var(--color-text-secondary)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 14,
      height: 2,
      background: "var(--color-accent)",
      borderRadius: 2
    }
  }), " ", strategy), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      color: "var(--color-text-muted)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 14,
      height: 0,
      borderTop: "2px dashed var(--color-text-muted)"
    }
  }), " SPY"))))));
}

// ── Strategies ───────────────────────────────────────────────────────
function StrategiesScreen() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(2,1fr)",
      gap: 14
    }
  }, Q.strategies.map(s => /*#__PURE__*/React.createElement(Card, {
    key: s.name,
    variant: "compact",
    interactive: true
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "flex-start",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      fontSize: 16,
      fontWeight: 700,
      color: "var(--color-text-primary)"
    }
  }, s.name), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "6px 0 0",
      fontSize: 13,
      color: "var(--color-text-muted)",
      maxWidth: 320
    }
  }, s.idea)), /*#__PURE__*/React.createElement(Badge, {
    variant: "accent"
  }, s.alloc, "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 14,
      display: "flex",
      alignItems: "center",
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      height: 6,
      borderRadius: 999,
      background: "var(--color-surface-raised)",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${s.alloc * 4}%`,
      maxWidth: "100%",
      height: "100%",
      background: "var(--color-accent)",
      borderRadius: 999
    }
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: 12,
      color: "var(--color-success)"
    }
  }, "Sharpe ", s.sharpe)))));
}

// ── App shell ────────────────────────────────────────────────────────
function App() {
  const [authed, setAuthed] = useState(false);
  const [route, setRoute] = useState("dashboard");
  const [prefill, setPrefill] = useState("");
  const titles = {
    dashboard: "Dashboard",
    predict: "Predict",
    backtest: "Backtest",
    strategies: "Strategies",
    account: "Account"
  };
  if (!authed) return /*#__PURE__*/React.createElement(LoginScreen, {
    onLogin: () => setAuthed(true)
  });
  const prefillFn = s => {
    setPrefill(s);
    setRoute("dashboard");
  };
  prefillFn.value = prefill;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: "100vh",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(Sidebar, {
    active: route,
    onNav: setRoute
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      minWidth: 0,
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement(Topbar, {
    title: titles[route],
    onLogout: () => setAuthed(false)
  }), /*#__PURE__*/React.createElement("main", {
    style: {
      flex: 1,
      overflow: "auto",
      padding: 24
    }
  }, route === "dashboard" && /*#__PURE__*/React.createElement(DashboardScreen, {
    onPrefill: prefillFn
  }), route === "predict" && /*#__PURE__*/React.createElement(PredictScreen, null), route === "backtest" && /*#__PURE__*/React.createElement(BacktestScreen, null), route === "strategies" && /*#__PURE__*/React.createElement(StrategiesScreen, null), route === "account" && /*#__PURE__*/React.createElement("div", {
    style: {
      color: "var(--color-text-muted)",
      fontSize: 14
    }
  }, "Account settings \u2014 Telegram username linking, risk presets, theme."))));
}
ReactDOM.createRoot(document.getElementById("root")).render(/*#__PURE__*/React.createElement(App, null));
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web/screens.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.CardHeader = __ds_scope.CardHeader;

__ds_ns.CardContent = __ds_scope.CardContent;

__ds_ns.CardFooter = __ds_scope.CardFooter;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.DriverPill = __ds_scope.DriverPill;

__ds_ns.PredictionRow = __ds_scope.PredictionRow;

__ds_ns.Alert = __ds_scope.Alert;

})();
