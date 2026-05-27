"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, BarChart2 } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import type { StrategyInfo } from "@/lib/api";
import { Card, Skeleton, Badge } from "@/components/ui";

const STRATEGY_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  trend_following:          { text: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/25" },
  cross_sectional_momentum: { text: "text-purple-400",  bg: "bg-purple-500/10",  border: "border-purple-500/25" },
  pairs_mean_reversion:     { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/25" },
  quality_value:            { text: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/25" },
  ml_return_predictor:      { text: "text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/25" },
  volatility_regime:        { text: "text-cyan-400",    bg: "bg-cyan-500/10",    border: "border-cyan-500/25" },
};

const DEFAULT_COLOR = { text: "text-slate-400", bg: "bg-slate-500/10", border: "border-slate-500/25" };

function StrategyCard({ info }: { info: StrategyInfo }) {
  const [open, setOpen] = useState(false);
  const c = STRATEGY_COLORS[info.name] ?? DEFAULT_COLOR;

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] overflow-hidden hover:border-[var(--border-bright)] transition-all">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className={clsx("px-2.5 py-1 rounded-lg border text-xs font-bold shrink-0", c.text, c.bg, c.border)}>
          {(info.default_allocation * 100).toFixed(0)}%
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white">{info.label}</p>
          <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{info.description}</p>
        </div>
        <span className="text-[10px] text-slate-600 mr-1 hidden sm:block">{info.params.length} params</span>
        <div className="shrink-0 text-slate-600">
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </div>
      </button>

      {open && (
        <div className="border-t border-[var(--border)] p-5 flex flex-col gap-4 animate-fade-in bg-[var(--bg)]/30">
          <p className="text-sm text-slate-400 leading-relaxed">{info.description}</p>

          {info.params.length > 0 && (
            <div>
              <p className="text-[10px] text-slate-600 uppercase tracking-widest mb-3 font-semibold">Configurable Parameters</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {info.params.map((p) => (
                  <div key={p.key} className="flex flex-col gap-1 p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium text-slate-300 truncate">{p.label}</span>
                      <Badge variant="blue">{p.type}</Badge>
                    </div>
                    <span className="text-[10px] text-slate-600 font-mono">
                      default: {String(p.default)}
                      {p.min !== undefined && p.max !== undefined && ` · ${p.min}–${p.max}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [view, setView]             = useState<"overview" | "params">("overview");

  const fetchStrategies = () => {
    setLoading(true);
    setError(null);
    api.strategies.list()
      .then(setStrategies)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load strategies"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchStrategies();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 pt-20 pb-24 md:pb-12 flex flex-col gap-6 animate-fade-in">

      {/* Header */}
      <div>
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center">
            <BarChart2 size={15} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-white">Strategies</h1>
        </div>
        <p className="text-xs text-slate-500 ml-10.5">
          Six production-ready quantitative strategies — click any card to explore configurable parameters.
        </p>
      </div>

      {/* View toggle */}
      <div className="flex items-center gap-2">
        {(["overview", "params"] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            className={clsx(
              "px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider border transition-all",
              view === v
                ? "bg-blue-500/15 border-blue-400/30 text-blue-200"
                : "border-[var(--border)] text-slate-400 hover:text-white hover:bg-white/[0.03]"
            )}
          >
            {v === "overview" ? "Overview" : "All Parameters"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[68px] w-full" />
          ))}
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
          <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
            <ChevronDown size={20} className="text-red-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-red-300">Failed to load strategies</p>
            <p className="text-xs text-slate-600 mt-1">{error}</p>
          </div>
          <button
            onClick={fetchStrategies}
            className="text-xs text-blue-400 hover:text-blue-300 font-semibold transition-colors border border-blue-500/20 px-4 py-2 rounded-lg hover:bg-blue-500/10"
          >
            Try again
          </button>
        </div>
      ) : view === "overview" ? (
        <div className="flex flex-col gap-3">
          {strategies.map((s) => <StrategyCard key={s.name} info={s} />)}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {strategies.map((s) => {
            const c = STRATEGY_COLORS[s.name] ?? DEFAULT_COLOR;
            return (
              <div key={s.name} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
                <div className="flex items-center gap-3 mb-4">
                  <div className={clsx("px-2.5 py-1 rounded-lg border text-xs font-bold shrink-0", c.text, c.bg, c.border)}>
                    {(s.default_allocation * 100).toFixed(0)}%
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{s.label}</p>
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{s.description}</p>
                  </div>
                </div>
                {s.params.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {s.params.map((p) => (
                      <div key={p.key} className="flex flex-col gap-1 p-3 rounded-lg bg-[var(--bg)] border border-[var(--border)]">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-slate-300 truncate">{p.label}</span>
                          <Badge variant="blue">{p.type}</Badge>
                        </div>
                        <span className="text-[10px] text-slate-600 font-mono">
                          default: {String(p.default)}
                          {p.min !== undefined && p.max !== undefined && ` · ${p.min}–${p.max}`}
                        </span>
                        {p.description && <span className="text-[10px] text-slate-500 leading-snug">{p.description}</span>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-600">No configurable parameters.</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Info footer */}
      <Card>
        <p className="text-xs text-slate-500 leading-relaxed">
          All strategy parameters are fully configurable on the{" "}
          <a href="/backtest" className="text-blue-400 hover:text-blue-300 transition-colors">Backtest</a> page.
          Allocations must sum to 100% across enabled strategies.
          The <strong className="text-slate-300">Volatility Regime</strong> strategy dynamically
          re-weights other strategies based on VIX levels — it works best when multiple strategies are enabled.
        </p>
      </Card>
    </div>
  );
}
