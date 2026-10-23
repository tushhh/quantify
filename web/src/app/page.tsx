"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, errorMessage, type PredictionItem, type PredictionResponse } from "@/lib/api";

const pct = (v?: number | null, digits = 1) =>
  v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;

const monthOfList = (asOf?: string | null) => {
  if (!asOf) return "";
  const d = new Date(`${asOf}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + 5);
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
};

const TOOLS = [
  {
    href: "/backtest",
    name: "Backtest",
    text: "Run any of the six strategies over past data with commissions, spread and slippage, and compare it with SPY before risking money.",
  },
  {
    href: "/portfolio",
    name: "Portfolio",
    text: "Log the trades you actually make, see live P&L, and get a Telegram message when a holding drops past your threshold.",
  },
  {
    href: "/strategies",
    name: "Strategies",
    text: "Read what each strategy does and which settings it uses, then change them in a backtest.",
  },
];

export default function OverviewPage() {
  const [result, setResult] = useState<PredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.predict.best(15)
      .then(setResult)
      .catch((err) => setError(errorMessage(err, "This month's list couldn't be loaded.")));
  }, []);

  const top = (result?.signals ?? []).filter((s) => s.side === "long").slice(0, 5);
  const band = top[0];
  const bt = result?.backtest;

  return (
    <div className="max-w-[1180px]">
      <section className="grid gap-10 grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-16 pt-4 lg:pt-10">
        <div>
          <h1 className="text-[31px] leading-[1.15] font-semibold tracking-tight text-[var(--color-text-primary)] max-w-[22ch]">
            Fifteen trend picks a month, each with a forecast and a public record.
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-[var(--color-text-secondary)] max-w-[60ch]">
            After each month&apos;s last close, Quantify ranks the 100 most-traded S&amp;P 500 stocks by the strength of
            their 6- and 12-month trends and publishes the top fifteen. Every pick shows what stocks at its rank did the
            following month, bad months included, and every list is scored against SPY once it&apos;s replaced.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/predict" className="inline-flex h-10 items-center px-4 rounded-[var(--radius-sm)] bg-[var(--color-accent)] text-white text-sm font-medium hover:bg-[var(--color-accent-hover)]">
              See this month&apos;s list
            </Link>
            <Link href="/backtest" className="inline-flex h-10 items-center px-4 rounded-[var(--radius-sm)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm font-medium hover:border-[var(--border-bright)]">
              Run a backtest
            </Link>
          </div>
        </div>

        <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)]">
          <div className="px-4 pt-4 pb-3 border-b border-[var(--color-border)]">
            <h3 className="text-sm font-medium text-[var(--color-text-primary)]">
              {result?.as_of ? `Top of the ${monthOfList(result.as_of)} list` : "Top of this month's list"}
            </h3>
            {band?.forecast_beat_spy_pct != null && (
              <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                Each of these five: <span className="font-mono text-[var(--color-text-primary)]">{pct(band.predicted_return_pct)}</span> expected
                next month, <span className="font-mono text-[var(--color-text-primary)]">{band.forecast_beat_spy_pct.toFixed(1)}%</span> chance to beat SPY.
              </p>
            )}
          </div>
          {error ? (
            <p className="px-4 py-6 text-sm text-[var(--color-text-secondary)]">{error}</p>
          ) : (
            <ol>
              {(top.length ? top : Array.from<PredictionItem | null>({ length: 5 }).fill(null)).map((s, i) => (
                <li key={s ? s.symbol : i} className="flex items-center justify-between gap-4 px-4 py-2.5 border-t border-[var(--color-border)]/60 first:border-t-0">
                  {s ? (
                    <>
                      <span className="flex items-baseline gap-3 min-w-0">
                        <span className="font-mono text-xs text-[var(--color-text-muted)] w-3">{i + 1}</span>
                        <span className="font-mono text-sm font-medium text-[var(--color-text-primary)]">{s.symbol}</span>
                        <span className="text-xs text-[var(--color-text-secondary)] truncate">{s.name}</span>
                      </span>
                      <span className="text-xs text-[var(--color-text-muted)] whitespace-nowrap"><span className="font-mono text-[var(--color-success)]">{pct(s.return_6m_pct, 0)}</span> in 6 months</span>
                    </>
                  ) : (
                    <div className="skeleton h-4 w-full rounded-[var(--radius-sm)]" />
                  )}
                </li>
              ))}
            </ol>
          )}
          <div className="px-4 py-3 border-t border-[var(--color-border)]">
            <Link href="/predict" className="text-xs font-medium text-[var(--color-accent)] hover:underline">See all fifteen with their forecasts</Link>
          </div>
        </div>
      </section>

      <section aria-labelledby="record-heading" className="mt-16 border-t border-[var(--color-border)] pt-8">
        <h3 id="record-heading" className="text-base font-medium text-[var(--color-text-primary)]">How the rule has done</h3>
        <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
          Walk-forward backtest{bt ? `, ${bt.start} to ${bt.end}` : ""}, after trading costs. Each month&apos;s list used only data available at that close.
        </p>
        <dl className="mt-6 grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4">
          {[
            { label: "Return per year", value: bt ? `${bt.cagr_pct.toFixed(1)}%` : null, sub: bt ? `SPY ${bt.spy_cagr_pct.toFixed(1)}%` : "", tone: "text-[var(--color-success)]" },
            { label: "Worst drop", value: bt ? `${bt.max_drawdown_pct.toFixed(0)}%` : null, sub: bt ? `SPY ${bt.spy_max_drawdown_pct.toFixed(0)}%` : "", tone: "text-[var(--color-danger)]" },
            { label: "Months beating SPY", value: bt ? `${bt.months_beat_spy_pct.toFixed(0)}%` : null, sub: "of every month tested", tone: "text-[var(--color-text-primary)]" },
            { label: "Years it lost to SPY", value: bt?.losing_years ?? null, sub: "expect losing stretches", tone: "text-[var(--color-text-primary)]" },
          ].map((m) => (
            <div key={m.label}>
              <dt className="text-xs text-[var(--color-text-secondary)]">{m.label}</dt>
              <dd className={`mt-1 font-mono text-xl ${m.tone}`}>
                {m.value ?? <span className="skeleton inline-block h-6 w-20 rounded-[var(--radius-sm)]" />}
              </dd>
              <dd className="mt-0.5 text-xs text-[var(--color-text-muted)]">{m.sub}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="tools-heading" className="mt-16 border-t border-[var(--color-border)] pt-8 pb-8">
        <h3 id="tools-heading" className="text-base font-medium text-[var(--color-text-primary)]">Check anything before you trust it</h3>
        <ul className="mt-4 grid gap-x-10 gap-y-6 md:grid-cols-3">
          {TOOLS.map((tool) => (
            <li key={tool.href}>
              <Link href={tool.href} className="text-sm font-medium text-[var(--color-text-primary)] hover:text-[var(--color-accent)]">
                {tool.name}
              </Link>
              <p className="mt-1 text-[13px] leading-relaxed text-[var(--color-text-secondary)] max-w-[44ch]">{tool.text}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
