#!/usr/bin/env python
"""
Walk-forward backtest of the published picks, judged against the agreed profit bar.

Replays quantify.trend_screen month by month: the list is scored from the last close of each
month (only data up to that close), bought at the next close, held for the month, with costs
charged on every trade. Uses the production scoring code, so it tests what users see.

    python scripts/backtest_picks.py                    # download data, report, check vs record
    python scripts/backtest_picks.py --cost-bps 16      # cost stress
    python scripts/backtest_picks.py --prices DIR       # reuse close.parquet/volume.parquet

Exit code 1 when results fall more than --tolerance points of excess return below the figures
recorded in trend_screen.BACKTEST (a change made the picks worse), or with --strict when any
row of the profit bar fails.

Caveat printed with every run: the universe is today's S&P 500 (survivorship bias), so absolute
returns are optimistic; compare changes against each other on the same data.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quantify.trend_screen import (  # noqa: E402
    BACKTEST, LIQUID_TOP, MAX_PER_SECTOR, N_PICKS, download_prices, forecast_bucket, score_trend,
    select_picks,
)

# The agreed bar (Oct 2026). Excess figures are annual percentage points over SPY.
BAR = {
    "excess_cagr_pct": 3.0,          # net excess return vs SPY >= 3 %/yr
    "information_ratio": 0.5,
    "months_beat_spy_pct": 55.0,
    "max_dd_vs_spy": 1.25,           # drawdown no worse than 1.25x SPY's
}


def month_end_anchors(index: pd.DatetimeIndex, start: str) -> list[pd.Timestamp]:
    s = pd.Series(index, index=index)
    ends = s.groupby(index.to_period("M")).max()
    return [t for t in ends if t >= pd.Timestamp(start)][:-1]  # last month may be incomplete


def simulate(close: pd.DataFrame, volume: pd.DataFrame, spy: pd.Series, start: str, sectors: dict[str, str],
             names: dict[str, str] | None = None, n: int = N_PICKS, liquid_top: int = LIQUID_TOP, cost_bps: float = 6.0) -> pd.DataFrame:
    """Daily net returns of the monthly book and SPY. Trades at the close after each anchor."""
    rets = close.pct_change(fill_method=None)
    spy_r = spy.pct_change(fill_method=None)
    dates = close.index
    trades = {}
    for anchor in month_end_anchors(dates, start):
        pos = dates.get_loc(anchor) + 1
        if pos < len(dates):
            scores = score_trend(close.loc[:anchor], volume.loc[:anchor], as_of=anchor, liquid_top=liquid_top)["score"]
            trades[dates[pos]] = select_picks(scores, sectors, n, names=names)
    first = min(trades)
    w: dict[str, float] = {}
    rows = []
    for t in dates[dates.get_loc(first):]:
        pr = 0.0
        if w:
            r = {s: (0.0 if np.isnan(rets.at[t, s]) else rets.at[t, s]) for s in w}
            pr = sum(w[s] * r[s] for s in w)
            w = {s: w[s] * (1 + r[s]) / (1 + pr) for s in w}
        cost = 0.0
        if t in trades:
            tgt = {s: 1.0 / len(trades[t]) for s in trades[t]}
            cost = sum(abs(tgt.get(s, 0.0) - w.get(s, 0.0)) for s in set(tgt) | set(w)) * cost_bps / 1e4
            w = tgt
        rows.append((t, pr - cost if t != first else -cost, spy_r.get(t, 0.0) if t != first else 0.0))
    return pd.DataFrame(rows, columns=["date", "port", "spy"]).set_index("date")


def forecast_by_rank(close, volume, spy, start, sectors, names=None, n=N_PICKS) -> dict:
    """Next-month return of each pick by rank bucket: the basis of trend_screen.FORECAST."""
    dates = close.index
    anchors = month_end_anchors(dates, start)
    rows = []
    for a, nxt in zip(anchors, anchors[1:]):
        buy, sell = dates[dates.get_loc(a) + 1], dates[dates.get_loc(nxt) + 1]
        scores = score_trend(close.loc[:a], volume.loc[:a], as_of=a)["score"]
        spy_r = spy[sell] / spy[buy] - 1
        for rank, s in enumerate(select_picks(scores, sectors, n, names=names), 1):
            r = close.at[sell, s] / close.at[buy, s] - 1
            rows.append((forecast_bucket(rank), r * 100, (r - spy_r) * 100))
    d = pd.DataFrame(rows, columns=["bucket", "ret", "exc"])
    return {b: {"mean_pct": round(float(g.ret.mean()), 1), "median_pct": round(float(g.ret.median()), 1),
                "low_pct": round(float(g.ret.quantile(0.1)), 1), "high_pct": round(float(g.ret.quantile(0.9)), 1),
                "beat_spy_pct": round(float((g.exc > 0).mean() * 100), 1)}
            for b, g in d.groupby("bucket", sort=False)}


def report(D: pd.DataFrame) -> dict:
    yrs = len(D) / 252
    eq, es = (1 + D.port).cumprod(), (1 + D.spy).cumprod()
    cagr, spy_cagr = eq.iloc[-1] ** (1 / yrs) - 1, es.iloc[-1] ** (1 / yrs) - 1
    xs = D.port - D.spy
    m = (1 + D).resample("ME").prod() - 1
    half = len(D) // 2

    def ann_xs(d):
        y = len(d) / 252
        return ((1 + d.port).prod() ** (1 / y) - (1 + d.spy).prod() ** (1 / y)) * 100

    dd, spy_dd = (eq / eq.cummax() - 1).min(), (es / es.cummax() - 1).min()
    return {
        "period": f"{D.index[0].date()} .. {D.index[-1].date()}",
        "cagr_pct": cagr * 100, "spy_cagr_pct": spy_cagr * 100, "excess_cagr_pct": (cagr - spy_cagr) * 100,
        "sharpe": D.port.mean() / D.port.std() * np.sqrt(252), "spy_sharpe": D.spy.mean() / D.spy.std() * np.sqrt(252),
        "information_ratio": xs.mean() / xs.std() * np.sqrt(252),
        "max_drawdown_pct": dd * 100, "spy_max_drawdown_pct": spy_dd * 100, "max_dd_vs_spy": dd / spy_dd,
        "months_beat_spy_pct": ((m.port - m.spy) > 0).mean() * 100,
        "excess_first_half_pct": ann_xs(D.iloc[:half]), "excess_second_half_pct": ann_xs(D.iloc[half:]),
        "excess_last_12m_pct": ann_xs(D[D.index > D.index[-1] - pd.Timedelta(days=365)]),
    }


def bar_rows(r: dict) -> list[tuple[str, bool]]:
    return [
        (f"Beats SPY by >= {BAR['excess_cagr_pct']:.0f} %/yr after costs ({r['excess_cagr_pct']:+.1f})", r["excess_cagr_pct"] >= BAR["excess_cagr_pct"]),
        (f"Sharpe above SPY's ({r['sharpe']:.2f} vs {r['spy_sharpe']:.2f})", r["sharpe"] > r["spy_sharpe"]),
        (f"Information ratio >= {BAR['information_ratio']} ({r['information_ratio']:.2f})", r["information_ratio"] >= BAR["information_ratio"]),
        (f"Beats SPY in >= {BAR['months_beat_spy_pct']:.0f}% of months ({r['months_beat_spy_pct']:.0f}%)", r["months_beat_spy_pct"] >= BAR["months_beat_spy_pct"]),
        (f"Positive in both halves ({r['excess_first_half_pct']:+.1f} / {r['excess_second_half_pct']:+.1f})", min(r["excess_first_half_pct"], r["excess_second_half_pct"]) > 0),
        (f"Positive in the last 12 months ({r['excess_last_12m_pct']:+.1f})", r["excess_last_12m_pct"] > 0),
        (f"Drawdown <= {BAR['max_dd_vs_spy']}x SPY's ({r['max_drawdown_pct']:.1f}% vs {r['spy_max_drawdown_pct']:.1f}%)", r["max_dd_vs_spy"] <= BAR["max_dd_vs_spy"]),
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--start", default="2017-11-01")  # covers pre-AI-boom years
    ap.add_argument("--cost-bps", type=float, default=6.0)
    ap.add_argument("--prices", help="directory with close.parquet and volume.parquet (saved after a download)")
    ap.add_argument("--tolerance", type=float, default=2.0, help="allowed drop in excess %/yr vs the record")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any row of the profit bar fails")
    ap.add_argument("--forecast", action="store_true", help="print next-month outcomes by rank (trend_screen.FORECAST)")
    args = ap.parse_args(argv)

    from quantify.data.universe import Universe
    universe = Universe.from_wikipedia()
    if args.prices and os.path.exists(os.path.join(args.prices, "close.parquet")):
        close = pd.read_parquet(os.path.join(args.prices, "close.parquet"))
        volume = pd.read_parquet(os.path.join(args.prices, "volume.parquet"))
    else:
        close, volume = download_prices(universe.tickers + ["SPY"], period="10y")
        if args.prices:
            os.makedirs(args.prices, exist_ok=True)
            close.to_parquet(os.path.join(args.prices, "close.parquet"))
            volume.to_parquet(os.path.join(args.prices, "volume.parquet"))
    spy = close.pop("SPY")
    volume = volume.drop(columns=["SPY"], errors="ignore")

    if args.forecast:
        print("FORECAST =", forecast_by_rank(close, volume, spy, args.start, universe.sector_map, universe.names))
        return 0
    r = report(simulate(close, volume, spy, args.start, universe.sector_map, universe.names, cost_bps=args.cost_bps))
    cap = "no sector cap" if MAX_PER_SECTOR is None else f"max {MAX_PER_SECTOR} per sector"
    print(f"pick-backtest: trend screen, {N_PICKS} picks ({cap}) from the {LIQUID_TOP} most-traded, monthly, "
          f"{args.cost_bps:g} bps/side, {r['period']}")
    print(f"  {r['cagr_pct']:.1f} %/yr vs SPY {r['spy_cagr_pct']:.1f} %/yr")
    rows = bar_rows(r)
    for label, ok in rows:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    print("  Caveat: universe is today's S&P 500 (survivorship bias); absolute returns are optimistic.")

    code = 0
    recorded = BACKTEST["excess_cagr_pct"] if args.cost_bps <= 6 else BACKTEST["excess_cagr_stress_pct"]
    if r["excess_cagr_pct"] < recorded - args.tolerance:
        print(f"REGRESSION: excess {r['excess_cagr_pct']:+.1f} %/yr is more than {args.tolerance} below the recorded {recorded:+.1f}")
        code = 1
    if args.strict and not all(ok for _, ok in rows):
        code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
