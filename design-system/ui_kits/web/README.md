# Quantify Web — UI Kit

An interactive, high-fidelity recreation of the Quantify web app, composed from this design system's primitives (`window.QuantifyDesignSystem_90f900.*`) plus kit-only chrome.

## Run
Open `index.html`. It loads React 18 + Babel, Lucide (CDN), the compiled DS bundle (`../../_ds_bundle.js`), mock data (`data.js`), and the screens.

## Flow
1. **Login** — accent-glow card, then enter the app.
2. **Dashboard** — KPI stat row · "Today's ML Picks" (`PredictionRow` list, click a row to pre-fill) · Active Portfolio with position cards + log-trade form.
3. **Predict** — ad-hoc ticker prediction, top-conviction cards, full ranked signal table.
4. **Backtest** — strategy picker + params → equity curve (strategy vs SPY) and result KPIs.
5. **Strategies** — the six built-in strategies with allocation + Sharpe.

## Files
- `index.html` — shell, script loading, mount.
- `data.js` — mock universe, predictions, trades, strategies, equity curves (`window.QKIT`).
- `kit.jsx` — kit composites: `Icon` (Lucide), `Sparkline`, `Sidebar`, `Topbar`.
- `screens.jsx` — `LoginScreen`, `DashboardScreen`, `PredictScreen`, `BacktestScreen`, `StrategiesScreen`, `App`.

## Notes
- DS primitives (`Button`, `Card`, `Badge`, `Input`, `StatCard`, `Alert`, `PredictionRow`, `DriverPill`) are **not re-implemented** — they come from the bundle. Only product-specific chrome lives here.
- This is a cosmetic recreation: navigation and form submits are simulated, no network calls.
