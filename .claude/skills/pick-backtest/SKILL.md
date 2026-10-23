---
name: pick-backtest
description: Would Quantify's published stock picks have made money? Replays the production trend screen (quantify/trend_screen.py) month by month on past data, after trading costs, and checks it against the agreed profit bar (beat SPY by 3%/yr, Sharpe above SPY's, information ratio 0.5, 55% of months, both halves, last 12 months, drawdown within 1.25x SPY's). Fails if a change made the picks worse than the recorded result. Use before changing the picker, its constants, the universe or the pick count, when proposing a new model for /predict, or when the user asks whether the picks are any good historically.
---

# pick-backtest: does the picker beat SPY after costs?

## Run it

```bash
python scripts/backtest_picks.py --prices <scratch>/pick-prices          # downloads ~10y once, then reuses it
python scripts/backtest_picks.py --prices <scratch>/pick-prices --cost-bps 16   # cost stress
python scripts/backtest_picks.py --prices <scratch>/pick-prices --strict        # exit 1 on any failed bar row
```

It scores the list with the production `score_trend` from each month's last close (only data up to that close), buys at the next close, holds a month, and charges costs on every trade. Exit code 1 when excess return falls more than 2 points below `trend_screen.BACKTEST`, i.e. a change made it worse.

## What a result means

- The Oct 2026 record: +11.4 %/yr vs SPY after costs (2021-01..2026-10), beat SPY in 54-57% of months, but Sharpe about equal to SPY's, -1 %/yr in 2021-2023, and a ~-36% drawdown vs SPY's -24.5%. It passes the profit rows and fails the risk rows. Say that plainly; don't round it up.
- The universe is today's S&P 500, so absolute returns are optimistic (survivorship). Compare variants against each other on the same data.
- A variant only counts as better if it improves on the same data AND holds in both halves. Trying many variants and keeping the best is overfitting: report how many you tried.
- Backtests showing +20 %/yr or more over SPY are a red flag, not a win.

## Changing the picker

1. Change `quantify/trend_screen.py` and keep `tests/test_strategy/test_trend_screen.py` passing.
2. Run this skill before and after; report both tables.
3. If you adopt the change, update `BACKTEST` in `trend_screen.py` (the page shows it) with the new numbers.
4. The live record (`track-record` skill) is the final judge; a backtest is a hypothesis.
