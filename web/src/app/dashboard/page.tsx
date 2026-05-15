"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Zap, Shield, AlertTriangle, Plus, Crosshair, Send,
  LogOut, UserCircle, RefreshCw, TrendingUp, TrendingDown,
  AlertCircle, RotateCcw, Clock, DollarSign,
} from "lucide-react";
import Link from "next/link";
import { api, type AuthUser, type PredictionItem, type TrackedTrade, type TickerInfo } from "@/lib/api";
import { Card, Badge, Alert } from "@/components/ui";

function pct(v: number) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
}

function fmt$(v: number) {
  return `$${Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ── Loading state ─────────────────────────────────────────────────────────────
function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 border-2 border-blue-500/50 border-t-blue-500 rounded-full animate-spin" />
        <p className="text-slate-500 text-sm">Loading dashboard…</p>
      </div>
    </div>
  );
}

// ── Trade card ────────────────────────────────────────────────────────────────
function TradeCard({
  t,
  currentPrice,
  onClose,
}: {
  t: TrackedTrade;
  currentPrice: number | null | undefined;
  onClose: (id: number) => void;
}) {
  const pnlAbs = currentPrice != null ? (currentPrice - t.buy_price) * t.shares : null;
  const pnlPct = currentPrice != null ? (currentPrice - t.buy_price) / t.buy_price : null;
  const isGain  = pnlAbs != null && pnlAbs >= 0;
  const hasPrice = currentPrice != null;

  return (
    <div className="rounded-xl bg-[var(--surface)] border border-[var(--border)] shadow-lg relative overflow-hidden hover:border-[var(--border-bright)] transition-all group">
      {/* alert stripe */}
      {t.alert && <div className="absolute top-0 left-0 w-full h-0.5 bg-red-500 animate-pulse" />}

      {/* P&L accent stripe */}
      {!t.alert && hasPrice && (
        <div className={`absolute top-0 left-0 w-full h-0.5 ${isGain ? "bg-emerald-500" : "bg-red-500"}`} />
      )}

      <div className="p-4">
        {/* Row 1: symbol + price + close */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-lg font-black text-white tracking-tight">{t.symbol}</span>
              {hasPrice && (
                <span className="text-sm font-mono text-slate-300">{fmt$(currentPrice!)}</span>
              )}
              {pnlPct != null && (
                <span className={`flex items-center gap-0.5 text-xs font-bold tabular-nums ${isGain ? "text-emerald-400" : "text-red-400"}`}>
                  {isGain ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                  {pct(pnlPct)}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5 font-mono">
              {t.shares} shares @ {fmt$(t.buy_price)}
            </p>
          </div>

          <div className="flex flex-col items-end gap-2 shrink-0">
            {pnlAbs != null && (
              <span className={`text-sm font-bold tabular-nums ${isGain ? "text-emerald-400" : "text-red-400"}`}>
                {isGain ? "+" : "−"}{fmt$(pnlAbs)}
              </span>
            )}
            <button
              onClick={() => onClose(t.id)}
              className="text-slate-500 hover:text-red-400 bg-[var(--surface-raised)] border border-[var(--border)] hover:border-red-500/30 hover:bg-red-500/10 px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all"
            >
              Close
            </button>
          </div>
        </div>

        {/* Alert bar */}
        {t.alert && (
          <div className="mt-3 bg-red-500/10 border border-red-500/20 rounded-lg p-2.5 flex gap-2 items-start">
            <AlertTriangle className="text-red-400 shrink-0 mt-0.5" size={14} />
            <p className="text-xs text-red-300 font-medium leading-relaxed">{t.alert}</p>
          </div>
        )}

        {/* Footer metadata */}
        <div className="mt-3 pt-3 border-t border-[var(--border)] grid grid-cols-3 gap-1 text-[10px] font-mono text-slate-600 uppercase tracking-wider">
          <span>In: {new Date(t.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
          <span className="text-center">Hold: {t.hold_value ?? t.hold_days}d</span>
          <span className="text-right text-blue-500">Out: {new Date(t.sell_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);

  const [loadingPreds, setLoadingPreds] = useState(false);
  const [predictions, setPredictions] = useState<PredictionItem[]>([]);
  const [predError, setPredError] = useState<string | null>(null);
  const [trades, setTrades] = useState<TrackedTrade[]>([]);
  const [prices, setPrices] = useState<Record<string, number | null>>({});
  const [loadingPrices, setLoadingPrices] = useState(false);
  const [universe, setUniverse] = useState<TickerInfo[]>([]);

  const [newTrade, setNewTrade] = useState({ symbol: "", shares: "", buy_price: "" });
  const [tradeError, setTradeError] = useState<string | null>(null);
  const [tradeSuccess, setTradeSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [holdUnit, setHoldUnit] = useState<"days" | "months" | "years">("days");
  const [holdValue, setHoldValue] = useState("10");
  const [activeTab, setActiveTab] = useState<"analysis" | "portfolio">("analysis");
  const [symbolOpen, setSymbolOpen] = useState(false);
  const [symbolIndex, setSymbolIndex] = useState(0);

  const loadPrices = useCallback(async () => {
    setLoadingPrices(true);
    try {
      const p = await api.trades.prices();
      setPrices(p);
    } catch {
      // prices are supplemental; silently skip
    } finally {
      setLoadingPrices(false);
    }
  }, []);

  const loadTrades = useCallback(async () => {
    try {
      const data = await api.trades.list();
      const active = data.filter((t) => t.status === "active");
      setTrades(active);
      if (active.length > 0) loadPrices();
    } catch (err) {
      console.error(err);
    }
  }, [loadPrices]);

  useEffect(() => {
    const check = async () => {
      try {
        const u = await api.auth.me();
        setUser(u);
        loadTrades().catch(console.error);
      } catch {
        router.push("/login");
      } finally {
        setLoadingAuth(false);
      }
    };
    void check();
  }, [router, loadTrades]);

  useEffect(() => {
    api.universe.get()
      .then((r) => setUniverse(r.tickers))
      .catch(console.error);
  }, []);

  const symbolQuery = newTrade.symbol.trim().toUpperCase();
  const filteredSymbols = symbolQuery
    ? universe.filter((t) =>
        t.symbol.toUpperCase().startsWith(symbolQuery) ||
        t.name.toLowerCase().includes(symbolQuery.toLowerCase())
      ).slice(0, 8)
    : universe.slice(0, 8);
  const isSymbolInUniverse = !!symbolQuery && universe.some((t) => t.symbol === symbolQuery);
  const canSubmitTrade = isSymbolInUniverse && !!newTrade.shares && !!newTrade.buy_price && !!holdValue;

  useEffect(() => {
    if (!symbolOpen) return;
    setSymbolIndex(0);
  }, [symbolQuery, symbolOpen]);

  const logout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  const handlePredict = async () => {
    setLoadingPreds(true);
    setPredError(null);
    try {
      const res = await api.predict.best(5);
      setPredictions(res.signals);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "ML analysis failed";
      setPredError(msg);
      console.error(e);
    } finally {
      setLoadingPreds(false);
    }
  };

  const selectSymbol = (symbol: string) => {
    setNewTrade({ ...newTrade, symbol });
    setSymbolOpen(false);
    setSymbolIndex(0);
  };

  const handleCreateTrade = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmitTrade) return;
    setTradeError(null);
    setTradeSuccess(false);
    setSubmitting(true);
    try {
      const sym = newTrade.symbol.trim().toUpperCase();
      const holdInt = parseInt(holdValue);
      if (!Number.isFinite(holdInt) || holdInt <= 0) {
        setTradeError("Enter a valid holding duration.");
        return;
      }
      await api.trades.create({
        symbol: sym,
        shares: parseFloat(newTrade.shares),
        buy_price: parseFloat(newTrade.buy_price),
        hold_unit: holdUnit,
        hold_value: holdInt,
      });
      setNewTrade({ symbol: "", shares: "", buy_price: "" });
      setTradeSuccess(true);
      setTimeout(() => setTradeSuccess(false), 4000);
      loadTrades();
    } catch (e: unknown) {
      setTradeError(e instanceof Error ? e.message : "Failed to log trade");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCloseTrade = async (id: number) => {
    try {
      await api.trades.close(id);
      loadTrades();
    } catch (e) {
      console.error(e);
    }
  };

  if (loadingAuth) return <PageLoader />;
  if (!user) return null;

  return (
    <div className="max-w-6xl mx-auto px-4 pt-20 pb-24 md:pb-12 animate-fade-in">

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8 p-4 rounded-2xl bg-[var(--surface)] border border-[var(--border)]">
        <div className="flex items-center gap-4">
          <div className="w-11 h-11 gradient-accent rounded-xl flex items-center justify-center shadow-lg shadow-blue-900/30 shrink-0">
            <UserCircle className="text-white" size={22} />
          </div>
          <div>
            <p className="font-bold text-white leading-tight">{user.username}</p>
            <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1.5">
              <Send size={9} className="text-blue-400" />
              {user.telegram_username
                ? <span><span className="text-blue-400">{user.telegram_username}</span> connected</span>
                : "No Telegram connected — add in Settings"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/account" className="text-xs font-medium text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-lg hover:bg-white/[0.05] border border-[var(--border)] hover:border-[var(--border-bright)]">
            Settings
          </Link>
          <button
            onClick={logout}
            className="text-xs font-medium text-slate-500 hover:text-red-400 transition-colors flex items-center gap-1.5 px-3 py-1.5 rounded-lg hover:bg-red-500/10"
          >
            <LogOut size={13} /> Logout
          </button>
        </div>
      </div>

      {/* ── Mobile tabs ─────────────────────────────────────────── */}
      <div className="flex items-center gap-2 mb-6 xl:hidden">
        {(["analysis", "portfolio"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-wider border transition-all ${
              activeTab === tab
                ? "bg-blue-500/20 border-blue-400/40 text-blue-200"
                : "border-[var(--border)] text-slate-400 hover:text-white bg-[var(--surface)]"
            }`}
          >
            {tab === "analysis" ? (
              <span className="flex items-center justify-center gap-1.5"><Crosshair size={13} /> ML Analysis</span>
            ) : (
              <span className="flex items-center justify-center gap-1.5">
                <Shield size={13} /> Portfolio
                {trades.length > 0 && (
                  <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-blue-500 text-white text-[9px] font-bold">
                    {trades.length}
                  </span>
                )}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Main grid ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">

        {/* ── ML Prediction column ──────────────────────────── */}
        <div className={`flex flex-col gap-4 ${activeTab !== "analysis" ? "hidden xl:flex" : ""}`}>

          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Crosshair size={18} className="text-blue-400" /> ML Analysis
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">Ensemble model: LightGBM + XGBoost + CatBoost</p>
            </div>
            <button
              onClick={handlePredict}
              disabled={loadingPreds}
              className="gradient-accent text-white font-semibold py-2 px-4 rounded-xl shadow-sm shadow-blue-900/30 transition-opacity hover:opacity-90 disabled:opacity-50 flex items-center gap-2 text-xs"
            >
              {loadingPreds ? (
                <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Analyzing…</>
              ) : (
                <><Zap size={13} /> Run ML Analysis</>
              )}
            </button>
          </div>

          {/* Result panel */}
          <div className="rounded-xl bg-[var(--surface)] border border-[var(--border)] overflow-hidden flex flex-col min-h-[340px]">

            {/* Error state */}
            {predError && !loadingPreds && (
              <div className="flex-1 flex flex-col gap-4 p-6">
                <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="text-red-400 shrink-0 mt-0.5" size={16} />
                  <div>
                    <p className="text-sm font-semibold text-red-300">Analysis failed</p>
                    <p className="text-xs text-red-400/70 mt-1 leading-relaxed">{predError}</p>
                  </div>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  This may happen if the ML model hasn&apos;t been trained yet or the data provider is temporarily unavailable. Try again in a moment.
                </p>
                <button
                  onClick={handlePredict}
                  className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 font-semibold self-start transition-colors"
                >
                  <RotateCcw size={12} /> Try again
                </button>
              </div>
            )}

            {/* Loading state */}
            {loadingPreds && (
              <div className="flex-1 flex flex-col items-center justify-center gap-4 py-12">
                <div className="relative">
                  <div className="w-12 h-12 border-2 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Zap size={14} className="text-blue-400" />
                  </div>
                </div>
                <div className="text-center px-6">
                  <p className="text-slate-300 text-sm font-semibold">Crunching market data…</p>
                  <p className="text-slate-500 text-xs mt-1.5 leading-relaxed">
                    Fetching 1 year of OHLCV data and running 3 ML models.
                  </p>
                  <div className="flex items-center justify-center gap-1.5 mt-3 text-amber-400/70 text-[10px]">
                    <Clock size={10} /> First run can take up to 90 seconds
                  </div>
                </div>
              </div>
            )}

            {/* Empty / prompt state */}
            {!predError && !loadingPreds && predictions.length === 0 && (
              <div className="flex-1 flex flex-col items-center justify-center py-12 px-6 text-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                  <Zap size={24} className="text-blue-400 opacity-60" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-400">No predictions yet</p>
                  <p className="text-xs text-slate-600 mt-2 leading-relaxed max-w-xs">
                    Run the ML analysis to get today&apos;s top algorithmically ranked stocks. Click any result to pre-fill the trade form.
                  </p>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-slate-600 bg-[var(--surface-raised)] border border-[var(--border)] rounded-lg px-3 py-2">
                  <Clock size={10} className="text-amber-500/60" />
                  Allow ~60–90 seconds on first run
                </div>
              </div>
            )}

            {/* Results table */}
            {!loadingPreds && predictions.length > 0 && (
              <div className="flex flex-col">
                <div className="grid grid-cols-4 px-5 py-2.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider border-b border-[var(--border)] bg-black/20">
                  <div>Rank</div>
                  <div>Symbol</div>
                  <div>Signal</div>
                  <div className="text-right">Strength</div>
                </div>
                {predictions.map((p, i) => (
                  <button
                    key={p.symbol}
                    type="button"
                    className="grid grid-cols-4 px-5 py-3.5 items-center hover:bg-white/[0.03] border-b border-[var(--border)] transition-colors cursor-pointer text-left w-full group"
                    onClick={() => { selectSymbol(p.symbol); setActiveTab("portfolio"); }}
                  >
                    <div className="font-mono text-slate-600 text-xs">#{i + 1}</div>
                    <div className="font-bold text-white text-base group-hover:text-blue-300 transition-colors">{p.symbol}</div>
                    <div><Badge variant="success" className="uppercase">{p.side}</Badge></div>
                    <div className="text-right font-mono text-blue-400 font-bold text-sm tabular-nums">
                      +{p.strength.toFixed(3)}
                    </div>
                  </button>
                ))}
                <div className="px-5 py-2.5 text-[10px] text-slate-600 border-t border-[var(--border)] bg-black/10 flex items-center gap-1.5">
                  <DollarSign size={9} className="text-blue-500/50" />
                  Click any row to pre-fill the trade form
                </div>
              </div>
            )}
          </div>

          {/* Info card */}
          {!loadingPreds && predictions.length > 0 && (
            <div className="rounded-xl bg-blue-500/[0.04] border border-blue-500/15 p-4 flex items-start gap-3 animate-fade-in">
              <Zap size={14} className="text-blue-400 mt-0.5 shrink-0" />
              <p className="text-xs text-slate-500 leading-relaxed">
                Signals reflect expected return over the next trading window. These are model predictions, not financial advice.
              </p>
            </div>
          )}
        </div>

        {/* ── Portfolio / Trade Manager column ──────────────── */}
        <div className={`flex flex-col gap-4 ${activeTab !== "portfolio" ? "hidden xl:flex" : ""}`}>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Shield size={18} className="text-blue-400" /> Active Portfolio
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {trades.length === 0 ? "No active positions" : `${trades.length} position${trades.length > 1 ? "s" : ""} tracked`}
              </p>
            </div>
            {trades.length > 0 && (
              <button
                onClick={loadPrices}
                disabled={loadingPrices}
                className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-blue-400 transition-colors py-1.5 px-2.5 rounded-lg hover:bg-blue-500/10"
              >
                <RefreshCw size={12} className={loadingPrices ? "animate-spin" : ""} />
                Refresh
              </button>
            )}
          </div>

          {/* New trade form */}
          <div className="rounded-xl bg-[var(--surface)] border border-[var(--border)] p-4">
            <h3 className="text-xs font-bold text-blue-300 mb-4 flex items-center gap-2 uppercase tracking-wider">
              <Plus size={14} /> Log a New Trade
            </h3>
            <form onSubmit={handleCreateTrade} className="flex flex-col gap-3">

              {/* Symbol + Shares + Price */}
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold block mb-1">Symbol</label>
                  <div className="relative">
                    <input
                      required
                      type="text"
                      placeholder="AAPL"
                      className="input-field uppercase text-sm py-2 px-3 rounded-lg"
                      value={newTrade.symbol}
                      onFocus={() => setSymbolOpen(true)}
                      onBlur={() => setTimeout(() => setSymbolOpen(false), 120)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") { setSymbolOpen(false); return; }
                        if (!symbolOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) setSymbolOpen(true);
                        if (!filteredSymbols.length) return;
                        if (e.key === "ArrowDown") { e.preventDefault(); setSymbolIndex((i) => (i + 1) % filteredSymbols.length); }
                        if (e.key === "ArrowUp")   { e.preventDefault(); setSymbolIndex((i) => (i - 1 + filteredSymbols.length) % filteredSymbols.length); }
                        if (e.key === "Enter" && symbolOpen) {
                          e.preventDefault();
                          const picked = filteredSymbols[symbolIndex];
                          if (picked) selectSymbol(picked.symbol);
                        }
                      }}
                      onChange={(e) => {
                        setTradeError(null);
                        setSymbolOpen(true);
                        setNewTrade({ ...newTrade, symbol: e.target.value.toUpperCase() });
                      }}
                    />
                    {symbolOpen && (
                      <div className="absolute z-20 mt-1 w-full rounded-xl bg-[var(--surface-raised)] border border-[var(--border)] shadow-2xl overflow-hidden animate-fade-in">
                        {filteredSymbols.length > 0 ? (
                          filteredSymbols.map((t, i) => (
                            <button
                              key={t.symbol}
                              type="button"
                              onClick={() => selectSymbol(t.symbol)}
                              onMouseEnter={() => setSymbolIndex(i)}
                              className={`w-full text-left px-3 py-2 text-xs transition-colors flex items-center gap-2 ${
                                i === symbolIndex ? "bg-blue-600/20 text-white" : "hover:bg-white/[0.03] text-slate-300"
                              }`}
                            >
                              <span className="font-mono font-bold text-white text-xs w-14 shrink-0">{t.symbol}</span>
                              <span className="text-slate-500 truncate flex-1 text-[10px]">{t.name}</span>
                            </button>
                          ))
                        ) : symbolQuery ? (
                          <div className="px-3 py-2.5 text-xs text-slate-500">No matches found.</div>
                        ) : null}
                      </div>
                    )}
                  </div>
                  {symbolQuery && !isSymbolInUniverse && (
                    <p className="text-[10px] text-red-400 mt-0.5">Select from list</p>
                  )}
                </div>

                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold block mb-1">Shares</label>
                  <input
                    required
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="10"
                    className="input-field text-sm py-2 px-3 rounded-lg"
                    value={newTrade.shares}
                    onChange={(e) => setNewTrade({ ...newTrade, shares: e.target.value })}
                  />
                </div>

                <div>
                  <label className="text-[10px] uppercase tracking-wider text-slate-500 font-bold block mb-1">Buy $</label>
                  <input
                    required
                    type="number"
                    step="0.01"
                    min="0.01"
                    placeholder="150.00"
                    className="input-field text-sm py-2 px-3 rounded-lg"
                    value={newTrade.buy_price}
                    onChange={(e) => setNewTrade({ ...newTrade, buy_price: e.target.value })}
                  />
                </div>
              </div>

              {/* Holding duration */}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] p-3 flex flex-col gap-2.5">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Holding Duration</p>
                <div className="flex gap-1.5 flex-wrap">
                  {(["days", "months", "years"] as const).map((unit) => (
                    <label
                      key={unit}
                      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-[10px] uppercase tracking-wider font-bold cursor-pointer transition-all ${
                        holdUnit === unit
                          ? "bg-blue-500/15 border-blue-500/40 text-blue-300"
                          : "border-[var(--border)] text-slate-500 hover:text-white hover:border-[var(--border-bright)]"
                      }`}
                    >
                      <input type="radio" name="hold_unit" className="accent-blue-500 sr-only" checked={holdUnit === unit} onChange={() => setHoldUnit(unit)} />
                      {unit}
                    </label>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="1"
                    className="input-field max-w-[120px] text-sm py-1.5 px-3 rounded-lg"
                    value={holdValue}
                    onChange={(e) => setHoldValue(e.target.value)}
                  />
                  <span className="text-xs text-slate-500">{holdUnit}</span>
                </div>
              </div>

              {tradeError && (
                <Alert variant="danger">
                  <AlertCircle size={14} className="shrink-0 mt-0.5" />
                  {tradeError}
                </Alert>
              )}
              {tradeSuccess && (
                <Alert variant="success">
                  <span className="font-semibold">Trade logged!</span> Telegram alert activated if connected.
                </Alert>
              )}

              <button
                type="submit"
                disabled={!canSubmitTrade || submitting}
                className="w-full gradient-accent text-white font-bold py-2.5 rounded-xl transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-sm shadow-sm shadow-blue-900/30"
              >
                {submitting ? (
                  <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Validating…</>
                ) : (
                  <>Log Trade &amp; Activate Alerts</>
                )}
              </button>
            </form>
          </div>

          {/* Active positions */}
          <div className="flex flex-col gap-3">
            {trades.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 rounded-2xl border border-dashed border-white/10 text-slate-600 gap-3">
                <Shield size={28} className="opacity-20" />
                <p className="text-sm">No active positions being tracked.</p>
              </div>
            ) : (
              trades.map((t) => (
                <TradeCard
                  key={t.id}
                  t={t}
                  currentPrice={prices[t.symbol]}
                  onClose={handleCloseTrade}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
