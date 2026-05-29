"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Sparkles, RefreshCw, TrendingUp, TrendingDown, Clock, Database,
  AlertTriangle, ChevronDown, Filter, Info, ArrowUpRight, Plus,
} from "lucide-react";
import { api, PredictionExplanation, PredictionItem, PredictionResponse } from "@/lib/api";
import { Card, CardHeader, Badge, Alert, Skeleton } from "@/components/ui";
import Link from "next/link";

const TABLE_HEADERS = ["#", "Ticker", "Company", "Sector", "Signal", "Strength", "Pred. Return 5d", "Drivers"];

// ── Helpers ─────────────────────────────────────────────────────────────────

function StrengthBar({ value, side }: { value: number; side: string }) {
  const pct = Math.abs(value) * 100;
  const isLong = side === "long";
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${isLong ? "bg-emerald-500" : "bg-red-500"}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className={`text-[10px] font-mono tabular-nums w-8 text-right ${isLong ? "text-emerald-400" : "text-red-400"}`}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

function SectorBadge({ sector }: { sector: string }) {
  const colors: Record<string, string> = {
    "Information Technology": "text-blue-300 bg-blue-500/10 border-blue-500/20",
    "Health Care": "text-emerald-300 bg-emerald-500/10 border-emerald-500/20",
    "Financials": "text-violet-300 bg-violet-500/10 border-violet-500/20",
    "Consumer Discretionary": "text-orange-300 bg-orange-500/10 border-orange-500/20",
    "Consumer Staples": "text-yellow-300 bg-yellow-500/10 border-yellow-500/20",
    "Industrials": "text-cyan-300 bg-cyan-500/10 border-cyan-500/20",
    "Energy": "text-amber-300 bg-amber-500/10 border-amber-500/20",
    "Materials": "text-lime-300 bg-lime-500/10 border-lime-500/20",
    "Real Estate": "text-pink-300 bg-pink-500/10 border-pink-500/20",
    "Utilities": "text-teal-300 bg-teal-500/10 border-teal-500/20",
    "Communication Services": "text-indigo-300 bg-indigo-500/10 border-indigo-500/20",
  };
  const cls = colors[sector] ?? "text-slate-400 bg-slate-500/10 border-slate-500/20";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-semibold tracking-wide ${cls}`}>
      {sector.replace("Information Technology", "Tech").replace("Communication Services", "Comms").replace("Consumer ", "Cons. ")}
    </span>
  );
}

function ExplanationPills({ items }: { items?: PredictionExplanation[] }) {
  if (!items || items.length === 0) {
    return <span className="text-[10px] text-slate-600">No drivers</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {items.slice(0, 3).map((item) => (
        <span
          key={`${item.feature}-${item.zscore}`}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-700/50 bg-slate-800/40 px-2.5 py-1 text-[10px] text-slate-300"
        >
          <span className={item.direction === "higher" ? "text-emerald-400" : "text-red-400"}>
            {item.direction === "higher" ? "▲" : "▼"}
          </span>
          <span className="font-mono">{item.feature}</span>
          <span className="text-slate-500">z={item.zscore.toFixed(2)}</span>
        </span>
      ))}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function ScreenerPage() {
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [forcing, setForcing] = useState(false);
  const [isComputing, setIsComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topN, setTopN] = useState(10);
  const [sectorFilter, setSectorFilter] = useState<string>("");
  const [directionFilter, setDirectionFilter] = useState<"all" | "long" | "short">("all");
  const [sectors, setSectors] = useState<string[]>([]);
  const [hasLoaded, setHasLoaded] = useState(false);

  const fetchPredictions = useCallback(async (force = false) => {
    setError(null);
    if (force) setForcing(true);
    else if (!isComputing) setLoading(true);

    try {
      const data = await api.predict.best(50, sectorFilter || undefined, force);
      if (data.status === "computing") {
        setIsComputing(true);
        setTimeout(() => fetchPredictions(false), 10000);
      } else {
        setIsComputing(false);
        setResult(data);
        setHasLoaded(true);
        setLoading(false);
        setForcing(false);
      }
    } catch (err: any) {
      setError(err?.message ?? "Failed to load predictions. Please try again.");
      setIsComputing(false);
      setLoading(false);
      setForcing(false);
    }
  }, [sectorFilter, isComputing]);

  useEffect(() => {
    fetchPredictions(false);
  }, []);

  useEffect(() => {
    api.predict.sectors().then(setSectors).catch(() => {});
  }, []);

  // Apply client-side filters on the cached result
  const signals = (result?.signals ?? []).filter(s => {
    if (directionFilter !== "all" && s.side !== directionFilter) return false;
    if (sectorFilter && s.sector.toLowerCase() !== sectorFilter.toLowerCase()) return false;
    return true;
  }).slice(0, topN);

  const topSignals = signals.slice(0, 3);
  const longs = signals.filter(s => s.side === "long").length;
  const shorts = signals.filter(s => s.side === "short").length;

  return (
    <div className="min-h-screen pt-20 pb-24 md:pb-12 animate-fade-in relative overflow-hidden prediction-aurora">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 right-[-8%] h-72 w-72 rounded-full bg-amber-400/10 blur-3xl animate-float-slow" />
        <div className="absolute top-24 left-[-6%] h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl animate-float-slower" />
        <div className="absolute bottom-[-20%] right-1/3 h-80 w-80 rounded-full bg-rose-400/10 blur-[120px] animate-float-slow" />
      </div>
      <div className="max-w-7xl mx-auto px-4 flex flex-col gap-4 relative z-10">

        {/* ── Page Header ──────────────────────────────────────────────── */}
        <div className="animate-fade-in-up flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-amber-400/20 bg-amber-400/10 text-[10px] uppercase tracking-[0.22em] text-amber-200">
              Prediction Lab
            </div>
            <div className="flex items-center gap-3 mt-3">
              <div className="w-10 h-10 rounded-xl gradient-accent flex items-center justify-center shadow-sm shadow-blue-900/30">
                <Sparkles size={18} className="text-white" />
              </div>
              <h1 className="text-3xl md:text-4xl font-black text-white tracking-tight">ML Stock Screener</h1>
            </div>
            <p className="text-slate-400 text-sm mt-3">
              Ranked S&P 500 signals for the next 5 trading days, with drivers pulled from the top ML features.
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              {["3Y history", "Top/Bottom decile", "5D horizon", "S&P 500 only"].map((chip) => (
                <span key={chip} className="text-[10px] uppercase tracking-wider px-2.5 py-1 rounded-full border border-slate-700 bg-slate-900/40 text-slate-400">
                  {chip}
                </span>
              ))}
            </div>
          </div>

          {/* Cache status + re-run button */}
          <div className="flex items-center gap-3 ml-12 lg:ml-0 flex-wrap">
            {result && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-2xl border border-[var(--border)] bg-[var(--surface)] text-[11px] text-slate-500">
                {result.cached ? (
                  <>
                    <Clock size={11} className="text-amber-400" />
                    <span className="text-amber-300">Cached</span>
                    <span>· {result.cache_age_minutes.toFixed(0)}m ago</span>
                  </>
                ) : (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-emerald-300">Fresh</span>
                    <span>· {result.date}</span>
                  </>
                )}
                <span className="mx-1 text-slate-600">|</span>
                <Database size={11} />
                <span>{result.universe_size} stocks scanned</span>
              </div>
            )}
            <button
              id="screener-rerun-btn"
              onClick={() => fetchPredictions(true)}
              disabled={forcing || isComputing || loading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold gradient-accent text-white hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed shadow-sm shadow-blue-900/30"
            >
              <RefreshCw size={13} className={forcing || isComputing ? "animate-spin" : ""} />
              {forcing || isComputing ? "Recomputing…" : "Re-run Predictions"}
            </button>
          </div>
        </div>

        {/* ── Re-run warning ───────────────────────────────────────────── */}
        {(forcing || isComputing) && (
          <Alert variant="warning">
            <strong>Training Models in Background</strong> — the ML ensemble is training on ~100 stocks. This will take ~2–3 minutes. You can safely close this page, it will auto-refresh when ready.
          </Alert>
        )}

        {/* ── Error ────────────────────────────────────────────────────── */}
        {error && (
          <Alert variant="danger">
            <div className="flex items-start gap-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <div>
                <strong>Prediction failed</strong>
                <p className="text-xs mt-0.5 opacity-80">{error}</p>
              </div>
            </div>
          </Alert>
        )}

        {/* ── Main grid ───────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">

          {/* ── Sidebar ─────────────────────────────────────────────── */}
          <div className="lg:col-span-1 flex flex-col gap-4 animate-slide-in-left">

            {/* Filters */}
            <Card>
              <CardHeader title="Filters" subtitle="Narrow your results" />
              <div className="flex flex-col gap-4">

                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1.5">
                    Show Top N
                  </label>
                  <select
                    id="screener-top-n"
                    className="input-field"
                    value={topN}
                    onChange={e => setTopN(Number(e.target.value))}
                  >
                    {[5, 10, 20, 50].map(n => (
                      <option key={n} value={n}>Top {n} stocks</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1.5">
                    Sector
                  </label>
                  <select
                    id="screener-sector-filter"
                    className="input-field"
                    value={sectorFilter}
                    onChange={e => setSectorFilter(e.target.value)}
                  >
                    <option value="">All Sectors</option>
                    {sectors.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1.5">
                    Direction
                  </label>
                  <div className="grid grid-cols-3 gap-1">
                    {(["all", "long", "short"] as const).map(d => (
                      <button
                        key={d}
                        id={`screener-dir-${d}`}
                        onClick={() => setDirectionFilter(d)}
                        className={`py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                          directionFilter === d
                            ? d === "long"
                              ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                              : d === "short"
                              ? "bg-red-500/15 border-red-500/30 text-red-300"
                              : "bg-blue-500/15 border-blue-500/30 text-blue-300"
                            : "border-[var(--border)] text-slate-500 hover:text-slate-300 hover:bg-white/[0.03]"
                        }`}
                      >
                        {d.charAt(0).toUpperCase() + d.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            {/* Summary stats */}
            {result && !loading && (
              <Card>
                <CardHeader title="Summary" />
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Showing</span>
                    <span className="text-white font-semibold">{signals.length} stocks</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-500 flex items-center gap-1.5"><TrendingUp size={11} className="text-emerald-500" /> Bullish picks</span>
                    <span className="text-emerald-400 font-semibold">{longs}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-500 flex items-center gap-1.5"><TrendingDown size={11} className="text-red-500" /> Bearish picks</span>
                    <span className="text-red-400 font-semibold">{shorts}</span>
                  </div>
                  <div className="h-px bg-[var(--border)] my-1" />
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Universe scanned</span>
                    <span className="text-slate-300 font-mono">{result.universe_size}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-500">Model date</span>
                    <span className="text-slate-300 font-mono">{result.date}</span>
                  </div>
                  {result.model_metrics && (
                    <>
                      <div className="h-px bg-[var(--border)] my-1" />
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Validation</div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-500">Hit rate</span>
                        <span className="text-slate-300 font-mono">{((result.model_metrics.hit_rate ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-500">Spearman IC</span>
                        <span className="text-slate-300 font-mono">{(result.model_metrics.spearman_ic ?? 0).toFixed(3)}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-500">RMSE</span>
                        <span className="text-slate-300 font-mono">{(result.model_metrics.rmse ?? 0).toFixed(4)}</span>
                      </div>
                    </>
                  )}
                </div>
              </Card>
            )}

            {/* How it works */}
            <Card>
              <CardHeader title="How it works" />
              <div className="flex flex-col gap-3 text-xs text-slate-400 leading-relaxed">
                <p>The ML ensemble trains on <strong className="text-slate-200">3 years of price & feature data</strong> from the S&P 500, then predicts each stock's 5-day forward return.</p>
                <p>Stocks are ranked by predicted return, and the <strong className="text-slate-200">top decile → Long</strong>, <strong className="text-slate-200">bottom decile → Short</strong>.</p>
                <p>Drivers highlight the most extreme features (z-scores) behind each rank.</p>
                <p>Results are <strong className="text-slate-200">cached daily</strong>. Use Re-run to get fresh signals.</p>
                <div className="h-px bg-[var(--border)] my-1" />
                <Link
                  href="/backtest"
                  className="flex items-center gap-1.5 text-[var(--accent)] hover:opacity-80 transition-opacity font-semibold"
                >
                  Validate model in Backtest
                  <ArrowUpRight size={12} />
                </Link>
              </div>
            </Card>
          </div>

          {/* ── Results Table ────────────────────────────────────────── */}
          <div className="lg:col-span-3 animate-fade-in-up">
            {topSignals.length > 0 && (
              <div className="grid md:grid-cols-3 gap-4 mb-6">
                {topSignals.map((s, i) => (
                  <div
                    key={s.symbol}
                    className={`relative overflow-hidden rounded-3xl border bg-[var(--surface)]/60 p-4 shadow-xl animate-fade-in-up ${
                      i === 0 ? "border-amber-400/40" : "border-[var(--border)]"
                    }`}
                    style={{ animationDelay: `${i * 60}ms` }}
                  >
                    <div className="absolute -top-16 -right-12 h-32 w-32 rounded-full bg-amber-400/10 blur-2xl" />
                    <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-500">
                      <span>Rank {String(i + 1).padStart(2, "0")}</span>
                      <span className={s.side === "long" ? "text-emerald-300" : "text-red-300"}>{s.side}</span>
                    </div>
                    <div className="mt-3 text-3xl font-black text-white tracking-tight">
                      {s.symbol}
                    </div>
                    <div className="text-xs text-slate-500 mt-1 truncate">{s.name || s.symbol}</div>
                    <div className="mt-3 flex items-center justify-between text-xs">
                      <span className={`font-mono font-semibold ${
                        s.predicted_return_pct >= 0 ? "text-emerald-400" : "text-red-400"
                      }`}>
                        {s.predicted_return_pct >= 0 ? "+" : ""}{s.predicted_return_pct.toFixed(2)}% 5d
                      </span>
                      <span className="text-slate-400">Strength {Math.abs(s.strength).toFixed(2)}</span>
                    </div>
                    <div className="mt-3">
                      <ExplanationPills items={s.explanations} />
                    </div>
                  </div>
                ))}
              </div>
            )}
            <Card variant="compact">
              <CardHeader
                title="Top Predictions"
                subtitle={`ML-ranked stocks for the week · ${result?.date ?? "Loading…"}`}
                density="compact"
              />

              {/* Loading skeletons */}
              {(loading && !hasLoaded) && (
                <div className="flex flex-col gap-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="skeleton h-12 rounded-xl" style={{ animationDelay: `${i * 40}ms` }} />
                  ))}
                </div>
              )}

              {/* Results */}
              {(!loading || hasLoaded) && signals.length > 0 && (
                <div className="overflow-x-auto rounded-xl border border-[var(--border)] bg-black/20">
                  <table className="w-full text-xs min-w-[640px] border-collapse">
                    <thead>
                      <tr className="border-b border-[var(--border)] bg-white/[0.02]">
                        {TABLE_HEADERS.map(h => (
                          <th key={h} className="text-left px-4 py-3 text-[10px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {signals.map((s, i) => (
                        <tr
                          key={s.symbol}
                          className="border-b border-[var(--border)]/40 hover:bg-white/[0.025] transition-colors animate-fade-in-up"
                          style={{ animationDelay: `${i * 40}ms` }}
                        >
                          <td className="px-4 py-4 text-slate-600 font-mono text-[10px]">
                            {String(i + 1).padStart(2, "0")}
                          </td>
                          <td className="px-4 py-4">
                            <span className="font-mono font-bold text-white tracking-wide">{s.symbol}</span>
                          </td>
                          <td className="px-4 py-4 text-slate-400 max-w-[160px] truncate">
                            {s.name || s.symbol}
                          </td>
                          <td className="px-4 py-4">
                            <SectorBadge sector={s.sector} />
                          </td>
                          <td className="px-4 py-4">
                            <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold border ${
                              s.side === "long"
                                ? "text-emerald-300 bg-emerald-500/10 border-emerald-500/25"
                                : "text-red-300 bg-red-500/10 border-red-500/25"
                            }`}>
                              {s.side === "long"
                                ? <TrendingUp size={12} />
                                : <TrendingDown size={12} />}
                              {s.side.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-4 py-4 w-32">
                            <StrengthBar value={s.strength} side={s.side} />
                          </td>
                          <td className="px-4 py-4">
                            <span className={`font-mono font-semibold tabular-nums ${
                              s.predicted_return_pct >= 0 ? "text-emerald-400" : "text-red-400"
                            }`}>
                              {s.predicted_return_pct >= 0 ? "+" : ""}{s.predicted_return_pct.toFixed(2)}%
                            </span>
                          </td>
                          <td className="px-4 py-4">
                            <ExplanationPills items={s.explanations} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Empty state */}
              {(!loading || hasLoaded) && signals.length === 0 && !error && (
                <div className="flex flex-col items-center justify-center py-16 gap-4">
                  <div className="w-14 h-14 rounded-xl bg-[var(--surface)] border border-[var(--border)] flex items-center justify-center">
                    <Sparkles size={24} className="text-slate-600" />
                  </div>
                  <div className="text-center">
                    <p className="text-slate-400 text-sm font-semibold">No predictions yet</p>
                    <p className="text-slate-600 text-xs mt-1">
                      {hasLoaded ? "Try clearing filters or re-running the model." : "Click Re-run Predictions to generate ML signals."}
                    </p>
                  </div>
                  <button
                    onClick={() => fetchPredictions(false)}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold gradient-accent text-white hover:opacity-90 transition-opacity"
                  >
                    <Sparkles size={13} />
                    Load Predictions
                  </button>
                </div>
              )}
            </Card>

            {/* Disclaimer */}
            <div className="mt-4 flex items-start gap-2 px-1 text-[10px] text-slate-600 leading-relaxed">
              <Info size={11} className="mt-0.5 shrink-0" />
              <p>
                These predictions are generated by a machine learning model trained on historical price data and are for <strong className="text-slate-500">informational purposes only</strong>. Past model performance does not guarantee future results. Always conduct your own research before making any investment decisions.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
