"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, errorMessage, type PredictionItem, type PredictionResponse } from "@/lib/api";

// Shared axis for every range bar, so ranges can be compared down the list (percent).
const AXIS_MIN = -20;
const AXIS_MAX = 30;

const pct = (v?: number | null, digits = 1) =>
  v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;

const toAxis = (v: number) => ((Math.min(Math.max(v, AXIS_MIN), AXIS_MAX) - AXIS_MIN) / (AXIS_MAX - AXIS_MIN)) * 100;

const longDate = (iso?: string | null) =>
  iso ? new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" }) : "";

// The list made from a month's last close is held through the following month.
const heldMonth = (asOf?: string | null) => {
  if (!asOf) return "";
  const d = new Date(`${asOf}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 5);
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
};

const SECTOR_SHORT: Record<string, string> = {
  "Information Technology": "Tech",
  "Communication Services": "Communications",
  "Consumer Discretionary": "Consumer disc.",
  "Consumer Staples": "Consumer staples",
  "Health Care": "Health care",
  "Real Estate": "Real estate",
};

function RangeBar({ low, high, expected, index }: { low: number; high: number; expected: number; index: number }) {
  const left = toAxis(low);
  const right = toAxis(high);
  return (
    <div className="relative h-9" role="img" aria-label={`Likely range ${pct(low, 0)} to ${pct(high, 0)}, expected ${pct(expected)}`}>
      <div className="absolute inset-x-0 top-3 h-px bg-[var(--color-border)]" />
      <div className="absolute top-1 h-4 w-px bg-[var(--color-text-muted)]" style={{ left: `${toAxis(0)}%` }} />
      <div
        className="range-draw absolute top-3 h-1.5 -translate-y-1/2 rounded-full bg-[var(--color-accent)]/50"
        style={{ left: `${left}%`, width: `${right - left}%`, animationDelay: `${index * 60}ms` }}
      />
      <div className="absolute top-3 h-3.5 w-0.5 -translate-y-1/2 rounded-full bg-[var(--color-text-primary)]" style={{ left: `calc(${toAxis(expected)}% - 1px)` }} />
      <span className="absolute top-5 -translate-x-1/2 font-mono text-[11px] text-[var(--color-danger)]" style={{ left: `${left}%` }}>{pct(low, 0)}</span>
      <span className="absolute top-5 -translate-x-1/2 font-mono text-[11px] text-[var(--color-success)]" style={{ left: `${right}%` }}>{pct(high, 0)}</span>
    </div>
  );
}

const BANDS = [
  { label: "Ranks 1 to 5", from: 1, to: 5 },
  { label: "Ranks 6 to 10", from: 6, to: 10 },
  { label: "Ranks 11 to 15", from: 11, to: 15 },
];

function BandRow({ label, first, index }: { label: string; first: PredictionItem; index: number }) {
  const hasForecast = first.forecast_low_pct != null && first.forecast_high_pct != null;
  return (
    <tr className="border-t border-[var(--color-border)] bg-[var(--color-surface)]">
      <td colSpan={6} className="px-4 py-3">
        <div className="grid gap-x-6 gap-y-2 grid-cols-[1fr_auto_auto] sm:grid-cols-[minmax(0,1.3fr)_auto_minmax(12rem,2fr)_auto] items-start">
          <div>
            <div className="text-sm font-medium text-[var(--color-text-primary)]">{label}</div>
            <div className="mt-0.5 text-xs text-[var(--color-text-secondary)]">Next-month forecast per stock</div>
          </div>
          <div className="text-right">
            <div className="font-mono text-base text-[var(--color-text-primary)]">{pct(first.predicted_return_pct)}</div>
            <div className="text-xs text-[var(--color-text-secondary)]">expected</div>
          </div>
          <div className="col-span-3 row-start-2 sm:col-span-1 sm:row-start-auto">
            {hasForecast && <RangeBar low={first.forecast_low_pct!} high={first.forecast_high_pct!} expected={first.predicted_return_pct} index={index} />}
          </div>
          <div className="text-right">
            <div className="font-mono text-base text-[var(--color-text-primary)]">
              {first.forecast_beat_spy_pct != null ? `${first.forecast_beat_spy_pct.toFixed(1)}%` : "–"}
            </div>
            <div className="text-xs text-[var(--color-text-secondary)]">chance to beat SPY</div>
          </div>
        </div>
      </td>
    </tr>
  );
}

function PickRow({ s, rank }: { s: PredictionItem; rank: number }) {
  return (
    <tr className="border-t border-[var(--color-border)]/60">
      <td className="py-2 pl-4 pr-2 w-10 font-mono text-xs text-[var(--color-text-muted)]">{rank}</td>
      <td className="py-2 pr-4">
        <span className="font-mono text-sm font-medium text-[var(--color-text-primary)]">{s.symbol}</span>
        <span className="block sm:inline sm:ml-2 text-xs text-[var(--color-text-secondary)]">{s.name || s.symbol}</span>
      </td>
      <td className="py-2 pr-4 text-right font-mono text-sm text-[var(--color-success)]">{pct(s.return_6m_pct, 0)}</td>
      <td className="hidden sm:table-cell py-2 pr-4 text-right font-mono text-sm text-[var(--color-success)]">{pct(s.return_12m_pct, 0)}</td>
      <td className="hidden sm:table-cell py-2 pr-6 text-right font-mono text-sm text-[var(--color-text-secondary)]">{pct(s.pct_above_ma200, 0)}</td>
      <td className="hidden md:table-cell py-2 pr-4 text-right text-xs text-[var(--color-text-secondary)] whitespace-nowrap">
        {SECTOR_SHORT[s.sector] ?? s.sector}
      </td>
    </tr>
  );
}

function SkeletonRows() {
  return (
    <tbody>
      {Array.from({ length: 8 }).map((_, i) => (
        <tr key={i} className="border-t border-[var(--color-border)]">
          <td colSpan={6} className="py-3 px-4"><div className="skeleton h-5 rounded-[var(--radius-sm)]" /></td>
        </tr>
      ))}
    </tbody>
  );
}

export default function PicksPage() {
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sector, setSector] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(await api.predict.best(15));
    } catch (err) {
      setError(errorMessage(err, "The picks couldn't be loaded. Try again in a minute."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const picks = useMemo(() => (result?.signals ?? []).filter((s) => s.side === "long"), [result]);
  const sectors = useMemo(() => Array.from(new Set(picks.map((s) => s.sector))).sort(), [picks]);
  const shown = sector ? picks.filter((s) => s.sector === sector) : picks;
  const bt = result?.backtest;
  const isTrend = result?.method === "trend";

  return (
    <div className="max-w-[1320px]">
      <header className="max-w-3xl">
        <h1 className="text-[25px] leading-tight font-semibold tracking-tight text-[var(--color-text-primary)]">
          {isTrend ? `Trend picks for ${heldMonth(result?.as_of)}` : "This month's picks"}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-[var(--color-text-secondary)]">
          {isTrend ? (
            <>
              The fifteen strongest 6- and 12-month trends among the 100 most-traded S&amp;P 500 stocks, set from the{" "}
              {longDate(result?.as_of)} close and held until the next list on {longDate(result?.next_refresh)}.
              Each forecast is what stocks at that rank did over the following month, from 2017 to 2026.
            </>
          ) : (
            "The fifteen strongest trends among the 100 most-traded S&P 500 stocks, updated after each month's last close."
          )}
        </p>
      </header>

      <div className="mt-8 grid gap-8 grid-cols-[minmax(0,1fr)] xl:grid-cols-[minmax(0,1fr)_300px]">
        <section aria-labelledby="picks-heading" className="min-w-0">
          <div className="flex items-end justify-between gap-4 mb-3">
            <h3 id="picks-heading" className="text-base font-medium text-[var(--color-text-primary)]">
              {sector ? `${shown.length} of ${picks.length} picks in ${sector}` : `${picks.length || 15} picks, ranked by trend strength`}
            </h3>
            {sectors.length > 1 && (
              <label className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
                Sector
                <select
                  value={sector}
                  onChange={(e) => setSector(e.target.value)}
                  className="h-8 px-2 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-primary)] text-xs"
                >
                  <option value="">All sectors</option>
                  {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
            )}
          </div>

          {error && (
            <div role="alert" className="mb-4 flex items-center justify-between gap-4 rounded-[var(--radius-lg)] border border-[var(--color-danger)]/40 bg-[var(--color-danger-subtle)] px-4 py-3">
              <p className="text-sm text-[var(--color-text-primary)]">{error}</p>
              <button onClick={load} className="h-8 px-3 rounded-[var(--radius-sm)] bg-[var(--color-accent)] text-white text-xs font-medium shrink-0">
                Try again
              </button>
            </div>
          )}

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] overflow-hidden">
            <table className="w-full text-left">
              <thead className="text-xs text-[var(--color-text-secondary)]">
                <tr>
                  <th scope="col" className="py-2.5 pl-4 pr-2 font-normal text-left">Rank</th>
                  <th scope="col" className="py-2.5 pr-4 font-normal text-left">Stock</th>
                  <th scope="col" className="py-2.5 pr-4 font-normal text-right">Past 6 months</th>
                  <th scope="col" className="hidden sm:table-cell py-2.5 pr-4 font-normal text-right">Past 12 months</th>
                  <th scope="col" className="hidden sm:table-cell py-2.5 pr-6 font-normal text-right">Above 200-day average</th>
                  <th scope="col" className="hidden md:table-cell py-2.5 pr-4 font-normal text-right">Sector</th>
                </tr>
              </thead>
              {loading && !result ? (
                <SkeletonRows />
              ) : (
                <tbody>
                  {BANDS.map((band, bi) => {
                    const members = shown.filter((s) => {
                      const r = picks.indexOf(s) + 1;
                      return r >= band.from && r <= band.to;
                    });
                    if (!members.length) return null;
                    return [
                      <BandRow key={band.label} label={band.label} first={members[0]} index={bi} />,
                      ...members.map((s) => <PickRow key={s.symbol} s={s} rank={picks.indexOf(s) + 1} />),
                    ];
                  })}
                </tbody>
              )}
            </table>
            {!loading && !error && picks.length === 0 && (
              <div className="px-4 py-10 text-center">
                <p className="text-sm text-[var(--color-text-primary)]">No list has been published yet.</p>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                  A new list is made after each month&apos;s last close. Meanwhile, you can test the rule in a backtest.
                </p>
                <Link href="/backtest" className="mt-4 inline-flex h-8 items-center px-3 rounded-[var(--radius-sm)] bg-[var(--color-accent)] text-white text-xs font-medium">
                  Run a backtest
                </Link>
              </div>
            )}
          </div>
          <p className="mt-3 text-xs leading-relaxed text-[var(--color-text-muted)] max-w-3xl">
            Each band&apos;s bar spans the 10th to 90th percentile of next-month returns for past picks at those ranks (8 in 10
            outcomes fell inside it); the white tick is the average and the grey line is zero. Single stocks swing widely: the
            edge has come from holding the whole list.
          </p>
        </section>

        <aside aria-label="Track record" className="flex flex-col gap-6 text-sm">
          <section className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <h3 className="font-medium text-[var(--color-text-primary)]">How this rule has done</h3>
            {bt ? (
              <>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Backtest, {bt.start} to {bt.end}, after trading costs</p>
                <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
                  <div>
                    <dt className="text-xs text-[var(--color-text-secondary)]">Return per year</dt>
                    <dd className="font-mono text-lg text-[var(--color-success)]">{bt.cagr_pct.toFixed(1)}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-[var(--color-text-secondary)]">SPY per year</dt>
                    <dd className="font-mono text-lg text-[var(--color-text-primary)]">{bt.spy_cagr_pct.toFixed(1)}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-[var(--color-text-secondary)]">Worst drop</dt>
                    <dd className="font-mono text-lg text-[var(--color-danger)]">{bt.max_drawdown_pct.toFixed(0)}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-[var(--color-text-secondary)]">SPY worst drop</dt>
                    <dd className="font-mono text-lg text-[var(--color-text-primary)]">{bt.spy_max_drawdown_pct.toFixed(0)}%</dd>
                  </div>
                </dl>
                <p className="mt-4 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                  Beat SPY in {bt.months_beat_spy_pct.toFixed(0)}% of months and lost to it in {bt.losing_years}.
                  The forecasts come from the same history the rule was chosen on, so treat them as optimistic.
                </p>
              </>
            ) : (
              <div className="mt-3 flex flex-col gap-2">
                <div className="skeleton h-4 rounded-[var(--radius-sm)]" />
                <div className="skeleton h-4 w-2/3 rounded-[var(--radius-sm)]" />
              </div>
            )}
          </section>

          <section className="px-1">
            <h3 className="font-medium text-[var(--color-text-primary)]">Live record</h3>
            <p className="mt-1 text-xs leading-relaxed text-[var(--color-text-secondary)]">
              Every list is saved when it&apos;s published and scored against SPY with what the stocks actually did.
              {result?.next_refresh ? ` This list is scored when it's replaced on ${longDate(result.next_refresh)}.` : ""}
            </p>
            <Link href="/backtest" className="mt-3 inline-block text-xs font-medium text-[var(--color-accent)] hover:underline">
              Test the rule yourself in Backtest
            </Link>
          </section>
        </aside>
      </div>
    </div>
  );
}
