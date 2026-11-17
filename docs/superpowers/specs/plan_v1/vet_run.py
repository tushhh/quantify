"""Stage 2 of the PLAN_V1 vetting: one engine run per period for one variant.

usage: vet_run.py <main checkout> <vet dir> <variant>
variants: base, cost2x, delay1, u80, u120, alloc5050, earlier, later, c2007 (2007-2016)."""
import json, os, pickle, sys, logging
from datetime import date
repo, vet, variant = sys.argv[1:]
sys.path[:0] = [os.path.join(repo, "src"), repo]
logging.disable(logging.WARNING)
import pandas as pd
from api.schemas import BacktestRequest
from api.routers import backtest as R
from quantify.backtest.engine import BacktestEngine
from quantify.backtest.costs import CostModel

sel = json.load(open(os.path.join(vet, "selections.json")))["selections"]
prices = pickle.load(open(os.path.join(vet, "prices.pkl"), "rb"))
PERIODS = {
    "base": [("2017-01-01", "2021-12-31", "2016-12-30:100"), ("2022-01-01", "2026-11-13", "2021-12-31:100")],
    "c2007": [("2007-01-01", "2011-12-31", "2006-12-29:100"), ("2012-01-01", "2016-12-31", "2011-12-30:100")],
    "u80": [("2017-01-01", "2021-12-31", "2016-12-30:80"), ("2022-01-01", "2026-11-13", "2021-12-31:80")],
    "u120": [("2017-01-01", "2021-12-31", "2016-12-30:120"), ("2022-01-01", "2026-11-13", "2021-12-31:120")],
    "earlier": [("2016-12-01", "2021-11-30", "2016-11-30:100"), ("2021-12-01", "2026-11-13", "2021-11-30:100")],
    "later": [("2017-02-01", "2022-01-31", "2017-01-31:100"), ("2022-02-01", "2026-11-13", "2022-01-31:100")],
}
periods = PERIODS.get(variant, PERIODS["base"])
alloc = {"trend_following": 0.5, "cross_sectional_momentum": 0.5} if variant == "alloc5050" else \
        {"trend_following": 0.4615, "cross_sectional_momentum": 0.5385}

class DelayedEngine(BacktestEngine):
    def _slice_lookback(self, *a, **k):
        w = super()._slice_lookback(*a, **k)
        return {s: df.iloc[:-1] for s, df in w.items() if len(df) > 1}

out = []
for start, end, key in periods:
    uni = sel[key]
    strategies = {k: {"enabled": k in alloc, "allocation": alloc.get(k, 0.0)} for k in
                  ["trend_following", "cross_sectional_momentum", "pairs_mean_reversion", "quality_value", "ml_return_predictor", "volatility_regime"]}
    req = BacktestRequest(start_date=date.fromisoformat(start), end_date=date.fromisoformat(end), strategies=strategies, universe=uni + ["SPY"])
    lo = pd.Timestamp(start) - pd.DateOffset(years=2)
    data = {s: prices[s].loc[lo:end].copy() for s in uni + ["SPY"] if s in prices and len(prices[s].loc[lo:end])}
    cost = R._build_cost_model(req)
    if variant == "cost2x":
        cost = CostModel(commission_per_share=0.01, min_commission=2.0, spread_bps=10.0, market_impact_bps=20.0, slippage_pct=0.001)
    cls = DelayedEngine if variant == "delay1" else BacktestEngine
    eng = cls(strategies=R._build_strategy_instances(req), initial_capital=100_000.0, cost_model=cost,
              position_sizer=R._build_position_sizer(req), risk_manager=R._build_risk_manager(req),
              start_date=req.start_date, end_date=req.end_date, benchmark_symbol="SPY")
    res = eng.run(data)
    eq = res.equity_curve; eq.index = pd.DatetimeIndex(eq.index).tz_localize(None).normalize()
    spy = data["SPY"]["close"]; spy.index = pd.DatetimeIndex(spy.index).tz_localize(None).normalize()
    out.append(pd.DataFrame({"port": eq.pct_change(), "spy": spy.reindex(eq.index).pct_change()}).dropna())
    pd.DataFrame(res.trades).to_csv(os.path.join(vet, f"trades_{variant}_{start[:4]}.csv"), index=False)
    print(variant, start, end, "universe", len(uni), "with data", len(data) - 1, "trades", len(res.trades), flush=True)
pd.concat(out).to_csv(os.path.join(vet, f"daily_{variant}.csv"))
