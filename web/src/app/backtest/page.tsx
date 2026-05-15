"use client";

import { useEffect, useRef, useState } from "react";
import { Play, Square, AlertCircle, Info, ChevronDown, ChevronUp, Zap, TrendingUp } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";
import { RiskProfileSelector } from "@/components/RiskProfileSelector";
import { StrategyConfigurator } from "@/components/StrategyConfigurator";
import { EquityCurveChart, DrawdownChart } from "@/components/Charts";
import { TradeLogTable } from "@/components/TradeLogTable";
import { MetricCard, Card, CardHeader, Button, Skeleton, Alert } from "@/components/ui";

function pct(v: number, dp = 2) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(dp)}%`;
}
function num(v: number, dp = 2) {
  return v.toFixed(dp);
}

export default function BacktestPage() {
  const {
    strategyInfos, setStrategyInfos,
    presets, setPresets,
    startDate, setStartDate,
    endDate, setEndDate,
    initialCapital, setInitialCapital,
    benchmark, setBenchmark,
    isRunning, setIsRunning,
    backtestResult, setBacktestResult,
    error, setError,
    buildRequest,
  } = useAppStore();

  const abortRef  = useRef<AbortController | null>(null);
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [serverWarning, setServerWarning] = useState(false);
  const [showAdvanced, setShowAdvanced]   = useState(false);

  useEffect(() => {
    if (!strategyInfos.length) api.strategies.list().then(setStrategyInfos).catch(() => {});
    if (!presets.length)       api.risk.presets().then(setPresets).catch(() => {});
  }, [strategyInfos.length, presets.length, setStrategyInfos, setPresets]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleRun = async () => {
    if (isRunning) {
      abortRef.current?.abort();
      setIsRunning(false);
      setServerWarning(false);
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    setError(null);
    setBacktestResult(null);
    setIsRunning(true);
    setServerWarning(false);
    timerRef.current = setTimeout(() => setServerWarning(true), 8_000);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const req = buildRequest();
      const res = await api.backtest.run(req, ctrl.signal);
      setBacktestResult(res);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setIsRunning(false);
      setServerWarning(false);
      if (timerRef.current) clearTimeout(timerRef.current);
    }
  };

  const m = backtestResult?.metrics;

  return (
    <div className="min-h-screen pt-20 pb-24 md:pb-12 animate-fade-in">
      {/* Subtle bg gradient */}
      <div className="fixed inset-0 -z-10 pointer-events-none">
        <div className="absolute inset-0 bg-[var(--bg)]" />
        <div className="absolute top-0 left-1/3 w-80 h-80 bg-blue-600/5 rounded-full blur-3xl" />
      </div>

      <div className="max-w-7xl mx-auto px-4 flex flex-col gap-6">

        {/* ── Page header ─────────────────────────────────────────────── */}
        <div className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-9 h-9 rounded-xl gradient-accent flex items-center justify-center shadow-sm shadow-blue-900/30">
              <Zap size={17} className="text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white">Backtest Engine</h1>
          </div>
          <p className="text-slate-500 text-xs ml-12">
            Simulate strategies on historical data and analyze risk-adjusted performance metrics
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── Left: Config panel ──────────────────────────────────────── */}
          <div className="lg:col-span-1 flex flex-col gap-4 animate-slide-in-left">

            {/* Basic parameters */}
            <Card>
              <CardHeader title="Configuration" subtitle="Simulation parameters" />
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1.5">Start Date</label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full rounded-lg bg-[var(--surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-white focus:ring-blue-500/40 focus:ring-1 focus:outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1.5">End Date</label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full rounded-lg bg-[var(--surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-white focus:ring-blue-500/40 focus:ring-1 focus:outline-none transition-all"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1.5">Initial Capital ($)</label>
                  <input
                    type="number"
                    value={initialCapital}
                    min={1000}
                    max={100_000_000}
                    step={1000}
                    onChange={(e) => setInitialCapital(Number(e.target.value))}
                    className="w-full rounded-lg bg-[var(--surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-white focus:ring-blue-500/40 focus:ring-1 focus:outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block mb-1.5">Benchmark</label>
                  <select
                    value={benchmark}
                    onChange={(e) => setBenchmark(e.target.value)}
                    className="w-full rounded-lg bg-[var(--surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-white focus:ring-blue-500/40 focus:ring-1 focus:outline-none transition-all"
                  >
                    <option value="SPY">SPY — S&P 500</option>
                    <option value="QQQ">QQQ — Nasdaq 100</option>
                    <option value="IWM">IWM — Russell 2000</option>
                  </select>
                </div>
              </div>
            </Card>

            {/* Risk profile */}
            <Card>
              <CardHeader title="Risk Profile" subtitle="Portfolio limits & position sizing" />
              {presets.length > 0 ? (
                <RiskProfileSelector presets={presets} />
              ) : (
                <div className="space-y-2">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-36 w-full" />
                </div>
              )}
            </Card>

            {/* Advanced toggle */}
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between px-4 py-3 rounded-xl bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--border-bright)] text-sm font-medium text-slate-300 hover:text-white transition-all"
            >
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider">
                {showAdvanced ? <ChevronUp size={14} className="text-blue-400" /> : <ChevronDown size={14} />}
                Advanced — Strategy Overrides
              </span>
              {showAdvanced && <span className="text-[10px] bg-blue-500/15 text-blue-300 px-2 py-0.5 rounded-md border border-blue-500/20">Open</span>}
            </button>

            {showAdvanced && (
              <div className="animate-fade-in-up flex flex-col gap-4">
                <Card>
                  <CardHeader title="Strategy Allocations" subtitle="Enable strategies & set weights" />
                  {strategyInfos.length > 0 ? (
                    <StrategyConfigurator strategies={strategyInfos} />
                  ) : (
                    <div className="space-y-2">
                      {Array.from({ length: 6 }).map((_, i) => (
                        <Skeleton key={i} className="h-12 w-full" />
                      ))}
                    </div>
                  )}
                </Card>
              </div>
            )}

            {/* Run button */}
            <button
              onClick={handleRun}
              className={`w-full py-3.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.98] ${
                isRunning
                  ? "bg-red-500/10 border border-red-500/30 text-red-300 hover:bg-red-500/15"
                  : "gradient-accent text-white shadow-sm shadow-blue-900/30 hover:opacity-90"
              }`}
            >
              {isRunning ? (
                <><Square size={14} fill="currentColor" /> Stop Backtest</>
              ) : (
                <><Play size={15} fill="currentColor" /> Run Backtest</>
              )}
            </button>

            {/* Alerts */}
            {serverWarning && (
              <Alert variant="warning">
                <Info size={13} className="shrink-0 mt-0.5" />
                <span>Server is waking from sleep — this first request may take 30+ seconds.</span>
              </Alert>
            )}

            {error && (
              <Alert variant="danger">
                <AlertCircle size={13} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </Alert>
            )}
          </div>

          {/* ── Right: Results panel ─────────────────────────────────────── */}
          <div className="lg:col-span-2 flex flex-col gap-5">

            {/* Running skeleton */}
            {isRunning && (
              <div className="flex flex-col gap-4 animate-fade-in-up">
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <div className="w-3.5 h-3.5 border-2 border-blue-400/40 border-t-blue-400 rounded-full animate-spin shrink-0" />
                  <span className="text-xs text-blue-300 font-medium">Running simulation…</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {Array.from({ length: 9 }).map((_, i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
                <Skeleton className="h-72 w-full rounded-xl" />
                <Skeleton className="h-52 w-full rounded-xl" />
              </div>
            )}

            {/* Results */}
            {backtestResult && m && !isRunning && (
              <div className="flex flex-col gap-5 animate-fade-in-up">
                {/* Success banner */}
                <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
                  <span className="text-xs text-emerald-300 font-semibold">Backtest completed successfully</span>
                </div>

                {/* Key metrics */}
                <div>
                  <p className="text-[10px] text-slate-600 uppercase tracking-widest font-semibold mb-2">Performance Metrics</p>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <MetricCard label="Total Return"   value={pct(m.total_return)}      positive={m.total_return > 0} size="lg" />
                    <MetricCard label="Ann. Return"    value={pct(m.annualized_return)} positive={m.annualized_return > 0} />
                    <MetricCard label="Sharpe Ratio"   value={num(m.sharpe_ratio)}      positive={null} />
                    <MetricCard label="Sortino Ratio"  value={num(m.sortino_ratio)}     positive={null} />
                    <MetricCard label="Max Drawdown"   value={pct(m.max_drawdown * -1)} positive={false} />
                    <MetricCard label="Win Rate"       value={`${(m.win_rate * 100).toFixed(1)}%`} positive={null} />
                    <MetricCard label="Calmar Ratio"   value={num(m.calmar_ratio)}      positive={null} />
                    <MetricCard label="Profit Factor"  value={m.profit_factor > 999 ? "∞" : num(m.profit_factor)} positive={null} />
                    <MetricCard label="Total Trades"   value={String(m.total_trades)}   positive={null} sub={`${m.avg_holding_days}d avg hold`} />
                  </div>
                </div>

                {/* Charts */}
                <EquityCurveChart data={backtestResult.equity_curve} />
                <DrawdownChart data={backtestResult.drawdown_curve} />

                {/* Trade log */}
                {backtestResult.trades.length > 0 && (
                  <TradeLogTable trades={backtestResult.trades} />
                )}

                {/* Metadata */}
                <Card>
                  <CardHeader title="Run Metadata" />
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                    {Object.entries(backtestResult.metadata).map(([k, v]) => {
                      if (Array.isArray(v)) return null;
                      return (
                        <div key={k}>
                          <span className="text-slate-600 block capitalize text-[10px] uppercase tracking-wider">{k.replace(/_/g, " ")}</span>
                          <span className="font-mono text-slate-300 text-sm">{String(v)}</span>
                        </div>
                      );
                    })}
                    <div>
                      <span className="text-slate-600 block text-[10px] uppercase tracking-wider">Signals generated</span>
                      <span className="font-mono text-slate-300 text-sm">{backtestResult.signals_count}</span>
                    </div>
                  </div>
                </Card>
              </div>
            )}

            {/* Empty state */}
            {!backtestResult && !isRunning && !error && (
              <div className="flex flex-col items-center justify-center h-96 gap-5">
                <div className="w-20 h-20 rounded-2xl bg-[var(--surface)] border border-[var(--border)] flex items-center justify-center">
                  <TrendingUp size={36} className="text-blue-500/40" />
                </div>
                <div className="text-center">
                  <p className="text-slate-400 text-sm font-semibold">Ready to run</p>
                  <p className="text-slate-600 text-xs mt-1.5 max-w-xs">
                    Configure parameters on the left, then click{" "}
                    <span className="text-blue-400 font-semibold">Run Backtest</span>
                  </p>
                </div>
                <div className="flex gap-3 text-[10px] text-slate-600">
                  <span className="px-2.5 py-1.5 rounded-lg bg-[var(--surface)] border border-[var(--border)]">Up to 3 years of data</span>
                  <span className="px-2.5 py-1.5 rounded-lg bg-[var(--surface)] border border-[var(--border)]">6 strategies</span>
                  <span className="px-2.5 py-1.5 rounded-lg bg-[var(--surface)] border border-[var(--border)]">Full risk controls</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
