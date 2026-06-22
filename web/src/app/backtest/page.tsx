"use client";

import { useEffect, useRef, useState } from "react";
import { Play, Square, AlertCircle, Info, ChevronDown, ChevronUp, Zap, TrendingUp, Cloud } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { api, BASE } from "@/lib/api";
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
    costs, setCosts,
    isRunning, setIsRunning,
    backtestResult, setBacktestResult,
    error, setError,
    buildRequest,
  } = useAppStore();

  const abortRef  = useRef<AbortController | null>(null);
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);
  const esRef     = useRef<EventSource | null>(null);
  const [serverWarning, setServerWarning] = useState(false);
  const [showAdvanced, setShowAdvanced]   = useState(false);
  const [progressMsg, setProgressMsg]     = useState<string | null>(null);
  const [isCloudRun, setIsCloudRun]       = useState(false);

  const dateError = startDate && endDate && startDate >= endDate
    ? "End date must be after start date"
    : null;

  useEffect(() => {
    if (!strategyInfos.length) api.strategies.list().then(setStrategyInfos).catch(() => {});
    if (!presets.length)       api.risk.presets().then(setPresets).catch(() => {});
  }, [strategyInfos.length, presets.length, setStrategyInfos, setPresets]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      esRef.current?.close();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleRun = async () => {
    if (isRunning) {
      abortRef.current?.abort();
      esRef.current?.close();
      setIsRunning(false);
      setIsCloudRun(false);
      setServerWarning(false);
      setProgressMsg(null);
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }

    setError(null);
    setBacktestResult(null);
    setIsRunning(true);
    setIsCloudRun(false);
    setServerWarning(false);
    setProgressMsg("Connecting to engine...");
    timerRef.current = setTimeout(() => setServerWarning(true), 8_000);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    const jobId = `job_${Math.random().toString(36).substring(2, 15)}`;

    // Open SSE for in-process runs; cloud runs will close it immediately
    const es = new EventSource(`${BASE}/api/backtest/stream?job_id=${jobId}`);
    esRef.current = es;
    es.onmessage = (e) => {
      if (e.data === "done") { es.close(); }
      else { setProgressMsg(e.data); }
    };
    es.onerror = () => { es.close(); };

    try {
      const req = buildRequest();
      const submitRes = await api.backtest.submit(req, jobId, ctrl.signal);
      const cloudRun = submitRes.is_cloud_run === true;

      if (cloudRun) {
        es.close();
        setIsCloudRun(true);
        setProgressMsg(null);
        if (timerRef.current) clearTimeout(timerRef.current);
        setServerWarning(false);
      }

      // Poll for result
      const pollInterval = cloudRun ? 5_000 : 1_000;
      while (true) {
        if (ctrl.signal.aborted) return;
        await new Promise((r) => setTimeout(r, pollInterval));
        if (ctrl.signal.aborted) return;
        const pollRes = await api.backtest.pollResult(jobId, ctrl.signal);
        if (pollRes.status === "running") continue;
        setBacktestResult(pollRes);
        break;
      }
    } catch (e: unknown) {
      if (e instanceof Error && (e.name === "AbortError" || e.message === "Aborted")) return;
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setIsRunning(false);
      setIsCloudRun(false);
      setServerWarning(false);
      setProgressMsg(null);
      es.close();
      if (timerRef.current) clearTimeout(timerRef.current);
    }
  };

  const m = backtestResult?.metrics;

  return (
    <div className="min-h-screen pt-12 sm:pt-16 pb-12 sm:pb-16 md:pb-10 animate-fade-in">
      {/* Subtle bg gradient */}
      <div className="fixed inset-0 -z-10 pointer-events-none">
        <div className="absolute inset-0 bg-[var(--color-bg)]" />
        <div className="absolute top-0 left-1/3 w-80 h-80 bg-[var(--color-cta)]/10 rounded-full blur-3xl" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-4 flex flex-col gap-3">

        {/* ── Page header ─────────────────────────────────────────────── */}
        <div className="animate-fade-in-up">
          <div className="flex items-center gap-3 mb-0.5">
            <div className="w-9 h-9 rounded-xl gradient-accent flex items-center justify-center shadow-sm shadow-[var(--color-cta)]/30">
              <Zap size={17} className="text-[var(--color-text-inverse)]" />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-[var(--color-text-primary)]">Backtest engine</h1>
          </div>
          <p className="text-[var(--color-text-muted)] text-xs ml-12 pr-2">
            Simulate strategies on historical data and analyze risk-adjusted performance metrics
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

          {/* ── Left: Config panel ──────────────────────────────────────── */}
          <div className="lg:col-span-1 flex flex-col gap-4 animate-slide-in-left">

            {/* Basic parameters */}
            <Card variant="compact">
              <CardHeader title="Configuration" subtitle="Simulation parameters" density="compact" />
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider font-semibold block mb-1.5">Start Date</label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      className="w-full rounded-lg bg-[var(--color-surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--color-text-primary)] focus:ring-[var(--color-accent)]/40 focus:ring-1 focus:outline-none transition-all"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider font-semibold block mb-1.5">End Date</label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      className="w-full rounded-lg bg-[var(--color-surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--color-text-primary)] focus:ring-[var(--color-accent)]/40 focus:ring-1 focus:outline-none transition-all"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider font-semibold block mb-1.5">Initial Capital ($)</label>
                  <input
                    type="number"
                    value={initialCapital}
                    min={1000}
                    max={100_000_000}
                    step={1000}
                    onChange={(e) => setInitialCapital(Number(e.target.value))}
                    className="w-full rounded-lg bg-[var(--color-surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--color-text-primary)] focus:ring-[var(--color-accent)]/40 focus:ring-1 focus:outline-none transition-all"
                  />
                </div>

                <div>
                  <label className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider font-semibold block mb-1.5">Benchmark</label>
                  <select
                    value={benchmark}
                    onChange={(e) => setBenchmark(e.target.value)}
                    className="w-full rounded-lg bg-[var(--color-surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--color-text-primary)] focus:ring-[var(--color-accent)]/40 focus:ring-1 focus:outline-none transition-all"
                  >
                    <option value="SPY">SPY — S&P 500</option>
                    <option value="QQQ">QQQ — Nasdaq 100</option>
                    <option value="IWM">IWM — Russell 2000</option>
                  </select>
                </div>
              </div>
            </Card>

            {/* Risk profile */}
            <Card variant="compact">
              <CardHeader title="Risk Profile" subtitle="Portfolio limits & position sizing" density="compact" />
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
              className="flex items-center justify-between px-4 py-3 rounded-xl bg-[var(--color-surface)] border border-[var(--border)] hover:border-[var(--border-bright)] text-sm font-medium text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] transition-all"
            >
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider">
                {showAdvanced ? <ChevronUp size={14} className="text-[var(--color-cta)]" /> : <ChevronDown size={14} />}
                Advanced Settings
              </span>
              {showAdvanced && <span className="text-[10px] bg-[var(--color-cta)]/15 text-[var(--color-cta)] px-2 py-0.5 rounded-md border border-[var(--color-cta)]/20">Open</span>}
            </button>

            {showAdvanced && (
              <div className="animate-fade-in-up flex flex-col gap-4">
                <Card variant="compact">
                  <CardHeader title="Trading Costs" subtitle="Slippage, spread, and commission" density="compact" />
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider font-semibold block mb-1.5">Comm. ($/sh)</label>
                      <input
                        type="number"
                        step={0.001}
                        min={0}
                        value={costs.commission_per_share}
                        onChange={(e) => setCosts({ commission_per_share: Number(e.target.value) })}
                        className="w-full rounded-lg bg-[var(--color-surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--color-text-primary)] focus:ring-[var(--color-accent)]/40 focus:ring-1 focus:outline-none transition-all"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider font-semibold block mb-1.5">Spread (bps)</label>
                      <input
                        type="number"
                        step={1}
                        min={0}
                        value={costs.spread_bps}
                        onChange={(e) => setCosts({ spread_bps: Number(e.target.value) })}
                        className="w-full rounded-lg bg-[var(--color-surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--color-text-primary)] focus:ring-[var(--color-accent)]/40 focus:ring-1 focus:outline-none transition-all"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-wider font-semibold block mb-1.5">Slippage (bps)</label>
                      <input
                        type="number"
                        step={1}
                        min={0}
                        value={Math.round(costs.slippage_pct * 10000)}
                        onChange={(e) => setCosts({ slippage_pct: Number(e.target.value) / 10000 })}
                        className="w-full rounded-lg bg-[var(--color-surface-raised)] border border-[var(--border)] px-3 py-2 text-xs text-[var(--color-text-primary)] focus:ring-[var(--color-accent)]/40 focus:ring-1 focus:outline-none transition-all"
                      />
                    </div>
                  </div>
                </Card>

                <Card variant="compact">
                  <CardHeader title="Strategy Allocations" subtitle="Enable strategies & set weights" density="compact" />
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

            {/* Date error */}
            {dateError && (
              <Alert variant="danger">
                <AlertCircle size={13} className="shrink-0 mt-0.5" />
                <span>{dateError}</span>
              </Alert>
            )}

            {/* Run button */}
            <div className="flex flex-col gap-3">
              <button
                onClick={handleRun}
                disabled={!!dateError}
                className={`w-full py-3.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed ${
                  isRunning
                    ? "bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/15"
                    : "gradient-accent text-[var(--color-text-inverse)] shadow-sm shadow-[var(--color-cta)]/30 hover:opacity-90"
                }`}
              >
                {isRunning ? (
                  <><Square size={14} fill="currentColor" /> Stop Backtest</>
                ) : (
                  <><Play size={15} fill="currentColor" /> Run Backtest</>
                )}
              </button>
              {isRunning && !isCloudRun && progressMsg && (
                <div className="text-center text-xs font-mono text-[var(--color-cta)] animate-pulse">
                  {progressMsg}
                </div>
              )}
              {isRunning && isCloudRun && (
                <div className="flex items-center justify-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
                  <Cloud size={11} className="text-[var(--color-cta)]/60" />
                  <span>Polling cloud runner every 5s…</span>
                </div>
              )}
            </div>

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
                {isCloudRun ? (
                  /* Cloud run — no SSE progress, just a status card */
                  <div className="flex flex-col gap-2 px-4 py-4 rounded-xl bg-[var(--color-cta)]/8 border border-[var(--color-cta)]/25">
                    <div className="flex items-center gap-3">
                      <Cloud size={16} className="text-[var(--color-cta)] shrink-0 animate-pulse" />
                      <span className="text-xs text-[var(--color-cta)] font-semibold">Running on cloud runner</span>
                    </div>
                    <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed pl-7">
                      This run was sent to a GitHub Actions runner for extra memory and speed.
                      Results will appear here automatically — no live step progress is available for cloud runs.
                      Typically finishes in <span className="text-[var(--color-text-secondary)]">2–3 minutes</span>.
                    </p>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-[var(--color-cta)]/10 border border-[var(--color-cta)]/20">
                    <div className="w-3.5 h-3.5 border-2 border-[var(--color-cta)]/40 border-t-[var(--color-cta)] rounded-full animate-spin shrink-0" />
                    <span className="text-xs text-[var(--color-cta)] font-medium">Running simulation…</span>
                  </div>
                )}
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
                <div className="flex items-center gap-2.5 px-4 py-3 rounded-xl bg-[var(--color-success)]/10 border border-[var(--color-success)]/20">
                  <div className="w-2 h-2 rounded-full bg-[var(--color-success)] animate-pulse shrink-0" />
                  <span className="text-xs text-[var(--color-success)] font-semibold">Backtest completed successfully</span>
                </div>

                {/* Key metrics */}
                <div>
                  <p className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-widest font-semibold mb-2">Performance Metrics</p>
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

                {/* Strategy breakdown */}
                {backtestResult.trades.length > 0 && (() => {
                  const byStrategy = backtestResult.trades.reduce((acc: Record<string, { trades: number; wins: number; pnl: number }>, t: any) => {
                    const k = t.strategy_name || "unknown";
                    if (!acc[k]) acc[k] = { trades: 0, wins: 0, pnl: 0 };
                    acc[k].trades++;
                    acc[k].pnl += t.pnl;
                    if (t.pnl > 0) acc[k].wins++;
                    return acc;
                  }, {} as Record<string, { trades: number; wins: number; pnl: number }>);
                  const rows = Object.entries(byStrategy).sort((a: any, b: any) => b[1].pnl - a[1].pnl);
                  return (
                    <Card>
                        <CardHeader className="p-4 pb-0">
                          <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Strategy Breakdown</h3>
                          <p className="text-xs text-[var(--color-text-muted)]">P&L and win rate per strategy</p>
                        </CardHeader>
                        <div className="overflow-x-auto -mx-1 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface)]">
                          <table className="w-full text-sm min-w-[420px]">
                            <thead>
                              <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface-raised)]">
                                {["Strategy", "Trades", "Win Rate", "Total P&L"].map(h => (
                                  <th key={h} className="align-middle text-left px-3 py-3 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-[var(--color-border-subtle)]">
                              {rows.map(([name, s]: [string, any]) => {
                                const isPos = s.pnl >= 0;
                                return (
                                  <tr key={name} className="hover:bg-[var(--color-surface-raised)] transition-colors">
                                    <td className="px-3 py-2.5 text-[var(--color-text-primary)] capitalize">{name.replace(/_/g, " ")}</td>
                                    <td className="px-3 py-2.5 text-[var(--color-text-secondary)] tabular-nums">{s.trades}</td>
                                    <td className="px-3 py-2.5 tabular-nums text-[var(--color-text-primary)]">{((s.wins / s.trades) * 100).toFixed(0)}%</td>
                                    <td className={`px-3 py-2.5 font-mono font-semibold tabular-nums ${isPos ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}`}>
                                      {isPos ? "+" : ""}${s.pnl.toFixed(0)}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </Card>
                  );
                })()}

                {/* Trade log */}
                {backtestResult.trades.length > 0 && (
                  <TradeLogTable trades={backtestResult.trades} />
                )}

                {/* Metadata */}
                <Card variant="compact">
                  <CardHeader title="Run Metadata" density="compact" />
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                    {Object.entries(backtestResult.metadata).map(([k, v]) => {
                      if (Array.isArray(v)) return null;
                      return (
                        <div key={k}>
                          <span className="text-[var(--color-text-secondary)] block capitalize text-[10px] uppercase tracking-wider">{k.replace(/_/g, " ")}</span>
                          <span className="font-mono text-[var(--color-text-primary)] text-sm">{String(v)}</span>
                        </div>
                      );
                    })}
                    <div>
                      <span className="text-[var(--color-text-secondary)] block text-[10px] uppercase tracking-wider">Signals generated</span>
                      <span className="font-mono text-[var(--color-text-primary)] text-sm">{backtestResult.signals_count}</span>
                    </div>
                  </div>
                </Card>
              </div>
            )}

            {/* Empty state */}
            {!backtestResult && !isRunning && !error && (
              <div className="flex flex-col items-center justify-center h-96 gap-5">
                <div className="w-20 h-20 rounded-2xl bg-[var(--color-surface)] border border-[var(--border)] flex items-center justify-center">
                  <TrendingUp size={36} className="text-[var(--color-cta)]/40" />
                </div>
                <div className="text-center">
                  <p className="text-[var(--color-text-secondary)] text-sm font-semibold">Ready to run</p>
                  <p className="text-[var(--color-text-muted)] text-xs mt-1.5 max-w-xs">
                    Configure parameters on the left, then click{" "}
                    <span className="text-[var(--color-cta)] font-semibold">Run Backtest</span>
                  </p>
                </div>
                <div className="flex gap-3 text-[10px] text-[var(--color-text-secondary)]">
                  <span className="px-2.5 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">Up to 3 years of data</span>
                  <span className="px-2.5 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">6 strategies</span>
                  <span className="px-2.5 py-1.5 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">Full risk controls</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
