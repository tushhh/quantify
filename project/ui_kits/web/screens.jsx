/* Quantify UI kit — screens. Composes DS bundle primitives + kit chrome. */
const DS = window.QuantifyDesignSystem_90f900;
const { Button, Badge, Card, CardHeader, CardContent, CardFooter, Input, StatCard, Alert, PredictionRow, DriverPill } = DS;
const { Icon, Sparkline, Sidebar, Topbar } = window;
const { useState } = React;
const Q = window.QKIT;

const money = (v) => "$" + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)}%`;
const overline = { fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.22em", color: "var(--color-accent)" };

// ── Login ────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ minHeight: "100%", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", top: 40, left: "50%", transform: "translateX(-50%)", width: 560, height: 360, background: "var(--color-accent)", opacity: 0.14, filter: "blur(120px)", borderRadius: "50%", pointerEvents: "none" }} />
      <div style={{ position: "relative", width: "100%", maxWidth: 400 }}>
        <Card style={{ padding: 32 }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 22 }}>
            <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <div style={{ position: "absolute", width: 130, height: 130, borderRadius: "50%", background: "radial-gradient(circle, rgba(47,141,186,0.32), rgba(47,141,186,0) 70%)" }} />
              <img src="../../assets/logo-emblem.png" height="76" alt="Quantify" style={{ display: "block", position: "relative" }} />
            </div>
          </div>
          <h1 style={{ margin: 0, textAlign: "center", fontSize: 24, fontWeight: 800, color: "var(--color-text-primary)", letterSpacing: "-0.02em" }}>Welcome back</h1>
          <p style={{ margin: "6px 0 26px", textAlign: "center", fontSize: 14, color: "var(--color-text-muted)" }}>Log in to your trading home</p>
          <form onSubmit={(e) => { e.preventDefault(); onLogin(); }} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Input label="Username" placeholder="Enter your username" defaultValue="tushar" />
            <Input label="Password" type={show ? "text" : "password"} placeholder="Enter your password" defaultValue="••••••••" hint={show ? "Showing password" : "Click Log In to continue"} />
            <Button type="submit" size="lg" style={{ width: "100%", marginTop: 4 }}>Log In</Button>
          </form>
          <p style={{ margin: "18px 0 0", textAlign: "center", fontSize: 13, color: "var(--color-text-muted)" }}>
            No account? <span style={{ color: "var(--color-accent)", fontWeight: 500, cursor: "pointer" }}>Sign up free</span>
          </p>
        </Card>
      </div>
    </div>
  );
}

// ── Trade / position card ────────────────────────────────────────────
function PositionCard({ t }) {
  const pnlAbs = (t.current - t.buy_price) * t.shares;
  const pnlPct = (t.current - t.buy_price) / t.buy_price;
  const gain = pnlAbs >= 0;
  const col = gain ? "var(--color-success)" : "var(--color-danger)";
  return (
    <Card variant="compact" style={{ position: "relative", overflow: "hidden", padding: 0 }}>
      <div style={{ height: 2, background: t.alert ? "var(--color-danger)" : col }} />
      <div style={{ padding: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontSize: 17, fontWeight: 800, color: "var(--color-text-primary)" }}>{t.symbol}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--color-text-secondary)" }}>{money(t.current)}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, fontWeight: 700, color: col }}>{pct(pnlPct * 100)}</span>
            </div>
            <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>{t.shares} shares @ {money(t.buy_price)}</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 700, color: col }}>{gain ? "+" : "−"}{money(pnlAbs)}</span>
            <Button variant="ghost" size="xs">Close</Button>
          </div>
        </div>
        {t.alert && <div style={{ marginTop: 12 }}><Alert variant="danger">{t.alert}</Alert></div>}
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--color-border)", display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 6, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--color-text-muted)" }}>
          <span>In {t.in}</span>
          <span style={{ textAlign: "center" }}>Hold {t.hold_days}d</span>
          <span style={{ textAlign: "center" }}>Dip {(t.dip * 100).toFixed(0)}%</span>
          <span style={{ textAlign: "right", color: "var(--color-success)" }}>Out {t.out}</span>
        </div>
      </div>
    </Card>
  );
}

// ── Dashboard ────────────────────────────────────────────────────────
function DashboardScreen({ onPrefill }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
        <StatCard label="Portfolio Value" value="$128,406" change={3.1} />
        <StatCard label="Open P&L" value="+$1,842" change={1.4} changeLabel="today" />
        <StatCard label="Sharpe (ML)" value="1.84" change={6.2} changeLabel="vs benchmark" />
        <StatCard label="Open Positions" value="2" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 20, alignItems: "start" }}>
        {/* Today's picks */}
        <Card style={{ overflow: "hidden" }}>
          <CardHeader title="Today's ML Picks" subtitle="5-day horizon · ensemble committee"
            actions={<Badge variant="accent">LightGBM · XGB · CatBoost</Badge>} />
          <div style={{ display: "grid", gridTemplateColumns: "40px 1fr auto auto", gap: 16, padding: "9px 18px", fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--color-text-muted)", borderBottom: "1px solid var(--color-border)", background: "var(--color-surface-raised)" }}>
            <span>Rank</span><span>Symbol</span><span>Signal</span><span style={{ textAlign: "right" }}>Strength</span>
          </div>
          {Q.predictions.map((p) => <PredictionRow key={p.symbol} {...p} onClick={() => onPrefill(p.symbol)} />)}
          <CardFooter style={{ justifyContent: "flex-start" }}>
            <Icon name="info" size={13} color="var(--color-text-muted)" />
            <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>Click any row to pre-fill the trade form · predictions, not advice.</span>
          </CardFooter>
        </Card>

        {/* Portfolio */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="shield" size={18} color="var(--color-accent)" />
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)" }}>Active Portfolio</h3>
            </div>
            <Button variant="ghost" size="sm" icon={<Icon name="refresh-cw" size={13} />}>Refresh</Button>
          </div>
          {Q.trades.map((t) => <PositionCard key={t.id} t={t} />)}
          <LogTradeCard prefill={onPrefill.value} />
        </div>
      </div>
    </div>
  );
}

function LogTradeCard() {
  const [symbol, setSymbol] = useState("");
  const [done, setDone] = useState(false);
  return (
    <Card variant="compact">
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, color: "var(--color-accent)" }}>
        <Icon name="plus" size={15} /> <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>Log a new trade</span>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); setDone(true); }} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: 8 }}>
          <Input label="Symbol" placeholder="AAPL" value={symbol} onChange={(e) => { setSymbol(e.target.value.toUpperCase()); setDone(false); }} />
          <Input label="Shares" placeholder="10" />
          <Input label="Buy" prefix="$" placeholder="150" />
        </div>
        {done
          ? <Alert variant="success" title="Trade logged">Telegram alert activated if connected.</Alert>
          : <Button type="submit" style={{ width: "100%" }}>Log Trade &amp; Activate Alerts</Button>}
      </form>
    </Card>
  );
}

// ── Predict ──────────────────────────────────────────────────────────
function PredictScreen() {
  const [query, setQuery] = useState("");
  const top = Q.predictions.filter((p) => p.side === "long").slice(0, 3);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Card variant="compact" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div>
          <p style={{ ...overline, margin: 0 }}>Ad-hoc prediction</p>
          <h3 style={{ margin: "6px 0 0", fontSize: 18, fontWeight: 700, color: "var(--color-text-primary)" }}>Run the ML ensemble on any ticker</h3>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}><Input label="Symbol" placeholder="e.g. GME" prefix="" value={query} onChange={(e) => setQuery(e.target.value.toUpperCase())} /></div>
          <Button icon={<Icon name="sparkles" size={15} />}>Predict</Button>
        </div>
        <Alert variant="info">Fetches 3y of daily prices, computes features, runs the pre-trained ensemble. Cached 4h.</Alert>
      </Card>

      <div>
        <p style={{ ...overline, marginBottom: 10 }}>Top conviction · long</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
          {top.map((p, i) => (
            <Card key={p.symbol} variant="compact" interactive style={{ position: "relative", overflow: "hidden" }}>
              <div style={{ position: "absolute", top: -40, right: -30, width: 110, height: 110, borderRadius: "50%", background: "var(--color-accent)", opacity: 0.1, filter: "blur(30px)" }} />
              <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--color-text-muted)" }}>Rank {String(i + 1).padStart(2, "0")}</div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                <span style={{ fontSize: 20, fontWeight: 800, color: "var(--color-text-primary)" }}>{p.symbol}</span>
                <Badge variant="success">LONG</Badge>
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-success)", marginTop: 8 }}>{pct(p.predictedReturnPct)} 1d</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 12 }}>
                {p.drivers.slice(0, 2).map((d, j) => <DriverPill key={j} {...d} />)}
              </div>
            </Card>
          ))}
        </div>
      </div>

      <Card style={{ overflow: "hidden" }}>
        <CardHeader title="All signals" subtitle="Ranked by model strength" actions={<Badge variant="info">S&amp;P 500 cache</Badge>} />
        {Q.predictions.map((p) => <PredictionRow key={p.symbol} {...p} onClick={() => {}} />)}
      </Card>
    </div>
  );
}

// ── Backtest ─────────────────────────────────────────────────────────
function BacktestScreen() {
  const [strategy, setStrategy] = useState("ML Return Predictor");
  const [ran, setRan] = useState(true);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 20, alignItems: "start" }}>
      <Card variant="compact" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <p style={{ ...overline, margin: 0 }}>Configure</p>
          <h3 style={{ margin: "6px 0 0", fontSize: 17, fontWeight: 700, color: "var(--color-text-primary)" }}>Backtest Lab</h3>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)" }}>Strategy</span>
          {Q.strategies.map((s) => (
            <button key={s.name} onClick={() => { setStrategy(s.name); setRan(false); }} style={{
              textAlign: "left", padding: "9px 12px", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: 13,
              border: `1px solid ${strategy === s.name ? "var(--color-accent)" : "var(--color-border)"}`,
              background: strategy === s.name ? "var(--color-accent-subtle)" : "var(--color-surface-raised)",
              color: strategy === s.name ? "var(--color-accent)" : "var(--color-text-secondary)", fontWeight: strategy === s.name ? 600 : 500,
            }}>{s.name}</button>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <Input label="Start" defaultValue="2022-01-01" />
          <Input label="End" defaultValue="2024-01-01" />
        </div>
        <Input label="Capital" prefix="$" defaultValue="100,000" />
        <Button onClick={() => setRan(true)} icon={<Icon name="play" size={14} />}>Run Backtest</Button>
      </Card>

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
          <StatCard label="Total Return" value="+26.1%" change={26.1} />
          <StatCard label="Sharpe" value="1.84" />
          <StatCard label="Max Drawdown" value="−8.4%" />
          <StatCard label="Win Rate" value="58%" />
        </div>
        <Card>
          <CardHeader title={`Equity curve — ${strategy}`} subtitle="Strategy vs SPY benchmark"
            actions={ran ? <Badge variant="success">Complete</Badge> : <Badge variant="warning">Stale</Badge>} />
          <CardContent>
            <Sparkline data={Q.equityCurve} bench={Q.benchCurve} />
            <div style={{ display: "flex", gap: 18, marginTop: 12, fontSize: 12 }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--color-text-secondary)" }}><span style={{ width: 14, height: 2, background: "var(--color-accent)", borderRadius: 2 }} /> {strategy}</span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--color-text-muted)" }}><span style={{ width: 14, height: 0, borderTop: "2px dashed var(--color-text-muted)" }} /> SPY</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ── Strategies ───────────────────────────────────────────────────────
function StrategiesScreen() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2,1fr)", gap: 14 }}>
      {Q.strategies.map((s) => (
        <Card key={s.name} variant="compact" interactive>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)" }}>{s.name}</h3>
              <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--color-text-muted)", maxWidth: 320 }}>{s.idea}</p>
            </div>
            <Badge variant="accent">{s.alloc}%</Badge>
          </div>
          <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ flex: 1, height: 6, borderRadius: 999, background: "var(--color-surface-raised)", overflow: "hidden" }}>
              <div style={{ width: `${s.alloc * 4}%`, maxWidth: "100%", height: "100%", background: "var(--color-accent)", borderRadius: 999 }} />
            </div>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-success)" }}>Sharpe {s.sharpe}</span>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── App shell ────────────────────────────────────────────────────────
function App() {
  const [authed, setAuthed] = useState(false);
  const [route, setRoute] = useState("dashboard");
  const [prefill, setPrefill] = useState("");
  const titles = { dashboard: "Dashboard", predict: "Predict", backtest: "Backtest", strategies: "Strategies", account: "Account" };

  if (!authed) return <LoginScreen onLogin={() => setAuthed(true)} />;

  const prefillFn = (s) => { setPrefill(s); setRoute("dashboard"); };
  prefillFn.value = prefill;

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar active={route} onNav={setRoute} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>
        <Topbar title={titles[route]} onLogout={() => setAuthed(false)} />
        <main style={{ flex: 1, overflow: "auto", padding: 24 }}>
          {route === "dashboard" && <DashboardScreen onPrefill={prefillFn} />}
          {route === "predict" && <PredictScreen />}
          {route === "backtest" && <BacktestScreen />}
          {route === "strategies" && <StrategiesScreen />}
          {route === "account" && <div style={{ color: "var(--color-text-muted)", fontSize: 14 }}>Account settings — Telegram username linking, risk presets, theme.</div>}
        </main>
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
