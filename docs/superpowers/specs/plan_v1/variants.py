"""Score the three pre-registered variants on the agreed bar.
usage: variants.py <main worktree> <bar dir>
1 raw strategy; 2 market filter + 5% loss limit; 3 market filter + 20% loss limit.
Rules (fixed before results): decisions on day t's close apply from t+1.
Market filter: invested only while SPY close > its 200-day SMA.
Loss limit L: if overlay equity closes >= L below its peak since last entry, go to cash,
stay out >= 21 trading days, then re-enter when the market filter is positive.
Every exit/entry costs 0.2% of equity."""
import sys, os
wt, bar = sys.argv[1:]
sys.path[:0] = [os.path.join(wt, "scripts"), os.path.join(wt, "src"), wt]
import numpy as np, pandas as pd, yfinance as yf
from backtest_picks import report, bar_rows

D = pd.concat([pd.read_csv(os.path.join(bar, f), index_col=0, parse_dates=True) for f in ("daily_2017.csv", "daily_2022.csv")])
spx = yf.download("SPY", start="2015-06-01", end="2026-11-15", progress=False, auto_adjust=True)["Close"].squeeze()
spx.index = pd.DatetimeIndex(spx.index).tz_localize(None).normalize()
above = (spx > spx.rolling(200).mean()).reindex(D.index).ffill()
SWITCH = 0.002

def overlay(limit):
    invested, eq, peak, out_days, stopped = bool(above.iloc[0]), 1.0, 1.0, 0, False
    rets, n_stops, n_switch, cash_days = [], 0, 0, 0
    for i, (d, row) in enumerate(D.iterrows()):
        r = row.port if invested else 0.0
        eq *= 1 + r
        cash_days += not invested
        # decide for tomorrow using today's close
        want = bool(above.loc[d])
        if invested:
            peak = max(peak, eq)
            if limit is not None and eq / peak - 1 <= -limit:
                want, stopped, out_days = False, True, 0
                n_stops += 1
        elif stopped:
            out_days += 1
            if out_days < 21:
                want = False
            elif want:
                stopped = False
        if want != invested:
            eq *= 1 - SWITCH; r = (1 + r) * (1 - SWITCH) - 1; n_switch += 1
            invested = want
            if invested: peak = eq
        rets.append(r)
    out = D.copy(); out["port"] = rets
    return out, n_stops, n_switch, cash_days / len(D)

rows = []
for name, limit in [("1 raw strategy", "raw"), ("2 filter + 5% limit", 0.05), ("3 filter + 20% limit", 0.20)]:
    if limit == "raw":
        X, stops, sw, cash = D, 0, 0, 0.0
    else:
        X, stops, sw, cash = overlay(limit)
    r = report(X)
    beta = np.cov(X.port, X.spy)[0, 1] / X.spy.var(); alpha = (X.port.mean() - beta * X.spy.mean()) * 252 * 100
    checks = bar_rows(r) + [(f"Positive alpha after beta ({alpha:+.1f}%/yr)", alpha > 0)]
    yr = ((1 + X).resample("YE").prod() - 1) * 100
    print(f"\n=== {name}: CAGR {r['cagr_pct']:.1f}% vs SPY {r['spy_cagr_pct']:.1f}% | worst drop {r['max_drawdown_pct']:.1f}% vs SPY {r['spy_max_drawdown_pct']:.1f}% | "
          f"stops {stops}, switches {sw}, in cash {cash:.0%} of days | passes {sum(ok for _, ok in checks)}/{len(checks)}")
    for label, ok in checks: print(("   PASS " if ok else "   FAIL ") + label)
    print("   by year:", ", ".join(f"{y.year} {a:+.0f}/{b:+.0f}" for y, (a, b) in zip(yr.index, yr[["port", "spy"]].values)))
