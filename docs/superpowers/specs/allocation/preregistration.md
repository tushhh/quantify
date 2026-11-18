# Asset-allocation strategies: pre-registered test

Written 2026-11-18, **before** any results. Rules, data and the bar must not change after results are
seen. Each strategy is run once, as published. Nothing is tuned.

## Owner's goal

Compound money as much as possible over 5-10 years, with losses deep enough to hurt but never deep
enough to become permanent. The owner chose the safest bar that still aims for strong long-run growth
(bar B).

## Strategies (rules as published; ETFs as the published versions use them)

1. **Faber GTAA-5** (Faber, *A Quantitative Approach to Tactical Asset Allocation*, 2007).
   - Assets: VTI, EFA, IEF, VNQ, DBC, equal 20 % each.
   - Each asset is held only if its month-end close is above its 10-month simple moving average of
     month-end closes. Otherwise that 20 % goes to cash.
   - Published 2007; unseen period 2008-01 onwards.
2. **Antonacci Global Equities Momentum (GEM)** (*Dual Momentum Investing*, 2014).
   - If SPY's 12-month total return beats cash (BIL / T-bills) over the same 12 months, hold whichever
     of SPY or EFA had the higher 12-month return. Otherwise hold AGG.
   - Published 2014; unseen period 2015-01 onwards.
3. **Keller & Keuning VAA-G4** (*Breadth Momentum and Vigilant Asset Allocation*, 2017).
   - Offensive assets: SPY, EFA, EEM, AGG. Defensive assets: LQD, IEF, SHY.
   - Momentum score = 12·r1 + 4·r3 + 2·r6 + 1·r12, where rN is the N-month total return.
   - If every offensive score is > 0, hold 100 % of the best offensive asset. Otherwise hold 100 % of
     the best defensive asset.
   - Published 2017-07; unseen period 2017-08 onwards.
4. **Baselines:**
   - SPY buy and hold;
   - 60/40 SPY/IEF, rebalanced monthly.

## Mechanics (all strategies)

- **Data:** Yahoo adjusted closes (total return, dividends reinvested). Cash = BIL. Before BIL exists
  (2007-05), cash = SHY. Data runs to 2026-11-13.
- **Timing:** signals use month-end closes. Trades execute at the **next trading day's close**, so there
  is no same-day lookahead.
- **Costs:** 0.20 % of each traded dollar (each side), on the turnover at every rebalance. This is above
  the app's default ~0.17 % and well above the owner's commission-free broker.
- **Full period:** from the first month-end where every asset in that strategy, plus SPY, has 12 months
  of history, through 2026-10.

## The bar (judged on each strategy's unseen period, after costs)

| # | Row | Pass mark |
|---|---|---|
| 1 | Worst drop (peak to trough, daily) | no deeper than −20 % |
| 2 | Compounds close to SPY | CAGR ≥ SPY's CAGR − 2.0 points over the same period |
| 3 | Return per unit of risk | Sharpe ≥ SPY's |
| 4 | Losses aren't permanent | longest stretch below a previous peak ≤ 24 months |
| 5 | Steady over time | worst rolling 5-year CAGR > 0 (over the full period, for enough 5-year windows) |
| 6 | Not a fluke | stationary block bootstrap (mean block 21 days, 10,000 resamples): worst drop no deeper than −25 % in ≥ 80 % of resamples, and CAGR ≥ SPY − 2.0 in ≥ 60 % |

- Also reported, as information only: the full-period numbers, results year by year, the numbers at
  double costs, and the number of trades a year.
- **Winner:** among strategies that pass all six rows, the one with the highest unseen-period CAGR. If
  none pass, report that plainly, with the closest one and the rows it failed. Don't loosen the bar.
