"use client";

import { useState, useMemo } from "react";
import { ArrowUpDown } from "lucide-react";
import clsx from "clsx";
import type { TradeRecord } from "@/lib/api";
import { Badge, Card, CardHeader } from "@/components/ui";

type SortKey = keyof TradeRecord;

function TradeHeaderCell({
  label,
  active,
  ascending,
  onClick,
}: {
  label: string;
  active: boolean;
  ascending: boolean;
  onClick: () => void;
}) {
  return (
    <th
      onClick={onClick}
      className="text-left px-3 py-2 text-[10px] font-semibold text-slate-500 uppercase tracking-wider cursor-pointer hover:text-white transition-colors select-none"
    >
      <span className="flex items-center gap-1">
        {label}
        <ArrowUpDown size={9} className={clsx(active ? "text-cyan-400" : "text-slate-600", ascending ? "rotate-180" : "")} />
      </span>
    </th>
  );
}

export function TradeLogTable({ trades }: { trades: TradeRecord[] }) {
  const [sortKey, setSortKey]   = useState<SortKey>("exit_date");
  const [sortAsc, setSortAsc]   = useState(false);
  const [search, setSearch]     = useState("");
  const [page, setPage]         = useState(0);
  const PAGE_SIZE = 15;

  const filtered = useMemo(
    () =>
      trades.filter(
        (t) =>
          t.symbol.toLowerCase().includes(search.toLowerCase()) ||
          t.strategy_name.toLowerCase().includes(search.toLowerCase())
      ),
    [trades, search]
  );

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const va = a[sortKey] ?? "";
      const vb = b[sortKey] ?? "";
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [filtered, sortKey, sortAsc]);

  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortAsc(!sortAsc);
    else { setSortKey(k); setSortAsc(false); }
  };

  return (
    <Card>
      <CardHeader
        title={`Trade Log`}
        subtitle={`${filtered.length} of ${trades.length} trades`}
      >
        <input
          type="text"
          placeholder="Search symbol / strategy…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(0); }}
          className="text-xs rounded-lg border border-[#1e2d4a] bg-[#162035] text-slate-300 px-3 py-1.5 w-44 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
        />
      </CardHeader>

      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-xs min-w-[640px]">
          <thead>
            <tr className="border-b border-[#1e2d4a]">
              <TradeHeaderCell label="Symbol" active={sortKey === "symbol"} ascending={sortAsc} onClick={() => toggleSort("symbol")} />
              <TradeHeaderCell label="Strategy" active={sortKey === "strategy_name"} ascending={sortAsc} onClick={() => toggleSort("strategy_name")} />
              <TradeHeaderCell label="Side" active={sortKey === "side"} ascending={sortAsc} onClick={() => toggleSort("side")} />
              <TradeHeaderCell label="Entry" active={sortKey === "entry_date"} ascending={sortAsc} onClick={() => toggleSort("entry_date")} />
              <TradeHeaderCell label="Exit" active={sortKey === "exit_date"} ascending={sortAsc} onClick={() => toggleSort("exit_date")} />
              <TradeHeaderCell label="P&L" active={sortKey === "pnl"} ascending={sortAsc} onClick={() => toggleSort("pnl")} />
              <TradeHeaderCell label="Return" active={sortKey === "return_pct"} ascending={sortAsc} onClick={() => toggleSort("return_pct")} />
              <TradeHeaderCell label="Days" active={sortKey === "holding_days"} ascending={sortAsc} onClick={() => toggleSort("holding_days")} />
            </tr>
          </thead>
          <tbody>
            {paged.map((t, i) => {
              const isWin = t.pnl > 0;
              return (
                <tr
                  key={i}
                  className="border-b border-[#1e2d4a]/50 hover:bg-white/[0.02] transition-colors"
                >
                  <td className="px-3 py-2 font-mono font-bold text-white">{t.symbol}</td>
                  <td className="px-3 py-2 text-slate-400 capitalize">
                    {t.strategy_name.replace(/_/g, " ")}
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={t.side === "long" ? "success" : "danger"}>
                      {t.side}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-slate-400 font-mono">
                    {t.entry_date ?? "–"}
                  </td>
                  <td className="px-3 py-2 text-slate-400 font-mono">
                    {t.exit_date ?? "–"}
                  </td>
                  <td className={clsx("px-3 py-2 font-mono font-semibold", isWin ? "text-emerald-400" : "text-red-400")}>
                    {isWin ? "+" : ""}${t.pnl.toFixed(2)}
                  </td>
                  <td className={clsx("px-3 py-2 font-mono", isWin ? "text-emerald-400" : "text-red-400")}>
                    {(t.return_pct * 100).toFixed(2)}%
                  </td>
                  <td className="px-3 py-2 text-slate-400">{t.holding_days}d</td>
                </tr>
              );
            })}
            {paged.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-slate-600">
                  No trades found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-slate-500">
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-1">
            <button
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
              className="px-2.5 py-1 rounded text-xs border border-[#1e2d4a] text-slate-400 disabled:opacity-40 hover:text-white transition-colors"
            >
              ‹ Prev
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(page + 1)}
              className="px-2.5 py-1 rounded text-xs border border-[#1e2d4a] text-slate-400 disabled:opacity-40 hover:text-white transition-colors"
            >
              Next ›
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
