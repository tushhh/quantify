# PLAN_V1 vetting: pre-registered checks

Written 2026-11-17, **before** any of these checks were run. Pass marks must not be changed after
results are seen. Each check is run once. A failed check is reported as failed, never re-tuned.

- **Base:** `PLAN_V1` as tested in `bar_test.py`. The strategies are trend_following 0.4615 and
  cross_sectional_momentum 0.5385, long-only. The engine uses app defaults for costs, sizing and risk,
  and is built via `_build_strategy_instances`.
- **Benchmark:** SPY total return (adjusted closes).

| # | Check | Method | Pass mark |
|---|---|---|---|
| A | Lookahead | `pandas-ta-executor` checker on every feature the two strategies read. | No lookahead or drift finding on those features. |
| B | Survivorship | Universe = top 100 by 63-day median dollar volume among stocks that were S&P 500 members **on the selection date** (end-2016, end-2021). Membership is rebuilt from today's list plus Wikipedia's "Selected changes" table, reversed. Delisted names are included where Yahoo still has data, and coverage is reported. | Full 2017-2026 excess CAGR vs SPY > 0 after costs, and Sharpe ≥ SPY's. |
| C | 2008 and the 2010s | Periods 2007-2011 (universe at end-2006) and 2012-2016 (universe at end-2011). Same method as B. | Excess CAGR > 0 over 2007-2016, and worst drop ≤ 1.25× SPY's. |
| D | Double costs | B's setup with every cost parameter doubled: commission $0.01/share (min $2), spread 10 bps, impact 20 bps, slippage 0.10 %. | Excess CAGR > 0. |
| E | One-day delay | B's setup, with every strategy seeing data one bar older (signals act a day late). | Excess CAGR > 0. |
| F | Settings | B's setup with each change made once: universe 80; universe 120; allocations 0.50/0.50; all periods starting one month earlier; all periods starting one month later. | Excess CAGR > 0 in **every** variant. |
| G | Concentration | From B's trades, remove the realised P&L of the 5 symbols with the largest total P&L. Recompute the CAGR from the remaining P&L. | Excess CAGR > 0. |
| H | Luck | Stationary block bootstrap (mean block length 21 trading days, 10,000 resamples) of B's daily (strategy − SPY) returns. | Excess CAGR > 0 in ≥ 90 % of resamples. |
| I | Owner's 5 % limit | Same bootstrap on strategy returns: the chance of a ≥ 5 % drop from peak within 1 year, and the median worst drop over 1 year and over 5 years. | Information only. |

**Decision rule.** If B, C or H fails, recommend **not** building the plan on `PLAN_V1`. If only D, E, F
or G fail, report each one as a specific weakness and let the owner decide.

## Results (run 2026-11-18, pass marks unchanged)

Full output: `vetting_results.txt`. Universes: `vet_selections.json`. The point-in-time membership
comes from Wikipedia revision 1314254751, with renames BK→BNY, MMC→MRSH and FI→FISV. Yahoo has no
prices for most delisted members (2006: 320 of 516 priced), so survivorship bias is reduced, not
removed. Results are still somewhat optimistic.

| Check | Result |
|---|---|
| A lookahead | PASS |
| B survivorship | **FAIL**: +16.1 %/yr vs SPY 14.8 %, Sharpe 0.81 vs 0.85 |
| C 2007-2016 | PASS: +1.0 %/yr excess, worst drop −45.5 % vs −55.2 % |
| D double costs | PASS: +0.3 %/yr |
| E one-day delay | PASS: +4.6 %/yr |
| F settings | PASS: +0.7 to +2.1 %/yr in all five |
| G without the top 5 | **FAIL**: 9.9 %/yr vs 14.8 % without MU, NVDA, AVGO, AMD, NFLX |
| H luck | **FAIL**: beats SPY in 61.8 % of resamples (needed 90 %) |
| I 5 % limit | 99 % chance of a 5 %+ drop in a year; median worst yearly drop −14.7 % |

Verdict under the pre-registered rule: **do not build the plan on PLAN_V1** (B and H failed).
