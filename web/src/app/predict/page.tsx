"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Sparkles, RefreshCw, TrendingUp, TrendingDown, Clock, Database,
  AlertTriangle, Info, ArrowUpRight,
} from "lucide-react";
import { api, PredictionExplanation, PredictionResponse } from "@/lib/api";
import { Card, CardHeader, Alert } from "@/components/ui";
import Link from "next/link";

const TABLE_HEADERS = ["Stock", "Sector", "Signal", "Strength", "Return 21d", "Drivers"];

function StrengthBar({ value, side }: { value: number; side: string }) {
  const pct = Math.abs(value) * 100;
  const isLong = side === "long";
  return (
    <div className="flex items-center gap-2 w-full">
      <div className="flex-1 h-1.5 rounded-full bg-[var(--color-surface-raised)] overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${isLong ? "bg-[var(--color-success)]" : "bg-[var(--color-danger)]"}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className={`text-[10px] font-mono tabular-nums w-8 text-right ${isLong ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

function SectorBadge({ sector }: { sector: string }) {
  const colors: Record<string, string> = {
    "Information Technology": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Health Care": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Financials": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Consumer Discretionary": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Consumer Staples": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Industrials": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Energy": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Materials": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Real Estate": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Utilities": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
    "Communication Services": "text-[var(--color-text-secondary)] bg-[var(--color-surface-raised)] border-[var(--border)]",
  };
  const cls = colors[sector] ?? "text-[var(--color-text-muted)] bg-[var(--color-surface-raised)] border-[var(--color-border)]";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[10px] font-semibold tracking-wide ${cls}`}>
      {sector.replace("Information Technology", "Tech").replace("Communication Services", "Comms").replace("Consumer ", "Cons. ")}
    </span>
  );
}

function ExplanationPills({ items }: { items?: PredictionExplanation[] }) {
  if (!items || items.length === 0) {
    return <span className="text-[10px] text-[var(--color-text-muted)]">No drivers</span>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.slice(0, 3).map((item) => (
        <span
          key={`${item.feature}-${item.zscore}`}
          className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1 text-[10px] text-[var(--color-text-secondary)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
        >
          <span className={item.direction === "higher" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
            {item.direction === "higher" ? "▲" : "▼"}
          </span>
          <span className="font-mono">{item.feature}</span>
          <span className="text-[var(--color-text-muted)]">z={item.zscore.toFixed(2)}</span>
        </span>
      ))}
    </div>
  );
}

function DriverLegend() {
  const items = [
    { label: "sma_crossover", desc: "Short MA vs long MA. Bullish when shorter averages are above longer ones.", tone: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
    { label: "rsi_14", desc: "14-day Relative Strength Index. Higher values show stronger momentum; extremes can signal overbought/oversold conditions.", tone: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
    { label: "macd_histogram", desc: "MACD momentum spread. Positive values often mean momentum is improving; negative values mean it is weakening.", tone: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
    { label: "return_63d / return_126d", desc: "Medium-term price trend over roughly 3 to 6 months.", tone: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
    { label: "volatility_*", desc: "How much the stock has been moving. Higher volatility means larger swings and less stability.", tone: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
    { label: "amihud_illiquidity", desc: "Liquidity proxy. Higher values mean the stock is harder to trade without moving price.", tone: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
  ];

  return (
    <div className="mt-4 pt-4 border-t border-[var(--border)]/70 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)] font-semibold">
          Feature guide
        </p>
        <p className="text-[12px] md:text-[13px] text-[var(--color-text-muted)] max-w-2xl leading-relaxed">
          The pills show the top features that pushed the model toward a long or short signal. The z-score tells you how unusual the value is versus the recent history.
        </p>
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {items.map((item) => (
          <div
            key={item.label}
            className={`rounded-2xl border px-3 py-2 text-[11px] md:text-[12px] ${item.bg} ${item.border} ${item.tone}`}
          >
            <div className="font-semibold uppercase tracking-[0.18em] text-[10px]">{item.label}</div>
            <div className="mt-1 text-[var(--color-text-secondary)] leading-relaxed">{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PredictPage() {
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
  const [predictionMode, setPredictionMode] = useState<"live" | "previous_close">("previous_close");

  // Use a ref to track computing state inside callbacks without causing
  // dependency changes that would re-trigger useEffect and create an
  // infinite render loop.
  const isComputingRef = useRef(false);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchPredictions = useCallback(async function fetchPredictions(force = false, mode: "live" | "previous_close" = predictionMode) {
    setError(null);
    if (force) setForcing(true);
    else if (!isComputingRef.current) setLoading(true);

    try {
      const data = await api.predict.best(50, sectorFilter || undefined, force, mode);
      if (data.status === "computing") {
        isComputingRef.current = true;
        setIsComputing(true);
        // Clear any existing poll timer before setting a new one
        if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
        pollTimerRef.current = setTimeout(() => fetchPredictions(false, mode), 10000);
      } else {
        isComputingRef.current = false;
        setIsComputing(false);
        setResult(data);
        setHasLoaded(true);
        setLoading(false);
        setForcing(false);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load predictions. Please try again.");
      isComputingRef.current = false;
      setIsComputing(false);
      setLoading(false);
      setForcing(false);
    }
  }, [predictionMode, sectorFilter]);

  const handleModeChange = useCallback((nextMode: "live" | "previous_close") => {
    if (nextMode === predictionMode) return;
    // Clear any pending poll when switching modes
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    isComputingRef.current = false;
    setIsComputing(false);
    setPredictionMode(nextMode);
    fetchPredictions(false, nextMode);
  }, [fetchPredictions, predictionMode]);

  // Initial load — only runs when predictionMode or sectorFilter changes,
  // NOT when isComputing toggles (which was the source of the infinite loop).
  useEffect(() => {
    fetchPredictions(false);
    return () => {
      // Cleanup poll timer on unmount or dependency change
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [fetchPredictions]);

  useEffect(() => {
    api.predict.sectors().then(setSectors).catch(() => {});
  }, []);

  const signals = (result?.signals ?? []).filter(s => {
    if (directionFilter !== "all" && s.side !== directionFilter) return false;
    if (sectorFilter && s.sector.toLowerCase() !== sectorFilter.toLowerCase()) return false;
    return true;
  }).slice(0, topN);

  const topSignals = signals.slice(0, 3);
  const longs = signals.filter(s => s.side === "long").length;
  const shorts = signals.filter(s => s.side === "short").length;

  return (
    <div className="min-h-screen pt-16 pb-16 md:pb-10 animate-fade-in relative overflow-hidden prediction-aurora">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 right-[-8%] h-72 w-72 rounded-full bg-[var(--color-cta)]/10 blur-3xl animate-float-slow" />
        <div className="absolute top-24 left-[-6%] h-64 w-64 rounded-full bg-[var(--color-success)]/10 blur-3xl animate-float-slower" />
        <div className="absolute bottom-[-20%] right-1/3 h-80 w-80 rounded-full bg-[var(--color-danger)]/10 blur-[120px] animate-float-slow" />
      </div>
      <div className="max-w-[1800px] mx-auto px-3 lg:px-5 flex flex-col gap-3 relative z-10">

        {/* Page Header */}
        <div className="animate-fade-in-up flex flex-col xl:flex-row xl:items-end xl:justify-between gap-3">
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[var(--border)] bg-[var(--color-surface)] text-[10px] uppercase tracking-[0.22em] text-[var(--color-text-secondary)]">
              Prediction Lab
            </div>
            <div className="flex items-center gap-3 mt-3">
              <div className="w-10 h-10 rounded-xl gradient-accent flex items-center justify-center shadow-sm shadow-[var(--color-cta)]/30">
                <Sparkles size={18} className="text-[var(--color-text-inverse)]" />
              </div>
              <h1 className="text-4xl md:text-5xl font-black text-[var(--color-text-primary)] tracking-tight">ML Stock Screener</h1>
            </div>
            <p className="text-[var(--color-text-secondary)] text-base mt-3 max-w-2xl leading-relaxed">
              Ranked S&P 500 signals for the next trading day, with drivers pulled from the top ML features.
            </p>
            <div className="flex flex-wrap gap-2 mt-4">
              {["3Y history", "Top/Bottom decile", "21D horizon", "S&P 500 only"].map((chip) => (
                <span key={chip} className="text-[10px] uppercase tracking-[0.18em] px-3 py-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)]">
                  {chip}
                </span>
              ))}
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3 ml-0 flex-wrap xl:justify-end">
            {result && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] text-[12px] text-[var(--color-text-muted)]">
                {result.cached ? (
                  <>
                    <Clock size={11} className="text-[var(--color-accent)]" />
                    <span className="text-[var(--color-accent)]">Cached</span>
                    <span>· {result.cache_age_minutes.toFixed(0)}m ago</span>
                  </>
                ) : (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-success)] animate-pulse" />
                    <span className="text-[var(--color-success)]">Fresh</span>
                    <span>· {result.date}</span>
                  </>
                )}
                <span className="mx-1 text-[var(--color-text-muted)]">|</span>
                <Database size={11} />
                <span>{result.universe_size} stocks scanned</span>
              </div>
            )}
            <div className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
              <button
                type="button"
                onClick={() => handleModeChange("previous_close")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] transition-all ${
                  predictionMode === "previous_close"
                    ? "bg-[var(--color-surface)]/25 text-[var(--color-text-primary)] shadow-sm"
                    : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
                }`}
              >
                <Clock size={11} className={predictionMode === "previous_close" ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"} />
                Previous Close
              </button>
              <button
                type="button"
                onClick={() => handleModeChange("live")}
                className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] transition-all ${
                  predictionMode === "live"
                    ? "bg-[var(--color-surface)]/25 text-[var(--color-text-primary)] shadow-sm"
                    : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
                }`}
              >
                <ArrowUpRight size={11} className={predictionMode === "live" ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)]"} />
                Live
              </button>
            </div>
            <button
              id="screener-rerun-btn"
              onClick={() => fetchPredictions(true, predictionMode)}
              disabled={forcing || isComputing || loading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold gradient-accent text-[var(--color-text-inverse)] hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed shadow-sm shadow-[var(--color-cta)]/30"
            >
              <RefreshCw size={13} className={forcing || isComputing ? "animate-spin" : ""} />
              {forcing || isComputing ? "Recomputing…" : "Re-run Predictions"}
            </button>
          </div>
        </div>

        {(forcing || isComputing) && (
          <Alert variant="warning">
            <strong>Training Models in Background</strong> — the ML ensemble is training on ~100 stocks. This will take ~2–3 minutes. You can safely close this page, it will auto-refresh when ready.
          </Alert>
        )}

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

        <div className="grid grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)] gap-4">

          <div className="flex flex-col gap-4 animate-slide-in-left">
            <Card variant="compact">
              <CardHeader title="Filters" subtitle="Narrow your results" density="compact" />
              <div className="flex flex-col gap-4">

                <div>
                  <label className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider font-semibold block mb-1.5">
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
                  <label className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider font-semibold block mb-1.5">
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
                  <label className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider font-semibold block mb-1.5">
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
                              ? "bg-[var(--color-success)]/15 border-[var(--color-success)] text-[var(--color-success)]"
                              : d === "short"
                              ? "bg-[var(--color-danger)]/15 border-[var(--color-danger)] text-[var(--color-danger)]"
                              : "bg-[var(--color-accent)]/15 border-[var(--color-accent)] text-[var(--color-accent)]"
                            : "border-[var(--border)] text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-raised)]"
                        }`}
                      >
                        {d.charAt(0).toUpperCase() + d.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>

            {result && !loading && (
              <Card variant="compact">
                <CardHeader title="Summary" density="compact" />
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-muted)]">Showing</span>
                    <span className="text-[var(--color-text-inverse)] font-semibold">{signals.length} stocks</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[var(--color-text-muted)] flex items-center gap-1.5"><TrendingUp size={11} className="text-[var(--color-success)]" /> Bullish picks</span>
                    <span className="text-[var(--color-success)] font-semibold">{longs}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-[var(--color-text-muted)] flex items-center gap-1.5"><TrendingDown size={11} className="text-[var(--color-danger)]" /> Bearish picks</span>
                    <span className="text-[var(--color-danger)] font-semibold">{shorts}</span>
                  </div>
                  <div className="h-px bg-[var(--border)] my-1" />
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-muted)]">Universe scanned</span>
                    <span className="text-[var(--color-text-secondary)] font-mono">{result.universe_size}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-[var(--color-text-muted)]">Model date</span>
                    <span className="text-[var(--color-text-secondary)] font-mono">{result.date}</span>
                  </div>
                  {result.model_metrics && (
                    <>
                      <div className="h-px bg-[var(--border)] my-1" />
                      <div className="text-[10px] uppercase tracking-wider text-[var(--color-text-muted)] font-semibold">Validation</div>
                      <div className="flex justify-between text-xs">
                        <span className="text-[var(--color-text-muted)]">Hit rate</span>
                        <span className="text-[var(--color-text-secondary)] font-mono">{((result.model_metrics.hit_rate ?? 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-[var(--color-text-muted)]">Spearman IC</span>
                        <span className="text-[var(--color-text-secondary)] font-mono">{(result.model_metrics.spearman_ic ?? 0).toFixed(3)}</span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-[var(--color-text-muted)]">RMSE</span>
                        <span className="text-[var(--color-text-secondary)] font-mono">{(result.model_metrics.rmse ?? 0).toFixed(4)}</span>
                      </div>
                    </>
                  )}
                </div>
              </Card>
            )}

            <Card variant="compact">
              <CardHeader title="How it works" density="compact" />
              <div className="flex flex-col gap-3 text-xs text-[var(--color-text-muted)] leading-relaxed">
                <p>The ML ensemble trains on <strong className="text-[var(--color-text-secondary)]">3 years of price & feature data</strong> from the S&P 500, then predicts each stock&apos;s 21-day forward return.</p>
                <p>Stocks are ranked by predicted return, and the <strong className="text-[var(--color-text-secondary)]">top decile → Long</strong>, <strong className="text-[var(--color-text-secondary)]">bottom decile → Short</strong>.</p>
                <p>Drivers highlight the most extreme features (z-scores) behind each rank.</p>
                <p>Results are <strong className="text-[var(--color-text-secondary)]">cached daily</strong>. Use Re-run to get fresh signals.</p>
                <div className="h-px bg-[var(--border)] my-1" />
                <Link
                  href="/backtest"
                  className="flex items-center gap-1.5 text-[var(--color-accent)] hover:opacity-80 transition-opacity font-semibold"
                >
                  Validate model in Backtest
                  <ArrowUpRight size={12} />
                </Link>
              </div>
            </Card>
          </div>

          <div className="animate-fade-in-up min-w-0">
            {topSignals.length > 0 && (
              <div className="grid md:grid-cols-3 gap-4 mb-6">
                {topSignals.map((s, i) => (
                  <div
                    key={s.symbol}
                    className={`relative overflow-hidden rounded-3xl border bg-[var(--color-surface)]/60 p-6 shadow-xl animate-fade-in-up ${
                      i === 0 ? "border-[var(--color-cta)]/40" : "border-[var(--border)]"
                    }`}
                    style={{ animationDelay: `${i * 60}ms` }}
                  >
                    <div className="absolute -top-16 -right-12 h-32 w-32 rounded-full bg-[var(--color-cta)]/10 blur-2xl" />
                    <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
                      <span>Rank {String(i + 1).padStart(2, "0")}</span>
                      <span className={s.side === "long" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>{s.side}</span>
                    </div>
                    <div className="mt-3 text-[2.15rem] font-black text-[var(--color-text-inverse)] tracking-tight leading-none">
                      {s.symbol}
                    </div>
                    <div className="text-sm text-[var(--color-text-muted)] mt-1 truncate">{s.name || s.symbol}</div>
                    <div className="mt-3 flex items-center justify-between text-sm">
                      <span className={`font-mono font-semibold ${
                        s.predicted_return_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                      }`}>
                        {s.predicted_return_pct >= 0 ? "+" : ""}{s.predicted_return_pct.toFixed(2)}% 21d
                      </span>
                      <span className="text-[var(--color-text-muted)]">Strength {Math.abs(s.strength).toFixed(2)}</span>
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

              {(loading && !hasLoaded) && (
                <div className="flex flex-col gap-2">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="skeleton h-12 rounded-xl" style={{ animationDelay: `${i * 40}ms` }} />
                  ))}
                </div>
              )}

              {(!loading || hasLoaded) && signals.length > 0 && (
                <div className="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--color-surface)]">
                  <div className="min-w-[1120px]">
                    <div className="grid grid-cols-[18rem_8rem_8rem_11rem_9rem_1fr] gap-x-4 px-5 py-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--color-text-secondary)] border-b border-[var(--border)] bg-[var(--color-surface-raised)]">
                      {TABLE_HEADERS.map((h) => (
                        <div
                          key={h}
                          className={`whitespace-nowrap ${h === "Return 21d" ? "text-center justify-self-center" : ""}`}
                        >
                          {h}
                        </div>
                      ))}
                    </div>

                    <div className="flex flex-col gap-4 py-3">
                      {signals.map((s, i) => (
                        <div
                          key={s.symbol}
                          className={`grid grid-cols-[18rem_8rem_8rem_11rem_9rem_1fr] gap-x-4 px-5 py-4.5 items-center rounded-2xl border border-[var(--border)]/50 animate-fade-in-up ${
                            i % 2 === 0 ? "bg-[var(--color-surface-raised)]" : "bg-[var(--color-surface)]"
                          } hover:bg-[var(--color-surface-raised)] transition-colors`}
                          style={{ animationDelay: `${i * 40}ms` }}
                        >
                          <div className="min-w-0">
                            <div className="flex flex-col gap-1 min-w-0">
                              <span className="text-[11px] font-mono text-[var(--color-text-muted)]">#{String(i + 1).padStart(2, "0")}</span>
                              <div className="flex items-baseline gap-2 min-w-0">
                                <span className="font-mono font-bold text-[var(--color-text-inverse)] text-[15px] tracking-[0.06em]">{s.symbol}</span>
                                <span className="text-[var(--color-text-secondary)] text-[13px] truncate">{s.name || s.symbol}</span>
                              </div>
                            </div>
                          </div>

                          <div className="pr-2">
                            <SectorBadge sector={s.sector} />
                          </div>

                          <div className="pr-2">
                            <span className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[12px] font-bold border ${
                              s.side === "long"
                                ? "text-[var(--color-success)] bg-[var(--color-success)]/10 border-[var(--color-success)]/50"
                                : "text-[var(--color-danger)] bg-[var(--color-danger)]/10 border-[var(--color-danger)]/50"
                            }`}>
                              {s.side === "long" ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                              {s.side.toUpperCase()}
                            </span>
                          </div>

                          <div className="pr-2">
                            <StrengthBar value={s.strength} side={s.side} />
                          </div>

                          <div className="pr-2 flex items-center justify-center h-full text-center">
                            <span className={`font-mono font-semibold tabular-nums text-[14px] leading-none whitespace-nowrap ${
                              s.predicted_return_pct >= 0 ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                            }`}>
                              {s.predicted_return_pct >= 0 ? "+" : ""}{s.predicted_return_pct.toFixed(2)}%
                            </span>
                          </div>

                          <div className="pl-1">
                            <ExplanationPills items={s.explanations} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {(!loading || hasLoaded) && signals.length > 0 && <DriverLegend />}

              {(!loading || hasLoaded) && signals.length === 0 && !error && (
                <div className="flex flex-col items-center justify-center py-16 gap-4">
                  <div className="w-14 h-14 rounded-xl bg-[var(--color-surface)] border border-[var(--border)] flex items-center justify-center">
                    <Sparkles size={24} className="text-[var(--color-text-muted)]" />
                  </div>
                  <div className="text-center">
                    <p className="text-[var(--color-text-muted)] text-sm font-semibold">No predictions yet</p>
                    <p className="text-[var(--color-text-secondary)] text-xs mt-1">
                      {hasLoaded ? "Try clearing filters or re-running the model." : "Click Re-run Predictions to generate ML signals."}
                    </p>
                  </div>
                  <button
                    onClick={() => fetchPredictions(false)}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold gradient-accent text-[var(--color-text-inverse)] hover:opacity-90 transition-opacity"
                  >
                    <Sparkles size={13} />
                    Load Predictions
                  </button>
                </div>
              )}
            </Card>

            <div className="mt-4 flex items-start gap-2 px-1 text-[10px] text-[var(--color-text-secondary)] leading-relaxed">
              <Info size={11} className="mt-0.5 shrink-0" />
              <p>
                These predictions are generated by a machine learning model trained on historical price data and are for <strong className="text-[var(--color-text-muted)]">informational purposes only</strong>. Past model performance does not guarantee future results. Always conduct your own research before making any investment decisions.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
