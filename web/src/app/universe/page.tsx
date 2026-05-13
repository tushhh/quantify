"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import type { TickerInfo } from "@/lib/api";
import { Skeleton, Badge } from "@/components/ui";

const SECTOR_COLORS: Record<string, string> = {
  "Technology":              "bg-blue-500/15   text-blue-400",
  "Consumer Discretionary":  "bg-violet-500/15 text-violet-400",
  "Financials":              "bg-emerald-500/15 text-emerald-400",
  "Healthcare":              "bg-rose-500/15   text-rose-400",
  "Energy":                  "bg-amber-500/15  text-amber-400",
  "Consumer Staples":        "bg-lime-500/15   text-lime-400",
  "Industrials":             "bg-orange-500/15 text-orange-400",
  "Communication Services":  "bg-cyan-500/15   text-cyan-400",
  "ETF":                     "bg-slate-500/15  text-slate-400",
};

export default function UniversePage() {
  const [tickers, setTickers]     = useState<TickerInfo[]>([]);
  const [sectors, setSectors]     = useState<string[]>([]);
  const [filter, setFilter]       = useState<string>("All");
  const [search, setSearch]       = useState("");
  const [loading, setLoading]     = useState(true);
  const [view, setView]           = useState<"sectors" | "list">("sectors");

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

  // Group by sector for heatmap-style display
  const bySector: Record<string, TickerInfo[]> = {};
  for (const t of visible) {
    (bySector[t.sector] ??= []).push(t);
  }

  return (
    <div className="max-w-5xl mx-auto px-4 pt-24 pb-24 md:pb-12 flex flex-col gap-6 animate-fade-in">
      <div>
        <h1 className="text-xl font-bold text-white">Universe</h1>
        <p className="text-xs text-slate-500 mt-1">
          Stock universe used in backtesting — {tickers.length} tickers across {sectors.length - 1} sectors.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setView("sectors")}
          className={clsx(
            "px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider border transition-all",
            view === "sectors"
              ? "bg-blue-500/20 border-blue-400/40 text-blue-200"
              : "border-white/10 text-slate-400 hover:text-white"
          )}
        >
          By Sector
        </button>
        <button
          type="button"
          onClick={() => setView("list")}
          className={clsx(
            "px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider border transition-all",
            view === "list"
              ? "bg-slate-700 border-slate-600 text-white"
              : "border-white/10 text-slate-400 hover:text-white"
          )}
        >
          All Tickers
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Search */}
        <div className="relative flex-1">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search ticker or company name…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-[#1e2d4a] bg-[#162035] text-sm text-slate-300 pl-8 pr-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
          />
        </div>

        {/* Sector pills — scrollable on mobile */}
        <div className="flex gap-1.5 overflow-x-auto pb-1 sm:pb-0 shrink-0">
          {sectors.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={clsx(
                "px-3 py-1.5 rounded-lg text-xs font-semibold border whitespace-nowrap transition-all",
                filter === s
                  ? "bg-blue-600 border-blue-500 text-white"
                  : "bg-[#162035] border-[#1e2d4a] text-slate-400 hover:text-white"
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
        <div className="flex flex-col gap-6">
          {Object.entries(bySector).map(([sector, items]) => (
            <div key={sector}>
              <div className="flex items-center gap-2 mb-3">
                <span
                  className={clsx(
                    "text-xs font-semibold px-2.5 py-1 rounded-lg",
                    SECTOR_COLORS[sector] ?? "bg-slate-500/15 text-slate-400"
                  )}
                >
                  {sector}
                </span>
                <span className="text-xs text-slate-600">{items.length} tickers</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2">
                {items.map((t) => (
                  <div
                    key={t.symbol}
                    className="flex flex-col gap-1 p-3 rounded-xl border border-[#1e2d4a] bg-[#0e1525] hover:border-blue-500/30 transition-all"
                  >
                    <span className="font-mono font-bold text-white text-sm">{t.symbol}</span>
                    <span className="text-[10px] text-slate-500 leading-tight line-clamp-2">{t.name}</span>
                    <Badge variant="default">{sector.split(" ")[0]}</Badge>
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
        <div className="rounded-xl border border-[#1e2d4a] bg-[#0e1525] overflow-hidden">
          <div className="grid grid-cols-3 px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-[#1e2d4a]">
            <span>Symbol</span>
            <span>Company</span>
            <span className="text-right">Sector</span>
          </div>
          <div className="max-h-[520px] overflow-y-auto">
            {visible.map((t) => (
              <div key={t.symbol} className="grid grid-cols-3 px-4 py-3 text-xs border-b border-white/5 hover:bg-white/[0.02]">
                <span className="font-mono text-white">{t.symbol}</span>
                <span className="text-slate-400 line-clamp-1">{t.name}</span>
                <span className="text-right text-slate-500">{t.sector}</span>
              </div>
            ))}
            {visible.length === 0 && (
              <div className="text-center py-10 text-slate-600 text-sm">No tickers match your filters</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
