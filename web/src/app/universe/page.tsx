"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Search, Globe } from "lucide-react";
import { api } from "@/lib/api";
import type { TickerInfo } from "@/lib/api";
import { Skeleton, Badge, Card } from "@/components/ui";

const SECTOR_COLORS: Record<string, string> = {
  "Technology":              "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "Consumer Discretionary":  "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "Financials":              "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "Healthcare":              "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "Energy":                  "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "Consumer Staples":        "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "Industrials":             "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "Communication Services":  "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
  "ETF":                     "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]",
};

const DEFAULT_SECTOR = "bg-[var(--color-surface-raised)] text-[var(--color-text-secondary)] border border-[var(--border)]";

export default function UniversePage() {
  const [tickers, setTickers] = useState<TickerInfo[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [filter, setFilter]   = useState<string>("All");
  const [search, setSearch]   = useState("");
  const [loading, setLoading] = useState(true);
  const [view, setView]       = useState<"sectors" | "list">("sectors");

  useEffect(() => {
    api.universe.get()
      .then((r) => {
        setTickers(r.tickers);
        setSectors(["All", ...r.sectors]);
      })
      .finally(() => setLoading(false));
  }, []);

  const visible = tickers.filter((t) => {
    const matchSector = filter === "All" || t.sector === filter;
    const matchSearch =
      !search ||
      t.symbol.toLowerCase().includes(search.toLowerCase()) ||
      t.name.toLowerCase().includes(search.toLowerCase());
    return matchSector && matchSearch;
  });

  const bySector: Record<string, TickerInfo[]> = {};
  for (const t of visible) {
    (bySector[t.sector] ??= []).push(t);
  }

  return (
    <div className="max-w-7xl mx-auto px-4 pt-16 pb-16 md:pb-10 flex flex-col gap-3 animate-fade-in">

      {/* Header */}
      <div>
        <div className="flex items-center gap-2.5 mb-0.5">
          <div className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center">
            <Globe size={15} className="text-[var(--color-text-inverse)]" />
          </div>
          <h1 className="text-xl font-bold text-[var(--color-text-inverse)]">Universe</h1>
        </div>
        <p className="text-xs text-[var(--color-text-muted)] ml-10.5">
          {tickers.length} tickers across {sectors.length - 1} sectors — the pool used in all backtests.
        </p>
      </div>

      {/* View toggle */}
      <div className="flex items-center gap-2">
        {(["sectors", "list"] as const).map((v) => (
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
            {v === "sectors" ? "By Sector" : "All Tickers"}
          </button>
        ))}
      </div>

      {/* Search + sector filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] pointer-events-none" />
          <input
            type="text"
            placeholder="Search ticker or company name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-[var(--border)] bg-[var(--color-surface-raised)] text-sm text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] pl-9 pr-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]/40 transition-all"
          />
        </div>
        <div className="flex gap-1.5 overflow-x-auto pb-0.5 shrink-0">
          {sectors.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-xs font-semibold border whitespace-nowrap transition-all",
                filter === s
                  ? "bg-[var(--color-cta)]/15 border-[var(--color-cta)] text-[var(--color-cta)]"
                  : "bg-[var(--color-surface-raised)] border-[var(--border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-inverse)] hover:border-[var(--border-bright)]"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {Array.from({ length: 20 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : view === "sectors" ? (
        <div className="flex flex-col gap-8">
          {Object.entries(bySector).map(([sector, items]) => (
            <div key={sector}>
              <div className="flex items-center gap-2 mb-3">
                <span className={clsx("text-xs font-semibold px-2.5 py-1 rounded-lg", SECTOR_COLORS[sector] ?? DEFAULT_SECTOR)}>
                  {sector}
                </span>
                <span className="text-xs text-[var(--color-text-secondary)]">{items.length} tickers</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2">
                {items.map((t) => (
                  <div
                    key={t.symbol}
                    className="flex flex-col gap-1 p-3 rounded-xl border border-[var(--border)] bg-[var(--color-surface)] hover:border-[var(--border-bright)] hover:bg-[var(--color-surface-raised)] transition-all cursor-default"
                  >
                    <span className="font-mono font-bold text-[var(--color-text-primary)] text-sm">{t.symbol}</span>
                    <span className="text-[10px] text-[var(--color-text-secondary)] leading-tight line-clamp-2">{t.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {visible.length === 0 && (
            <div className="text-center py-16 text-[var(--color-text-secondary)] text-sm">
              No tickers match your filters
            </div>
          )}
        </div>
      ) : (
        <Card variant="compact" className="overflow-hidden">
          <div className="grid grid-cols-3 px-4 py-3 text-[10px] font-bold text-[var(--color-text-secondary)] uppercase tracking-widest border-b border-[var(--border)] bg-[var(--color-surface)]">
            <span>Symbol</span>
            <span>Company</span>
            <span className="text-right">Sector</span>
          </div>
          <div className="max-h-[560px] overflow-y-auto">
            {visible.map((t) => (
              <div key={t.symbol} className="grid grid-cols-3 px-4 py-3 text-xs border-b border-[var(--border)]/40 hover:bg-[var(--color-surface-raised)] transition-colors">
                <span className="font-mono font-bold text-[var(--color-text-inverse)]">{t.symbol}</span>
                <span className="text-[var(--color-text-secondary)] line-clamp-1">{t.name}</span>
                <div className="text-right">
                  <Badge variant="default" className="text-[9px]">{t.sector.split(" ")[0]}</Badge>
                </div>
              </div>
            ))}
            {visible.length === 0 && (
              <div className="text-center py-12 text-[var(--color-text-secondary)] text-sm">No tickers match your filters</div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
