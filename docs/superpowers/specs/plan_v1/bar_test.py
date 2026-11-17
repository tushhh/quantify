"""Pre-registered test of the backtest strategy mix against the agreed profit bar.

usage: bar_test.py <main worktree> <pick-prices dir> <out dir> [--with-quality]
Periods and universes are fixed in advance: each period trades the 100 most-traded
(median dollar volume over the prior ~2-3 months) current S&P 500 members at its start.
"""
import json, logging, math, os, sys
from datetime import date
wt, prices_dir, out_dir, *flags = sys.argv[1:]
sys.path[:0] = [os.path.join(wt, "src"), wt, os.path.join(wt, "scripts")]
logging.basicConfig(level=logging.ERROR)
import numpy as np, pandas as pd
from api.schemas import BacktestRequest
from api.routers import backtest as R
from quantify.backtest.engine import BacktestEngine
from backtest_picks import report, bar_rows

WITH_Q = "--with-quality" in flags
close = pd.read_parquet(os.path.join(prices_dir, "close.parquet"))
volume = pd.read_parquet(os.path.join(prices_dir, "volume.parquet"))
PERIODS = [("2017-01-01", "2021-12-31", "2016-12-30"), ("2022-01-01", "2026-11-13", "2021-12-31")]

def universe_at(asof, n=100):
    c, v = close.loc[:asof].drop(columns=["SPY"], errors="ignore"), volume.loc[:asof].drop(columns=["SPY"], errors="ignore")
    dv = (c * v).tail(63).median().dropna()
    return list(dv.sort_values(ascending=False).index[:n])

alloc = {"trend_following": .30, "cross_sectional_momentum": .35, "quality_value": .25 if WITH_Q else None}
strategies = {k: {"enabled": False, "allocation": 0.0} for k in
              ["trend_following", "cross_sectional_momentum", "pairs_mean_reversion", "quality_value", "ml_return_predictor", "volatility_regime"]}
tot = sum(a for a in alloc.values() if a)
for k, a in alloc.items():
    if a: strategies[k] = {"enabled": True, "allocation": a / tot}

daily = []
for start, end, asof in PERIODS:
    uni = universe_at(asof)
    req = BacktestRequest(start_date=date.fromisoformat(start), end_date=date.fromisoformat(end),
                          strategies=strategies, universe=uni + ["SPY"])
    fetch_start = date(int(start[:4]) - 2, 1, 1)
    res = R._fetch_data(uni + ["SPY"], fetch_start, date.fromisoformat(end))
    data = res.data
    if WITH_Q:
        from quantify.data.fundamentals import fetch_fundamentals, add_fundamental_features
        data = add_fundamental_features(data, fetch_fundamentals(list(data)))
    eng = BacktestEngine(strategies=R._build_strategy_instances(req), initial_capital=100_000.0,
                         cost_model=R._build_cost_model(req), position_sizer=R._build_position_sizer(req),
                         risk_manager=R._build_risk_manager(req), start_date=req.start_date, end_date=req.end_date,
                         benchmark_symbol="SPY")
    result = eng.run(data)
    eq = result.equity_curve
    spy = data["SPY"]["close"]; spy.index = pd.DatetimeIndex(spy.index).tz_localize(None).normalize()
    eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    D = pd.DataFrame({"port": eq.pct_change(), "spy": spy.reindex(eq.index).pct_change()}).dropna()
    daily.append(D)
    t = result.trades
    print(f"== {start}..{end}: universe {len(uni)} (skipped {sorted(res.failed_symbols)}), trades {len(t)}, "
          f"by strategy {pd.Series([x['strategy_name'] for x in t]).value_counts().to_dict()}")
    r = report(D)
    print(f"   CAGR {r['cagr_pct']:.1f}% vs SPY {r['spy_cagr_pct']:.1f}% | excess {r['excess_cagr_pct']:+.1f}%/yr | Sharpe {r['sharpe']:.2f} vs {r['spy_sharpe']:.2f} | maxDD {r['max_drawdown_pct']:.1f}% vs {r['spy_max_drawdown_pct']:.1f}%")
    D.to_csv(os.path.join(out_dir, f"daily_{start[:4]}{'_q' if WITH_Q else ''}.csv"))

D = pd.concat(daily)
r = report(D)
beta = np.cov(D.port, D.spy)[0, 1] / D.spy.var()
alpha = (D.port.mean() - beta * D.spy.mean()) * 252 * 100
yr = ((1 + D).resample("YE").prod() - 1) * 100
print("\n== FULL", r["period"], "| beta %.2f, alpha %+.1f%%/yr" % (beta, alpha))
for label, ok in bar_rows(r):
    print(("  PASS " if ok else "  FAIL ") + label)
print(f"  {'PASS' if alpha > 0 else 'FAIL'} Positive alpha after beta ({alpha:+.1f}%/yr)")
print("\nby year (strategy vs SPY):")
for y, row in yr.iterrows(): print(f"  {y.year}: {row.port:+.1f}% vs {row.spy:+.1f}%")
json.dump({k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in r.items()} | {"alpha": alpha, "beta": beta},
          open(os.path.join(out_dir, f"bar{'_q' if WITH_Q else ''}.json"), "w"))
