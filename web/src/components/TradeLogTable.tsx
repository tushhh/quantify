"use client";

import { useState, useMemo } from "react";
import { ArrowUpDown } from "lucide-react";
import clsx from "clsx";
import type { TradeRecord } from "@/lib/api";
import { Badge, Card, CardHeader } from "@/components/ui";

type SortKey = keyof TradeRecord;

function HeaderCell({
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
      className="align-middle text-left px-3 py-3 text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider cursor-pointer hover:text-[var(--color-text-primary)] transition-colors select-none"
    >
      <span className="flex items-center gap-1">
        {label}
        <ArrowUpDown
          size={8}
          className={clsx(
            active ? "text-[var(--color-info)]" : "text-[var(--color-text-muted)]",
            ascending ? "rotate-180" : ""
          )}
        />
      </span>
    </th>
  );
}

export function TradeLogTable({ trades }: { trades: TradeRecord[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("exit_date");
  const [sortAsc, setSortAsc] = useState(false);
  const [search, setSearch]   = useState("");
  const [page, setPage]       = useState(0);
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

  const paged      = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortAsc(!sortAsc);
    else { setSortKey(k); setSortAsc(false); }
  };

  return (
    <Card>
      <CardHeader className="flex items-center justify-between gap-3 p-4 pb-0">
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">Trade Log</h3>
          <p className="text-xs text-[var(--color-text-muted)]">{filtered.length} of {trades.length} trades</p>
        </div>
        <div>
          <input
            type="text"
            placeholder="Search symbol / strategy…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            className="text-xs rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-raised)] text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] px-3 py-1.5 w-44 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]/30 transition-all"
          />
        </div>
      </CardHeader>

      <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[var(--shadow-xs)]">
        <table className="w-full text-sm min-w-[600px] border-collapse">
          <thead>
            <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface-raised)]">
              <HeaderCell label="Symbol"   active={sortKey === "symbol"}        ascending={sortAsc} onClick={() => toggleSort("symbol")} />
              <HeaderCell label="Strategy" active={sortKey === "strategy_name"} ascending={sortAsc} onClick={() => toggleSort("strategy_name")} />
              <HeaderCell label="Side"     active={sortKey === "side"}          ascending={sortAsc} onClick={() => toggleSort("side")} />
              <HeaderCell label="Entry"    active={sortKey === "entry_date"}    ascending={sortAsc} onClick={() => toggleSort("entry_date")} />
              <HeaderCell label="Exit"     active={sortKey === "exit_date"}     ascending={sortAsc} onClick={() => toggleSort("exit_date")} />
              <HeaderCell label="P&L"      active={sortKey === "pnl"}           ascending={sortAsc} onClick={() => toggleSort("pnl")} />
              <HeaderCell label="Return"   active={sortKey === "return_pct"}    ascending={sortAsc} onClick={() => toggleSort("return_pct")} />
              <HeaderCell label="Days"     active={sortKey === "holding_days"}  ascending={sortAsc} onClick={() => toggleSort("holding_days")} />
            </tr>
          </thead>
          <tbody className="bg-[var(--color-surface)] divide-y divide-[var(--color-border-subtle)]">
            {paged.map((t) => {
              const isWin = t.pnl > 0;
              const rowKey = `${t.symbol}-${t.strategy_name}-${t.entry_date ?? "open"}-${t.exit_date ?? "open"}`;
              return (
                <tr
                  key={rowKey}
                  className="hover:bg-[var(--color-surface-raised)] transition-colors cursor-default"
                >
                  <td className="px-4 py-3 font-mono font-semibold text-[var(--color-text-primary)]">{t.symbol}</td>
                  <td className="px-4 py-3 text-[var(--color-text-secondary)] capitalize text-[11px]">{t.strategy_name.replace(/_/g, " ")}</td>
                  <td className="px-4 py-3">
                    <Badge variant={t.side === "long" ? "success" : "danger"}>{t.side}</Badge>
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)] font-mono">{t.entry_date ?? "–"}</td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)] font-mono">{t.exit_date ?? "–"}</td>
                  <td className={clsx("px-4 py-3 font-mono font-semibold tabular-nums", isWin ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                    {isWin ? "+" : ""}${t.pnl.toFixed(2)}
                  </td>
                  <td className={clsx("px-4 py-3 font-mono tabular-nums", isWin ? "text-[var(--color-success)]" : "text-[var(--color-danger)]")}>
                    {isWin ? "+" : ""}{(t.return_pct * 100).toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-[var(--color-text-muted)]">{t.holding_days}d</td>
                </tr>
              );
            })}
            {paged.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-10 text-center text-[var(--color-text-muted)]">
                  No trades found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--color-border)]">
          <span className="text-xs text-[var(--color-text-muted)]">Page {page + 1} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
              className="px-3 py-1.5 rounded-[var(--radius-sm)] text-xs border border-[var(--color-border)] text-[var(--color-text-secondary)] disabled:opacity-40 hover:bg-[var(--color-surface-raised)] transition-all"
            >
              ← Prev
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(page + 1)}
              className="px-3 py-1.5 rounded-[var(--radius-sm)] text-xs border border-[var(--color-border)] text-[var(--color-text-secondary)] disabled:opacity-40 hover:bg-[var(--color-surface-raised)] transition-all"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
