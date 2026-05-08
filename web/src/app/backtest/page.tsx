"use client";

import { useEffect, useRef, useState } from "react";
import { Play, AlertCircle, Info } from "lucide-react";
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
    <div className="max-w-6xl mx-auto px-4 pt-24 pb-24 md:pb-12 flex flex-col gap-6 animate-fade-in">

      {/* Page title */}
      <div>
        <h1 className="text-xl font-bold text-white">Backtest</h1>
        <p className="text-xs text-slate-500 mt-1">
          Configure strategies, risk limits, and date range — then run a full historical backtest.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* ── Left: Configuration panel ─────────────────────────────────── */}
        <div className="lg:col-span-1 flex flex-col gap-5">

          {/* Basic params */}
          <Card>
            <CardHeader title="Parameters" />
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-500 block mb-1">Start Date</label>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-full rounded-lg border border-[#1e2d4a] bg-[#162035] text-sm text-slate-200 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500 block mb-1">End Date</label>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-full rounded-lg border border-[#1e2d4a] bg-[#162035] text-sm text-slate-200 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-slate-500 block mb-1">Initial Capital ($)</label>
                <input
                  type="number"
                  value={initialCapital}
                  min={1000}
                  max={100_000_000}
                  step={1000}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                  className="w-full rounded-lg border border-[#1e2d4a] bg-[#162035] text-sm text-slate-200 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                />
              </div>

              <div>
                <label className="text-xs text-slate-500 block mb-1">Benchmark</label>
                <select
                  value={benchmark}
                  onChange={(e) => setBenchmark(e.target.value)}
                  className="w-full rounded-lg border border-[#1e2d4a] bg-[#162035] text-sm text-slate-200 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
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
            <CardHeader title="Risk Profile" subtitle="Set portfolio-level limits" />
            {presets.length > 0 ? (
              <RiskProfileSelector presets={presets} />
            ) : (
              <div className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-32 w-full" />
              </div>
            )}
          </Card>

          {/* Strategy config */}
          <Card>
            <CardHeader title="Strategies" subtitle="Enable, allocate, and tune each strategy" />
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

          {/* Run button */}
          <Button
            onClick={handleRun}
            loading={isRunning}
            variant={isRunning ? "danger" : "primary"}
            className="w-full py-3 text-sm"
          >
            {isRunning ? (
              <><span className="animate-spin mr-1">⏳</span> Running… (click to cancel)</>
            ) : (
              <><Play size={14} /> Run Backtest</>
            )}
          </Button>

          {/* Server cold-start hint */}
          {serverWarning && (
            <div className="flex items-start gap-2 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-300">
              <Info size={14} className="shrink-0 mt-0.5" />
              <span>
                The server is waking up from sleep — this can take up to 30 seconds on the first request.
                Hang tight!
              </span>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg border border-red-500/30 bg-red-500/10 text-xs text-red-400">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* ── Right: Results panel ──────────────────────────────────────── */}
        <div className="lg:col-span-2 flex flex-col gap-5">

          {/* Loading skeleton */}
          {isRunning && (
            <div className="flex flex-col gap-4 animate-fade-in">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full" />
                ))}
              </div>
              <Skeleton className="h-80 w-full" />
              <Skeleton className="h-56 w-full" />
            </div>
          )}

          {/* Results */}
          {backtestResult && m && !isRunning && (
            <div className="flex flex-col gap-5 animate-fade-in">
              {/* Metrics grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <MetricCard label="Total Return"      value={pct(m.total_return)}      positive={m.total_return > 0} size="lg" />
                <MetricCard label="Sharpe Ratio"      value={num(m.sharpe_ratio)}      positive={null} />
                <MetricCard label="Sortino Ratio"     value={num(m.sortino_ratio)}     positive={null} />
                <MetricCard label="Max Drawdown"      value={pct(m.max_drawdown * -1)} positive={false} />
                <MetricCard label="Win Rate"          value={`${(m.win_rate * 100).toFixed(1)}%`} positive={null} />
                <MetricCard label="Annualised Return" value={pct(m.annualized_return)} positive={m.annualized_return > 0} />
                <MetricCard label="Calmar Ratio"      value={num(m.calmar_ratio)}      positive={null} />
                <MetricCard label="Profit Factor"     value={m.profit_factor > 999 ? "∞" : num(m.profit_factor)} positive={null} />
                <MetricCard label="Total Trades"      value={String(m.total_trades)}   positive={null} sub={`Avg ${m.avg_holding_days}d hold`} />
              </div>

              {/* Charts */}
              <EquityCurveChart data={backtestResult.equity_curve} />
              <DrawdownChart   data={backtestResult.drawdown_curve} />

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
            <div className="flex flex-col items-center justify-center h-80 gap-4 text-center">
              <div className="w-16 h-16 rounded-2xl bg-[#0e1525] border border-[#1e2d4a] flex items-center justify-center">
                <Play size={28} className="text-blue-500/60" />
              </div>
              <p className="text-slate-500 text-sm max-w-xs">
                Configure your risk profile and strategies on the left, then click{" "}
                <span className="text-blue-400">Run Backtest</span> to see results here.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
