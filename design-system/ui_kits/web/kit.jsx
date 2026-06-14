/* Quantify UI kit — shared chrome (icons, sidebar, topbar, sparkline).
   DS primitives (Button, Card, Badge, …) come from the compiled bundle
   via window.QuantifyDesignSystem_90f900. These are kit-only composites. */

const { useEffect, useRef, useState } = React;

// ── Lucide icon (CDN UMD via data-lucide + createIcons) ──────────────
function Icon({ name, size = 18, color = "currentColor", strokeWidth = 2, style = {} }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && window.lucide) {
      ref.current.innerHTML = "";
      const el = document.createElement("i");
      el.setAttribute("data-lucide", name);
      ref.current.appendChild(el);
      try { window.lucide.createIcons({ attrs: { width: size, height: size, "stroke-width": strokeWidth }, nameAttr: "data-lucide" }); } catch (e) {}
    }
  }, [name, size, strokeWidth]);
  return <span ref={ref} style={{ display: "inline-flex", color, width: size, height: size, ...style }} />;
}

// ── Sparkline (equity vs benchmark) ──────────────────────────────────
function Sparkline({ data, bench, width = 520, height = 120, stroke = "var(--color-accent)" }) {
  const all = bench ? data.concat(bench) : data;
  const min = Math.min(...all), max = Math.max(...all);
  const x = (i, arr) => (i / (arr.length - 1)) * width;
  const y = (v) => height - ((v - min) / (max - min || 1)) * (height - 8) - 4;
  const path = (arr) => arr.map((v, i) => `${i ? "L" : "M"}${x(i, arr).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${path(data)} L${width},${height} L0,${height} Z`;
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ display: "block" }}>
      <defs>
        <linearGradient id="qkfill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#qkfill)" />
      {bench && <path d={path(bench)} fill="none" stroke="var(--color-text-muted)" strokeWidth="1.5" strokeDasharray="4 4" opacity="0.6" />}
      <path d={path(data)} fill="none" stroke={stroke} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Sidebar ──────────────────────────────────────────────────────────
function Sidebar({ active, onNav }) {
  const groups = [
    { label: "Main", items: [ { id: "dashboard", label: "Dashboard", icon: "layout-dashboard" }, { id: "predict", label: "Predict", icon: "activity" } ] },
    { label: "Research", items: [ { id: "backtest", label: "Backtest", icon: "bar-chart-2" }, { id: "strategies", label: "Strategies", icon: "layers" } ] },
  ];
  const Item = ({ it }) => {
    const on = active === it.id;
    return (
      <button onClick={() => onNav(it.id)} style={{
        display: "flex", alignItems: "center", gap: 12, padding: "9px 12px", width: "100%",
        borderRadius: "var(--radius-md)", border: "none", cursor: "pointer", fontSize: 14, fontFamily: "var(--font-sans)",
        background: on ? "var(--color-accent-subtle)" : "transparent",
        color: on ? "var(--color-accent)" : "var(--color-text-secondary)", fontWeight: on ? 600 : 500,
        transition: "background var(--duration-fast) var(--ease-standard)",
      }}
      onMouseEnter={(e)=>{ if(!on) e.currentTarget.style.background="var(--color-surface-raised)"; }}
      onMouseLeave={(e)=>{ if(!on) e.currentTarget.style.background="transparent"; }}>
        <Icon name={it.icon} size={17} /> {it.label}
      </button>
    );
  };
  return (
    <aside style={{ width: 240, flexShrink: 0, background: "var(--color-surface)", borderRight: "1px solid var(--color-border)", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
      <div>
        <div style={{ padding: "16px 18px", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div style={{ position: "absolute", width: 56, height: 56, borderRadius: "50%", background: "radial-gradient(circle, rgba(47,141,186,0.38), rgba(47,141,186,0) 70%)" }} />
            <img src="../../assets/logo-emblem.png" height="34" alt="Quantify" style={{ display: "block", position: "relative" }} />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--color-text-primary)" }}>Quantify</div>
            <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>ML Trading</div>
          </div>
        </div>
        <nav style={{ padding: "8px 12px", display: "flex", flexDirection: "column", gap: 16 }}>
          {groups.map((g) => (
            <div key={g.label}>
              <p style={{ margin: "0 0 4px", padding: "0 12px", fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.16em", color: "var(--color-text-muted)" }}>{g.label}</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>{g.items.map((it) => <Item key={it.id} it={it} />)}</div>
            </div>
          ))}
        </nav>
      </div>
      <div style={{ padding: "12px", borderTop: "1px solid var(--color-border)" }}>
        <Item it={{ id: "account", label: "Account", icon: "user-circle" }} />
      </div>
    </aside>
  );
}

// ── Topbar ───────────────────────────────────────────────────────────
function Topbar({ title, onLogout }) {
  return (
    <header style={{ height: 56, flexShrink: 0, padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between", background: "color-mix(in srgb, var(--color-surface) 80%, transparent)", backdropFilter: "blur(8px)", borderBottom: "1px solid var(--color-border)", position: "sticky", top: 0, zIndex: 10 }}>
      <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "var(--color-text-primary)" }}>{title}</h2>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--color-success)", fontWeight: 600 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--color-success)" }} /> Live + Paper
        </span>
        <button title="Notifications" style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--color-text-secondary)", display: "inline-flex", padding: 6, borderRadius: "var(--radius-md)" }}><Icon name="bell" size={18} /></button>
        <button onClick={onLogout} title="Account" style={{ width: 34, height: 34, borderRadius: "50%", background: "var(--color-surface-raised)", border: "1px solid var(--color-border)", cursor: "pointer", color: "var(--color-text-secondary)", fontWeight: 600, fontSize: 13 }}>U</button>
      </div>
    </header>
  );
}

Object.assign(window, { Icon, Sparkline, Sidebar, Topbar });
