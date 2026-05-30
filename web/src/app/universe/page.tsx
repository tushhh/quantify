"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Search, Globe } from "lucide-react";
import { api } from "@/lib/api";
import type { TickerInfo } from "@/lib/api";
import { Skeleton, Badge, Card } from "@/components/ui";

const SECTOR_COLORS: Record<string, string> = {
  "Technology":              "bg-blue-500/15   text-blue-400   border border-blue-500/20",
  "Consumer Discretionary":  "bg-violet-500/15 text-violet-400 border border-violet-500/20",
  "Financials":              "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20",
  "Healthcare":              "bg-rose-500/15   text-rose-400   border border-rose-500/20",
  "Energy":                  "bg-amber-500/15  text-amber-400  border border-amber-500/20",
  "Consumer Staples":        "bg-lime-500/15   text-lime-400   border border-lime-500/20",
  "Industrials":             "bg-orange-500/15 text-orange-400 border border-orange-500/20",
  "Communication Services":  "bg-cyan-500/15   text-cyan-400   border border-cyan-500/20",
  "ETF":                     "bg-slate-500/15  text-slate-400  border border-slate-500/20",
};

const DEFAULT_SECTOR = "bg-slate-500/15 text-slate-400 border border-slate-500/20";

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
    <div className="max-w-5xl mx-auto px-4 pt-20 pb-24 md:pb-12 flex flex-col gap-4 animate-fade-in">

      {/* Header */}
      <div>
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-8 h-8 rounded-lg gradient-accent flex items-center justify-center">
            <Globe size={15} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-white">Universe</h1>
        </div>
        <p className="text-xs text-slate-500 ml-10.5">
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
                ? "bg-blue-500/15 border-blue-400/30 text-blue-200"
                : "border-[var(--border)] text-slate-400 hover:text-white hover:bg-white/[0.03]"
            )}
          >
            {v === "sectors" ? "By Sector" : "All Tickers"}
          </button>
        ))}
      </div>

      {/* Search + sector filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
          <input
            type="text"
            placeholder="Search ticker or company name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface-raised)] text-sm text-slate-300 placeholder-[var(--text-dim)] pl-9 pr-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500/40 transition-all"
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
                  ? "bg-blue-600 border-blue-500 text-white"
                  : "bg-[var(--surface-raised)] border-[var(--border)] text-slate-400 hover:text-white hover:border-[var(--border-bright)]"
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
                <span className="text-xs text-slate-600">{items.length} tickers</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2">
                {items.map((t) => (
                  <div
                    key={t.symbol}
                    className="flex flex-col gap-1 p-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-bright)] hover:bg-[var(--surface-raised)] transition-all cursor-default"
                  >
                    <span className="font-mono font-bold text-white text-sm">{t.symbol}</span>
                    <span className="text-[10px] text-slate-500 leading-tight line-clamp-2">{t.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {visible.length === 0 && (
            <div className="text-center py-16 text-slate-600 text-sm">
              No tickers match your filters
            </div>
          )}
        </div>
      ) : (
        <Card variant="compact" className="overflow-hidden">
          <div className="grid grid-cols-3 px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest border-b border-[var(--border)] bg-black/20">
            <span>Symbol</span>
            <span>Company</span>
            <span className="text-right">Sector</span>
          </div>
          <div className="max-h-[560px] overflow-y-auto">
            {visible.map((t) => (
              <div key={t.symbol} className="grid grid-cols-3 px-4 py-3 text-xs border-b border-[var(--border)]/40 hover:bg-white/[0.02] transition-colors">
                <span className="font-mono font-bold text-white">{t.symbol}</span>
                <span className="text-slate-400 line-clamp-1">{t.name}</span>
                <div className="text-right">
                  <Badge variant="default" className="text-[9px]">{t.sector.split(" ")[0]}</Badge>
                </div>
              </div>
            ))}
            {visible.length === 0 && (
              <div className="text-center py-12 text-slate-600 text-sm">No tickers match your filters</div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
