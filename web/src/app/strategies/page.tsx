"use client";

import PageHeader from "@/components/layout/page-header";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import clsx from "clsx";
import { api, errorMessage } from "@/lib/api";
import type { ParamSpec, StrategyInfo } from "@/lib/api";

const formatDefault = (p: ParamSpec) =>
  p.type === "bool" ? (p.default ? "On" : "Off") : String(p.default);

const formatRange = (p: ParamSpec) =>
  p.type === "select" && p.options?.length ? p.options.join(", ")
    : p.min != null && p.max != null ? `${p.min} to ${p.max}` : "–";

function StrategyRow({ info, open, onToggle }: { info: StrategyInfo; open: boolean; onToggle: () => void }) {
  const panelId = `strategy-${info.name}`;
  return (
    <li className="border-t border-[var(--color-border)] first:border-t-0">
      <button
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="w-full grid grid-cols-[minmax(0,1fr)_auto] sm:grid-cols-[minmax(0,1fr)_9rem_6rem_auto] items-center gap-x-6 gap-y-1 px-4 py-3 text-left hover:bg-[var(--color-surface)]"
      >
        <span className="min-w-0">
          <span className="block text-sm font-medium text-[var(--color-text-primary)]">{info.label}</span>
          <span className={clsx("block text-xs text-[var(--color-text-secondary)] mt-0.5", !open && "line-clamp-1")}>{info.description}</span>
        </span>
        <span className="hidden sm:block text-right text-xs text-[var(--color-text-secondary)]">
          <span className="font-mono text-sm text-[var(--color-text-primary)]">{(info.default_allocation * 100).toFixed(0)}%</span> of capital
        </span>
        <span className="hidden sm:block text-right text-xs text-[var(--color-text-secondary)]">
          <span className="font-mono">{info.params.length}</span> settings
        </span>
        <ChevronDown aria-hidden className={clsx("h-4 w-4 text-[var(--color-text-secondary)] transition-transform", open && "rotate-180")} />
      </button>

      {open && (
        <div id={panelId} className="px-4 pb-4">
          {info.params.length ? (
            <table className="w-full text-left text-xs">
              <thead className="text-[var(--color-text-secondary)]">
                <tr className="border-b border-[var(--color-border)]">
                  <th scope="col" className="py-2 pr-4 font-normal">Setting</th>
                  <th scope="col" className="py-2 pr-4 font-normal text-right">Default</th>
                  <th scope="col" className="py-2 pr-4 font-normal text-right">Allowed range</th>
                  <th scope="col" className="hidden md:table-cell py-2 font-normal">What it does</th>
                </tr>
              </thead>
              <tbody>
                {info.params.map((p) => (
                  <tr key={p.key} className="border-b border-[var(--color-border)]/50 last:border-b-0 align-top">
                    <td className="py-2 pr-4 text-[var(--color-text-primary)]">{p.label}</td>
                    <td className="py-2 pr-4 text-right font-mono text-[var(--color-text-primary)]">{formatDefault(p)}</td>
                    <td className="py-2 pr-4 text-right font-mono text-[var(--color-text-secondary)] whitespace-nowrap">{formatRange(p)}</td>
                    <td className="hidden md:table-cell py-2 text-[var(--color-text-secondary)] leading-relaxed">{p.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-xs text-[var(--color-text-secondary)]">This strategy has no settings to change.</p>
          )}
          <Link href="/backtest" className="mt-3 inline-block text-xs font-medium text-[var(--color-accent)] hover:underline">
            Change these in a backtest
          </Link>
        </div>
      )}
    </li>
  );
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Set<string>>(new Set());

  const fetchStrategies = useCallback(() => {
    setLoading(true);
    setError(null);
    api.strategies.list()
      .then(setStrategies)
      .catch((e) => setError(errorMessage(e, "The strategies couldn't be loaded. Try again in a minute.")))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchStrategies(); }, [fetchStrategies]);

  const allOpen = strategies.length > 0 && open.size === strategies.length;
  const toggle = (name: string) => setOpen((prev) => {
    const next = new Set(prev);
    if (next.has(name)) next.delete(name); else next.add(name);
    return next;
  });

  return (
    <div className="max-w-5xl pb-12">
      <PageHeader
        title="Strategies"
        description="The six strategies the backtester can combine, each with its default share of capital. Open one to see the settings it uses."
      >
        {strategies.length > 0 && (
          <button
            onClick={() => setOpen(allOpen ? new Set() : new Set(strategies.map((s) => s.name)))}
            className="h-8 px-3 rounded-[var(--radius-sm)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] hover:border-[var(--border-bright)]"
          >
            {allOpen ? "Collapse all" : "Expand all"}
          </button>
        )}
      </PageHeader>

      {error ? (
        <div role="alert" className="flex items-center justify-between gap-4 rounded-[var(--radius-lg)] border border-[var(--color-danger)]/40 bg-[var(--color-danger-subtle)] px-4 py-3">
          <p className="text-sm text-[var(--color-text-primary)]">{error}</p>
          <button onClick={fetchStrategies} className="h-8 px-3 rounded-[var(--radius-sm)] bg-[var(--color-accent)] text-white text-xs font-medium shrink-0">
            Try again
          </button>
        </div>
      ) : (
        <ul className="rounded-[var(--radius-lg)] border border-[var(--color-border)] overflow-hidden">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <li key={i} className="border-t border-[var(--color-border)] first:border-t-0 px-4 py-3">
                  <div className="skeleton h-4 w-1/3 rounded-[var(--radius-sm)]" />
                  <div className="skeleton h-3 w-2/3 mt-2 rounded-[var(--radius-sm)]" />
                </li>
              ))
            : strategies.map((s) => (
                <StrategyRow key={s.name} info={s} open={open.has(s.name)} onToggle={() => toggle(s.name)} />
              ))}
        </ul>
      )}
    </div>
  );
}
