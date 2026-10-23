---
name: track-record
description: Did the picks Quantify actually published make money? Scores every monthly list recorded on the append-only pick-history branch against what the stocks did afterwards vs SPY (bought at the first close after the list date, held until the next list, after costs). Use when the user asks how the picks have done, whether the model can be relied on, before trusting a backtest, or monthly to report the record.
---

# track-record: the live scoreboard

## Run it

```bash
git fetch origin pick-history
git show origin/pick-history:picks.jsonl > <scratch>/picks.jsonl
python scripts/track_record.py score --history <scratch>/picks.jsonl --json <scratch>/record.json
```

Prints one row per list (picks' return, SPY's return, excess, best and worst name) and the total since the first list. The most recent list is marked `open` while it is still being held.

## How lists get recorded

`screener_cron.yml` runs `track_record.py append` after every screen. It adds a list only when its `as_of` date is new (once a month), with a normal push to `pick-history`. Never force-push, rewrite or delete that branch: it is the only honest evidence of how the picks did, and the branch guard blocks it.

## Reading it

- Recording started with the 2026-09-30 list. Fewer than ~12 closed months is too short to conclude anything; say so.
- Judge it with the same bar as `pick-backtest` (beat SPY by ~3 %/yr, more months up than down vs SPY, drawdown not much worse than SPY's).
- If the live record trails the backtest for a long stretch, the backtest was too optimistic (survivorship, a regime change). Report it to the user rather than tuning the picker until the history looks good.
