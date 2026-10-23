"use client";

import PageHeader from "@/components/layout/page-header";
import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { api, errorMessage } from "@/lib/api";
import type { TickerInfo } from "@/lib/api";

export default function UniversePage() {
  const [tickers, setTickers] = useState<TickerInfo[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [sector, setSector] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.universe.get()
      .then((r) => { setTickers(r.tickers); setSectors(r.sectors); })
      .catch((err) => setError(errorMessage(err, "The stock list couldn't be loaded. Try again in a minute.")))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tickers
      .filter((t) => (!sector || t.sector === sector) && (!q || t.symbol.toLowerCase().includes(q) || t.name.toLowerCase().includes(q)))
      .sort((a, b) => a.sector.localeCompare(b.sector) || a.symbol.localeCompare(b.symbol));
  }, [tickers, sector, search]);

  return (
    <div className="max-w-4xl pb-12">
      <PageHeader
        title="Universe"
        description={loading ? "Large US stocks and ETFs, with the sector each one belongs to." : `${tickers.length} large US stocks and ETFs across ${sectors.length} sectors, with the sector each one belongs to.`}
      />

      <div className="flex flex-wrap items-end gap-3 mb-3">
        <label className="flex flex-col gap-1 text-xs text-[var(--color-text-secondary)] grow sm:grow-0 sm:w-64">
          Search
          <span className="relative">
            <Search aria-hidden className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--color-text-muted)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Ticker or company"
              className="w-full h-8 pl-8 pr-2 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface)] text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)]"
            />
          </span>
        </label>
        <label className="flex flex-col gap-1 text-xs text-[var(--color-text-secondary)]">
          Sector
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            className="h-8 px-2 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface)] text-sm text-[var(--color-text-primary)]"
          >
            <option value="">All sectors</option>
            {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        {!loading && (
          <p className="ml-auto text-xs text-[var(--color-text-secondary)] self-center">
            Showing <span className="font-mono">{visible.length}</span> of <span className="font-mono">{tickers.length}</span>
          </p>
        )}
      </div>

      {error ? (
        <p role="alert" className="rounded-[var(--radius-lg)] border border-[var(--color-danger)]/40 bg-[var(--color-danger-subtle)] px-4 py-3 text-sm text-[var(--color-text-primary)]">{error}</p>
      ) : (
        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-[var(--color-surface)] text-xs text-[var(--color-text-secondary)]">
              <tr>
                <th scope="col" className="py-2.5 pl-4 pr-4 font-normal w-24">Ticker</th>
                <th scope="col" className="py-2.5 pr-4 font-normal">Company</th>
                <th scope="col" className="py-2.5 pr-4 font-normal">Sector</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 10 }).map((_, i) => (
                    <tr key={i} className="border-t border-[var(--color-border)]"><td colSpan={3} className="px-4 py-2.5"><div className="skeleton h-4 rounded-[var(--radius-sm)]" /></td></tr>
                  ))
                : visible.map((t) => (
                    <tr key={t.symbol} className="border-t border-[var(--color-border)]/60 even:bg-[var(--color-surface)]/40">
                      <td className="py-2 pl-4 pr-4 font-mono text-sm font-medium text-[var(--color-text-primary)]">{t.symbol}</td>
                      <td className="py-2 pr-4 text-sm text-[var(--color-text-secondary)]">{t.name}</td>
                      <td className="py-2 pr-4 text-xs text-[var(--color-text-secondary)]">{t.sector}</td>
                    </tr>
                  ))}
            </tbody>
          </table>
          {!loading && visible.length === 0 && (
            <p className="px-4 py-8 text-center text-sm text-[var(--color-text-secondary)]">
              Nothing matches &ldquo;{search}&rdquo;{sector ? ` in ${sector}` : ""}. Try a ticker like AAPL, or clear the sector filter.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
