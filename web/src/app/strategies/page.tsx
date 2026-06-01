"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp, BarChart2 } from "lucide-react";
import clsx from "clsx";
import { api } from "@/lib/api";
import type { StrategyInfo } from "@/lib/api";
import { Card, Skeleton, Badge } from "@/components/ui";

const STRATEGY_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  trend_following:          { text: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
  cross_sectional_momentum: { text: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
  pairs_mean_reversion:     { text: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
  quality_value:            { text: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
  ml_return_predictor:      { text: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
  volatility_regime:        { text: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" },
};

const DEFAULT_COLOR = { text: "text-[var(--color-text-secondary)]", bg: "bg-[var(--color-surface-raised)]", border: "border-[var(--border)]" };

function StrategyCard({ info }: { info: StrategyInfo }) {
  const [open, setOpen] = useState(false);
  const c = STRATEGY_COLORS[info.name] ?? DEFAULT_COLOR;

  return (
    <Card variant="compact" className="overflow-hidden hover:border-[var(--border-bright)] transition-all">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-4 p-5 text-left hover:bg-[var(--color-surface)] transition-colors"
      >
        <div className={clsx("px-2.5 py-1 rounded-lg border text-xs font-bold shrink-0", c.text, c.bg, c.border)}>
          {(info.default_allocation * 100).toFixed(0)}%
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[var(--color-text-inverse)]">{info.label}</p>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-1">{info.description}</p>
        </div>
        <span className="text-[10px] text-[var(--color-text-secondary)] mr-1 hidden sm:block">{info.params.length} params</span>
        <div className="shrink-0 text-[var(--color-text-secondary)]">
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </div>
      </button>

      {open && (
        <div className="border-t border-[var(--border)] p-5 flex flex-col gap-4 animate-fade-in bg-[var(--color-surface)]/30">
          <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{info.description}</p>

          {info.params.length > 0 && (
            <div>
              <p className="text-[10px] text-[var(--color-text-secondary)] uppercase tracking-widest mb-3 font-semibold">Configurable Parameters</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {info.params.map((p) => (
                  <div key={p.key} className="flex flex-col gap-1 p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-medium text-[var(--color-text-primary)] truncate">{p.label}</span>
                      <Badge variant="blue">{p.type}</Badge>
                    </div>
                    <span className="text-[10px] text-[var(--color-text-secondary)] font-mono">
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
    </Card>
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
            <BarChart2 size={15} className="text-[var(--color-text-inverse)]" />
          </div>
          <h1 className="text-xl font-bold text-[var(--color-text-inverse)]">Strategies</h1>
        </div>
        <p className="text-xs text-[var(--color-text-muted)] ml-10.5">
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
                ? "bg-[var(--color-cta)]/15 border-[var(--color-cta)]/30 text-[var(--color-cta)]"
                : "border-[var(--border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] hover:bg-[var(--color-surface)]"
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
          <div className="w-12 h-12 rounded-xl bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/20 flex items-center justify-center">
            <ChevronDown size={20} className="text-[var(--color-danger)]" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--color-danger)]">Failed to load strategies</p>
            <p className="text-xs text-[var(--color-text-secondary)] mt-1">{error}</p>
          </div>
          <button
            onClick={fetchStrategies}
            className="text-xs text-[var(--color-cta)] hover:text-[var(--color-accent)] font-semibold transition-colors border border-[var(--color-cta)]/20 px-4 py-2 rounded-lg hover:bg-[var(--color-cta)]/10"
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
              <div key={s.name} className="rounded-xl border border-[var(--border)] bg-[var(--color-surface)] p-5">
                <div className="flex items-center gap-3 mb-4">
                  <div className={clsx("px-2.5 py-1 rounded-lg border text-xs font-bold shrink-0", c.text, c.bg, c.border)}>
                    {(s.default_allocation * 100).toFixed(0)}%
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[var(--color-text-primary)]">{s.label}</p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-1">{s.description}</p>
                  </div>
                </div>
                {s.params.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {s.params.map((p) => (
                      <div key={p.key} className="flex flex-col gap-1 p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--border)]">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-medium text-[var(--color-text-primary)] truncate">{p.label}</span>
                          <Badge variant="default">{p.type}</Badge>
                        </div>
                        <span className="text-[10px] text-[var(--color-text-secondary)] font-mono">
                          default: {String(p.default)}
                          {p.min !== undefined && p.max !== undefined && ` · ${p.min}–${p.max}`}
                        </span>
                        {p.description && <span className="text-[10px] text-[var(--color-text-muted)] leading-snug">{p.description}</span>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[var(--color-text-secondary)]">No configurable parameters.</p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Info footer */}
      <Card variant="compact">
        <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">
          All strategy parameters are fully configurable on the{" "}
          <a href="/backtest" className="text-[var(--color-cta)] hover:text-[var(--color-accent)] transition-colors">Backtest</a> page.
          Allocations must sum to 100% across enabled strategies.
          The <strong className="text-[var(--color-text-primary)]">Volatility Regime</strong> strategy dynamically
          re-weights other strategies based on VIX levels — it works best when multiple strategies are enabled.
        </p>
      </Card>
    </div>
  );
}
