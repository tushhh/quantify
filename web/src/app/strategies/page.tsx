"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import type { StrategyInfo } from "@/lib/api";
import { Card, Skeleton, Badge } from "@/components/ui";

const STRATEGY_COLORS: Record<string, string> = {
  trend_following:          "text-blue-400   bg-blue-500/10   border-blue-500/30",
  cross_sectional_momentum: "text-violet-400 bg-violet-500/10 border-violet-500/30",
  pairs_mean_reversion:     "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  quality_value:            "text-amber-400  bg-amber-500/10  border-amber-500/30",
  ml_return_predictor:      "text-rose-400   bg-rose-500/10   border-rose-500/30",
  volatility_regime:        "text-cyan-400   bg-cyan-500/10   border-cyan-500/30",
};

function StrategyCard({ info }: { info: StrategyInfo }) {
  const [open, setOpen] = useState(false);
  const color = STRATEGY_COLORS[info.name] ?? "text-slate-400 bg-slate-500/10 border-slate-500/30";

  return (
    <div className="rounded-xl border border-[#1e2d4a] bg-[#0e1525] overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className={clsx("px-2.5 py-1 rounded-lg border text-xs font-bold shrink-0", color)}>
          {(info.default_allocation * 100).toFixed(0)}%
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-white">{info.label}</p>
          <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{info.description}</p>
        </div>
        <div className="shrink-0 text-slate-600">
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="border-t border-[#1e2d4a] p-5 flex flex-col gap-4 animate-fade-in">
          <p className="text-sm text-slate-400 leading-relaxed">{info.description}</p>

          <div>
            <p className="text-xs text-slate-600 uppercase tracking-wider mb-3 font-semibold">Configurable Parameters</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {info.params.map((p) => (
                <div key={p.key} className="flex flex-col gap-0.5 p-3 rounded-lg bg-[#070b14] border border-[#1e2d4a]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-300">{p.label}</span>
                    <Badge variant="blue">{p.type}</Badge>
                  </div>
                  <span className="text-[10px] text-slate-600 font-mono">
                    default: {String(p.default)}
                    {p.min !== undefined && p.max !== undefined && ` | range: ${p.min}–${p.max}`}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"overview" | "params">("overview");

  useEffect(() => {
    api.strategies.list()
      .then(setStrategies)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 pt-24 pb-24 md:pb-12 flex flex-col gap-6 animate-fade-in">
      <div>
        <h1 className="text-xl font-bold text-white">Strategies</h1>
        <p className="text-xs text-slate-500 mt-1">
          Six production-ready quantitative strategies — click any card to explore configurable parameters.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setView("overview")}
          className={clsx(
            "px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider border transition-all",
            view === "overview"
              ? "bg-blue-500/20 border-blue-400/40 text-blue-200"
              : "border-white/10 text-slate-400 hover:text-white"
          )}
        >
          Overview
        </button>
        <button
          type="button"
          onClick={() => setView("params")}
          className={clsx(
            "px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider border transition-all",
            view === "params"
              ? "bg-violet-500/20 border-violet-400/40 text-violet-200"
              : "border-white/10 text-slate-400 hover:text-white"
          )}
        >
          Parameters
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : view === "overview" ? (
        <div className="flex flex-col gap-3">
          {strategies.map((s) => (
            <StrategyCard key={s.name} info={s} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {strategies.map((s) => (
            <div key={s.name} className="rounded-xl border border-[#1e2d4a] bg-[#0e1525] p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-white">{s.label}</p>
                <span className="text-xs text-slate-500">{(s.default_allocation * 100).toFixed(0)}% default</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {s.params.map((p) => (
                  <div key={p.key} className="flex flex-col gap-0.5 p-3 rounded-lg bg-[#070b14] border border-[#1e2d4a]">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-300">{p.label}</span>
                      <Badge variant="blue">{p.type}</Badge>
                    </div>
                    <span className="text-[10px] text-slate-600 font-mono">
                      default: {String(p.default)}
                      {p.min !== undefined && p.max !== undefined && ` | range: ${p.min}–${p.max}`}
                    </span>
                    <span className="text-[10px] text-slate-500">{p.description}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info card */}
      <Card>
        <p className="text-xs text-slate-500 leading-relaxed">
          All strategy parameters are fully configurable on the{" "}
          <a href="/backtest" className="text-blue-400 hover:underline">Backtest</a> page.
          Allocations must sum to 100% across enabled strategies.
          The <strong className="text-slate-300">Volatility Regime</strong> strategy dynamically
          re-weights the other strategies based on VIX levels — it works best when other strategies are enabled.
        </p>
      </Card>
    </div>
  );
}
