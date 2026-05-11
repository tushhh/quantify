"use client";

import { useEffect, useRef, useState } from "react";
import { Play, AlertCircle, Info, ChevronDown, Zap } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { api } from "@/lib/api";
import { RiskProfileSelector } from "@/components/RiskProfileSelector";
import { StrategyConfigurator } from "@/components/StrategyConfigurator";
import { EquityCurveChart, DrawdownChart } from "@/components/Charts";
import { TradeLogTable } from "@/components/TradeLogTable";
import { MetricCard, Card, CardHeader, Button, Skeleton } from "@/components/ui";

// ── Metrics helpers ───────────────────────────────────────────────────────────

function pct(v: number, dp = 2) {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(dp)}%`;
}
function num(v: number, dp = 2) {
  return v.toFixed(dp);
}

// ── Main page ─────────────────────────────────────────────────────────────────

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

  const abortRef = useRef<AbortController | null>(null);
  const [serverWarning, setServerWarning] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch strategy metadata + presets once
  useEffect(() => {
    if (!strategyInfos.length) {
      api.strategies.list().then(setStrategyInfos).catch(() => {});
    }
    if (!presets.length) {
      api.risk.presets().then(setPresets).catch(() => {});
    }
  }, [strategyInfos.length, presets.length, setStrategyInfos, setPresets]);

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

    // Show "waking up server" hint after 8 s (Render cold start)
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
    <div className="min-h-screen pt-28 pb-24 md:pb-12 animate-fade-in">
      {/* Gradient background */}
      <div className="fixed inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 via-transparent to-violet-500/5" />
        <div className="absolute top-0 left-1/3 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl" />
      </div>

      <div className="max-w-7xl mx-auto px-4 flex flex-col gap-8">

        {/* Header */}
        <div className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg gradient-accent">
              <Zap size={20} className="text-white" />
            </div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
              Backtest Engine
            </h1>
          </div>
          <p className="text-slate-400 text-sm">
            Run historical simulations with multiple strategies and analyze performance metrics
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* ── Left: Configuration panel ─────────────────────────────────── */}
          <div className="lg:col-span-1 flex flex-col gap-4">

            {/* Basic parameters - Always visible */}
            <Card className="animate-slide-in-left">
              <CardHeader title="Configuration" subtitle="Quick setup" />
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-slate-400 block mb-1.5">Start Date</label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full rounded-lg glass px-3 py-2 text-xs text-white focus:ring-cyan-500 focus:ring-1"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 block mb-1.5">End Date</label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full rounded-lg glass px-3 py-2 text-xs text-white focus:ring-cyan-500 focus:ring-1"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">Initial Capital ($)</label>
                  <input
                    type="number"
                    value={initialCapital}
                    min={1000}
                    max={100_000_000}
                    step={1000}
                    onChange={(e) => setInitialCapital(Number(e.target.value))}
                    className="w-full rounded-lg glass px-3 py-2 text-xs text-white focus:ring-cyan-500 focus:ring-1"
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-400 block mb-1.5">Benchmark</label>
                  <select
                    value={benchmark}
                    onChange={(e) => setBenchmark(e.target.value)}
                    className="w-full rounded-lg glass px-3 py-2 text-xs text-white focus:ring-cyan-500 focus:ring-1"
                  >
                    <option value="SPY">SPY — S&P 500</option>
                    <option value="QQQ">QQQ — Nasdaq 100</option>
                    <option value="IWM">IWM — Russell 2000</option>
                  </select>
                </div>
              </div>
            </Card>

            {/* Risk profile */}
            <Card className="animate-slide-in-left" style={{ animationDelay: "0.1s" }}>
              <CardHeader title="Risk Profile" subtitle="Portfolio limits" />
              {presets.length > 0 ? (
                <RiskProfileSelector presets={presets} />
              ) : (
                <div className="space-y-2">
                  <Skeleton className="h-16 w-full" />
                  <Skeleton className="h-32 w-full" />
                </div>
              )}
            </Card>

            {/* Advanced toggle */}
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center justify-between px-4 py-3 rounded-lg glass hover:border-cyan-500/50 text-sm font-medium text-slate-300 hover:text-white transition-all"
            >
              <span className="flex items-center gap-2">
                {showAdvanced ? (
                  <Zap size={16} className="text-cyan-400" />
                ) : (
                  <ChevronDown size={16} />
                )}
                Advanced Settings
              </span>
              {showAdvanced && <span className="text-xs bg-cyan-500/20 text-cyan-300 px-2 py-1 rounded">Open</span>}
            </button>

            {/* Advanced section - Collapsible */}
            {showAdvanced && (
              <div className="animate-fade-in-up space-y-4">
                <Card>
                  <CardHeader title="Strategies" subtitle="Enable & allocate" />
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
            <Button
              onClick={handleRun}
              loading={isRunning}
              variant={isRunning ? "danger" : "primary"}
              className="w-full py-3 text-sm font-bold"
            >
              {isRunning ? (
                <><span className="animate-spin">⏳</span> Running… (click to cancel)</>
              ) : (
                <><Play size={16} /> Run Backtest</>
              )}
            </Button>

            {/* Alerts */}
            {serverWarning && (
              <div className="flex items-start gap-2 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-300 animate-fade-in">
                <Info size={14} className="shrink-0 mt-0.5" />
                <span>Server is waking up from sleep — this can take up to 30 seconds.</span>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-xs text-red-300 animate-fade-in">
                <AlertCircle size={14} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* ── Right: Results panel ──────────────────────────────────────── */}
          <div className="lg:col-span-2 flex flex-col gap-6">

            {/* Loading skeleton */}
            {isRunning && (
              <div className="flex flex-col gap-4 animate-fade-in-up">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                  ))}
                </div>
                <Skeleton className="h-80 w-full rounded-lg" />
                <Skeleton className="h-56 w-full rounded-lg" />
              </div>
            )}

            {/* Results */}
            {backtestResult && m && !isRunning && (
              <div className="flex flex-col gap-6 animate-fade-in-up">
                {/* Success banner */}
                <div className="px-4 py-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-xs text-emerald-300 font-medium">Backtest completed successfully</span>
                </div>

                {/* Metrics grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <MetricCard label="Total Return"      value={pct(m.total_return)}      positive={m.total_return > 0} size="lg" />
                  <MetricCard label="Sharpe Ratio"      value={num(m.sharpe_ratio)}      positive={null} />
                  <MetricCard label="Sortino Ratio"     value={num(m.sortino_ratio)}     positive={null} />
                  <MetricCard label="Max Drawdown"      value={pct(m.max_drawdown * -1)} positive={false} />
                  <MetricCard label="Win Rate"          value={`${(m.win_rate * 100).toFixed(1)}%`} positive={null} />
                  <MetricCard label="Ann. Return"       value={pct(m.annualized_return)} positive={m.annualized_return > 0} />
                  <MetricCard label="Calmar Ratio"      value={num(m.calmar_ratio)}      positive={null} />
                  <MetricCard label="Profit Factor"     value={m.profit_factor > 999 ? "∞" : num(m.profit_factor)} positive={null} />
                  <MetricCard label="Total Trades"      value={String(m.total_trades)}   positive={null} sub={`${m.avg_holding_days}d avg`} />
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
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs text-slate-400">
                    {Object.entries(backtestResult.metadata).map(([k, v]) => {
                      if (Array.isArray(v)) return null;
                      return (
                        <div key={k}>
                          <span className="text-slate-600 block capitalize">{k.replace(/_/g, " ")}</span>
                          <span className="font-mono text-slate-300">{String(v)}</span>
                        </div>
                      );
                    })}
                    <div>
                      <span className="text-slate-600 block">Signals generated</span>
                      <span className="font-mono text-slate-300">{backtestResult.signals_count}</span>
                    </div>
                  </div>
                </Card>
              </div>
            )}

            {/* Empty state */}
            {!backtestResult && !isRunning && !error && (
              <div className="flex flex-col items-center justify-center h-96 gap-4 text-center">
                <div className="w-20 h-20 rounded-2xl glass flex items-center justify-center">
                  <Play size={40} className="text-cyan-500/60" />
                </div>
                <div>
                  <p className="text-slate-400 text-sm font-medium">Ready to backtest</p>
                  <p className="text-slate-500 text-xs max-w-xs mt-1">
                    Configure parameters, then click <span className="text-cyan-400">Run Backtest</span>
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

        {/* ── Left: Configuration panel ─────────────────────────────────── */}
  );
}
