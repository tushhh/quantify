# How each strategy did when tested

These are the test results behind the labels on the Strategies page (`TEST_RESULTS` in
`api/routers/strategies.py`). They were written 2026-11-19. Update both when a strategy is re-tested.

## Two kinds of test

1. **Without hindsight (the fair test).** Stocks are chosen from the companies that were actually in
   the S&P 500 at the start of each period, 2017-2026, including ones that later fell out. Pass marks
   are fixed before the run. Details and results: `docs/superpowers/specs/plan_v1/vetting.md` on the
   `feat/strategy-plan` branch.
2. **With hindsight (flatters every strategy).** These use the app's default universe: today's 20
   largest US stocks (AAPL, MSFT, NVDA, ...), 2021-01-01 to 2026-11-01. The universe was picked
   knowing these companies became winners, so it overstates returns. A strategy that loses here, or
   lags SPY, has no excuse.

## Solo runs with hindsight (one strategy at a time, app defaults, long-only)

| Strategy | Total return | Per year | Sharpe | Worst drop | Trades | SPY total |
|---|---|---|---|---|---|---|
| Trend following | +158.7 % | +17.8 % | 1.10 | −24.3 % | 136 | +121.2 % |
| Cross-sectional momentum | +88.7 % | +11.6 % | 1.03 | −13.9 % | 58 | +121.2 % |
| Pairs mean reversion | −2.3 % | −0.4 % | −0.18 | −4.6 % | 22 | +121.2 % |
| Quality value | +142.9 % | +16.5 % | 1.60 | −12.0 % | 33 | +121.2 % |
| ML return predictor | −7.9 % | −1.4 % | −0.15 | −20.8 % | 619 | +121.2 % |

Volatility regime wasn't run alone: it reads today's VIX, so a past test would see the future.

## Verdicts

| Strategy | Label | Why |
|---|---|---|
| Trend following | Matched SPY, no edge | Fair test: 15.0 %/yr vs SPY's 14.8 %. Without its top 5 stocks 10.8 %/yr. Beat SPY in only 52.8 % of luck-test resamples (90 % needed). |
| Cross-sectional momentum | Didn't beat SPY | It lagged SPY even with hindsight. Combined with trend following in the fair test it made 16.1 %/yr vs 14.8 %, but failed the concentration and luck checks. |
| Pairs mean reversion | Lost money | −2.3 % with hindsight while SPY made +121.2 %. |
| Quality value | Can't be tested fairly | It uses today's company fundamentals for every past date, so its +142.9 % sees the future. |
| ML return predictor | Lost money | −7.9 % with hindsight. Its monthly picks also lost to SPY after costs in the walk-forward test (Oct 2026). |
| Volatility regime | Can't be tested fairly | It reads today's VIX for every past date, so any backtest of it sees the future. |
