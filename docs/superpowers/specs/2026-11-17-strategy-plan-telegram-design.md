# Strategy plan via the Quantify Trades bot: design

Status: draft for the owner's approval, 2026-11-17.

## Intent

The owner wants the backtest to prove a strategy before they use it, and then wants the app to tell them
exactly what to trade and when, sized to the money they choose to put in. They don't want to be a guinea
pig, and they have lost thousands to the app's early, untested strategies. So the live plan must trade
**exactly** the configuration that was tested, nothing re-implemented or tuned afterwards. Every
instruction is recorded so the live record can be compared with the backtest.

## What was tested (the only thing the plan may trade)

Pre-registered test on 2026-11-17 against the agreed profit bar. 2017-2021 and 2022-2026 were run as
separate periods, each with its own universe. Result: +20.2 %/yr vs SPY +14.9 % after default costs.
It passed 6 of 8 rows. It failed the information ratio (0.41 < 0.5) and months beating SPY
(52 % < 55 %). Worst drop was -31 % vs SPY -34 %. The owner chose to build the plan anyway, knowing this.

Configuration (call it `PLAN_V1`):

- Strategies: `trend_following` and `cross_sectional_momentum`, with allocations **passed explicitly as
  0.4615 and 0.5385** (0.30 / 0.35 normalised; the test passed these values directly, and no engine
  code normalises). Long-only (`allow_short` False). Default strategy parameters.
- Universe: the 100 S&P 500 members with the highest 63-day median dollar volume as of 2021-12-31. This
  is the test's period-2 universe. Membership is the S&P 500 as of the Oct 2026 price cache, so it
  includes both GOOG and GOOGL.
  - The exact list is committed in `docs/superpowers/specs/plan_v1/plan_v1.json`. Use that file; don't
    regenerate it. Wikipedia membership and `get_sp500()` would give a different list.
- Engine: built directly, as in the test script, not through `_run_backtest_sync`, so there are no
  fundamentals, sector or earnings features. Components come from the router builders for a default
  `BacktestRequest`:
  - `_build_cost_model`, `_build_position_sizer`, `_build_risk_manager`: the default cost model,
    `EqualWeightSizer` (max position 10 %) and the `PortfolioRiskManager` defaults;
  - start 2022-01-03, benchmark SPY, $100,000 notional;
  - data fetched with `_fetch_data(symbols + ["SPY"], 2020-01-01, today)`.
- Code version: the test ran on `main` at d2606e5, which has whole shares. If the fractional-shares
  change (branch `fix/backtest-idle-capital`) is merged, run `PLAN_V1` with whole shares (fractional off),
  so the engine stays as tested. Fractional shares apply only to the user's order sizing on the server.
- Reference artifacts in `docs/superpowers/specs/plan_v1/`:
  - the test scripts, `bar_test.py` and `variants.py`;
  - the daily returns, `daily_2017.csv` and `daily_2022.csv`;
  - `plan_v1.json`, with the universe and the constants below.
- Acceptance check for the nightly script: run from 2022-01-03 to 2026-11-13, it must reproduce the
  test's period-2 daily returns (`daily_2022.csv`) to within rounding.
- Excluded: quality_value (it uses today's fundamentals) and volatility_regime (it uses live VIX).
  pairs_mean_reversion and ml_return_predictor are excluded because they lost money.
- Safety overlays (SPY 200-day filter, 5 % / 20 % stop) were tested and rejected. They lowered returns
  and still let the portfolio fall 28-36 %. They are not part of the plan.

## Goals

1. **Nightly book.** Each US trading night, compute the strategy's current holdings with the tested code.
2. **Instructions over Telegram.** For each user with an active plan, turn changes in the holdings into
   buy and sell instructions sized to their plan amount, with fractional shares. Send them through the
   existing **Quantify Trades** bot (`api/telegram_bot.py`).
3. **Done buttons.** The user taps ✅ Done under an instruction, and the bot records the trade in
   /portfolio (`Trade` rows) at the reference price. The user can correct the price.
4. **Weekly summary.** Plan value vs SPY since the plan started, plus any open instructions.
5. **Warnings.** Say plainly when the plan is behaving worse than anything seen in testing (see Safety).
6. **Track record.** Log every nightly book and every instruction, so live results can be scored against
   SPY and against the backtest.

## Non-goals

- Placing orders at a broker. The app tells; the user trades. No IBKR integration in this work.
- Shorting, leverage, or strategies other than `PLAN_V1`.
- A web page for the plan. Telegram only for v1. /portfolio already shows the recorded trades.
- Investment advice on how much to put in. The plan amount is the user's choice.
- Rolling the universe to a new period (the test's next period would start 2027). This is deferred: see
  Left to the builder.

## Anti-goals (failures even if it "works")

- Telling the user to trade anything other than what `PLAN_V1` holds.
- Old alert logic contradicting the plan. The existing hold-period, dip and hold-health alerts must
  ignore plan trades.
- Blending backtest numbers with live numbers in any message.
- Message spam: no message on nights with no changes, and at most one warning per state change.
- Selling the user out automatically. Warnings recommend; the user decides.

## Constraints

- Heroku has 512 MB, so the engine must not run on the web dyno. The engine runs on GitHub Actions, and
  Heroku does only sizing, storage and messaging.
- Protected areas (CLAUDE.md):
  - Telegram notification logic: the owner explicitly asked for this.
  - Database schema: **needs the owner's explicit OK** (tables below).
- `main` deploys to Vercel and Heroku. Work on `feat/strategy-plan` and hand over a PR.
- The model-cache, screener-cache and pick-history branches are untouched. No new data branches.
- Secrets come from repo secrets, never from workflow inputs. Internal endpoints call `_verify_secret`.
- GitHub schedules can start hours late. The user acts at the next US open, about 14 h after the close,
  so a late start is fine. A run that hasn't arrived by 12:00 UTC is reported (see Failure handling).

## Approaches considered

1. **Nightly engine run on GitHub Actions + callback to Heroku. Chosen by the owner.** It runs the exact
   tested code, the pattern already exists (`backtest.yml` → `/api/internal/backtest-complete`), and it
   stays within Heroku memory.
2. **Engine on Heroku via APScheduler.** Rejected: 100 symbols over 5 years exceeds 512 MB, and memory is
   a known Heroku issue.
3. **Re-implement the rules in a light signal function.** Rejected: it drifts from what was tested, which
   is the failure that cost the owner money before.

## Design

### 1. Nightly job: `.github/workflows/plan_cron.yml` + `scripts/run_plan.py`

- Schedule: weekdays at 22:30 UTC (after the 21:00 UTC close), plus `workflow_dispatch`.
- The script:
  1. Fetches daily OHLCV for the 100 `PLAN_V1` symbols and SPY, from 2020-01-01 to today, through the
     existing provider (`_fetch_data`).
  2. Builds the engine exactly as in `PLAN_V1` and runs it from 2022-01-03 to the latest close.
  3. Reads two things from the engine through a small read-only public accessor. This is the only
     engine change, and it is approved as part of this work.
     - **Holdings:** the per-strategy books after the last bar.
     - **Tonight's orders:** the orders the engine submitted on the last bar. These fill at the next
       open in the backtest, so they are what the user must place at the next US open. Without them
       the user would trade one day behind the test. (Builder's call.)
  4. Converts both to weights relative to equity at the last close: holdings weight = value / equity,
     order weight = shares × last close / equity. They are kept **per strategy**,
     `{strategy: {symbol: weight}}`, because the two strategies can hold the same stock separately.
     Then it POSTs the snapshot to `/api/internal/plan-snapshot` with `X-Internal-Secret`. The snapshot
     carries:
     - `as_of`: the last close date
     - `holdings`
     - `orders`: per strategy and symbol, `buy` with its weight, or `sell_all`
     - last-close prices for every symbol involved
     - `equity`
     - `config_id` = `PLAN_V1`
     - code SHA and engine `run_id`
- Instructions come **only from tonight's orders**, never from diffing tonight's re-run against last
  night's. A full re-run can rewrite history slightly: prices get dividend-adjusted, shares are whole and
  cash is checked. The stored history is never rewritten. (Builder's call.)
  - Drift is checked and reported, not acted on: tonight's holdings minus tonight's orders should equal
    last night's holdings plus last night's orders. Any mismatch is logged on the snapshot and shown to
    the owner in the weekly summary.
- **All 100 symbols and SPY must download.** If any are missing after the provider's retry, the night
  fails: no snapshot, no instructions, and a red run in GitHub. A missing stock would silently remove its
  holding and reshuffle momentum ranks. (Builder's call.)
- Failure handling: any exception, or a callback error, exits non-zero so the run shows red in GitHub.
  This is unlike `run_backtest.py`, which logs callback failures and still succeeds.

### 2. Server: `/api/internal/plan-snapshot` and order generation

- Store each snapshot in `plan_snapshots`. It is append-only, keyed by `as_of`; a duplicate `as_of`
  replaces nothing and returns 200.
- Turn the snapshot's `orders` into instructions for each active plan, per strategy and symbol:
  - **`buy`**: dollars = order weight × the plan's current value. Shares = dollars / last close, rounded
    down to 4 dp. Skip it if under $1.
  - **`sell_all`**: sell all of the plan's shares held for that strategy-symbol.
  - Held positions are never resized. The engine doesn't resize them either.
- **Plan holdings are separate `Trade` rows.** (Builder's call.)
  - Each row is tagged with `plan_id` and `plan_strategy`, one per plan, strategy and symbol. They are
    never merged with the user's own hand-entered positions in the same stock.
  - This needs plan-aware create and reduce functions next to `create_or_aggregate_trade` /
    `reduce_trade_shares`, because the existing ones merge on user and symbol and reset `sell_date`.
  - Manual `/buy` and `/sell` leave plan rows alone. `/portfolio` lists plan rows under a "Plan" label.
- **Top-up (`/plan 5000` on an active plan)** buys into the current holdings in proportion, like a new
  start, so the money tracks the strategy immediately. (Builder's call.)
- **Skipped instructions.** (Builder's call.)
  - A skipped buy leaves its cash uninvested.
  - A skipped sell credits plan cash at the reference price as if sold, and clears the row's `plan_id`
    (the shares become the user's own).
  - Either way, plan accounting keeps following the strategy, so skips don't show up as plan losses or
    warnings. The weekly summary counts the skips.
- Plan value = the plan's cash plus its open plan trades at last-close prices.
  - Plan cash = amount put in − buys done + sells done.
  - If the plan's cash can't cover all buys, scale the buys down proportionally. Never borrow.
- Messages go out after the snapshot is stored, through the trades bot's send helper.

### 3. Telegram: Quantify Trades bot (`api/telegram_bot.py`)

Account linking works as it does now (`/start`, `telegram_chat_id`).

| Command / button | Behaviour |
|---|---|
| `/plan 5000` | Start or top up a plan with $5,000. On start, the bot shows the test result in one line (6/8 rows passed, worst drop −31 %) and asks to confirm. Once confirmed, it sends the **current** book scaled to the amount as buy instructions. |
| `/plan` | Status: amount in, value, return vs SPY since start, open instructions. |
| `/plan withdraw 1000` | Lower the plan amount. The bot proposes proportional sells across holdings. |
| `/plan stop` | Lists sell-all instructions for every plan holding, with Done buttons. The plan becomes stopped once they are done. |
| ✅ Done | Records the trade in /portfolio at the reference price: `create_or_aggregate_trade` for buys, `reduce_trade_shares` / `close_trade_full` for sells. The trade is tagged with the plan. The message is edited to show it is done. |
| ✏️ Price | Asks for the actual fill price, then records the trade at that price. |
| ⏭ Skip | Marks the instruction skipped. The holding is then off-plan, and the weekly summary shows how many were skipped. |

Example nightly message (sketch):

```
📋 Plan update — Tue 18 Nov (after US close)
Place these at the next US open:

BUY  NVDA  ~$382  (2.0312 sh @ $188.07)   [✅ Done] [✏️ Price] [⏭ Skip]
SELL XOM   all 3.4410 sh (~$402)           [✅ Done] [✏️ Price] [⏭ Skip]

Plan: $5,000 in · value $5,214 (+4.3%) · SPY +2.9% since 3 Nov
```

Weekly summary: Saturdays at 01:00 UTC. It shows plan value vs SPY since start, best and worst holding,
and open or skipped instructions. Backtest numbers appear only on a separate, labelled line.

### 4. Safety warnings (no automatic selling)

Testing showed that selling everything at fixed loss limits made results worse, so warnings inform and
the user decides.

- **Heads-up at −5 % from the plan's peak**, the owner's stated comfort level. It says this is normal for
  the strategy (it fell 5 % or more from a peak 23 times in 2017-2026), shows the
  backtest's worst (−31 %), and offers `/plan stop`. It is sent once per new −5 % step: −5, −10, −15 …
- **Red flag** when the plan is worse than anything in testing:
  - a drop from peak beyond −31 %, or
  - a trailing-12-month return behind SPY by more than 19.5 points, the worst gap in the test
    (`worst_trailing_12m_gap_vs_spy` −0.1945 in `plan_v1.json`, reached 2023-11-06).
  - The −31 % threshold is `max_drawdown` −0.3095 in the same file.

  The red flag says the strategy is behaving outside its tested range, recommends stopping, and offers
  the stop button.
- Plans younger than 12 months use only the drawdown test.

### 5. Data (needs the owner's OK: new tables, one new column)

- `plan_snapshots`: `id`, `as_of` (date, unique), `config_id`, `weights_json`, `prices_json`,
  `equity`, `code_sha`, `run_id`, `created_at`.
- `plans`: `id`, `user_id` (unique), `config_id`, `amount_in`, `cash`, `status` (active / stopping /
  stopped), `started_at`, `peak_value`, `last_warning_level`, `created_at`.
- `plan_instructions`: `id`, `plan_id`, `snapshot_id`, `strategy`, `symbol`, `action` (buy / sell),
  `shares`, `ref_price`, `status` (pending / done / skipped), `fill_price`, `trade_id`, `created_at`,
  `done_at`.
- `trades.plan_id` (a nullable FK) and `trades.plan_strategy` (a nullable string), added through the
  existing `ensure_trade_columns()` pattern. Plan trades carry both. `check_alerts_loop` and the
  hold-health and dip alerts **skip rows where `plan_id` is set**. This needs a regression test.
- New tables are created by `create_all` at startup, as the existing ones are.

### 6. Track record

`plan_snapshots` and `plan_instructions` are the record. `scripts/plan_track_record.py` scores:

- the strategy's live book since the first snapshot vs SPY, and
- each user's executed plan vs SPY,

with backtest and live numbers in separate columns. A `track-record`-style skill can call it later.

### 7. Testing

- `run_plan.py`:
  - on synthetic data (the crosscheck fixtures), holdings weights sum to ≤ 1, there are per-strategy
    books with no shorts, and tonight's orders are exactly the orders submitted on the last bar;
  - a missing symbol fails the run;
  - the real-data reproduction check against `daily_2022.csv` (see What was tested) runs once by hand
    and is recorded in the PR.
- Snapshot → instructions:
  - `buy` and `sell_all` per strategy
  - the $1 minimum
  - proportional scaling when cash is short
  - no instruction for held positions without an order
  - a duplicate `as_of` is idempotent
  - drift is logged, not acted on
- Plan rows stay separate from manual rows. Manual `/sell` never touches plan rows.
- Skip accounting: a skipped sell credits cash and untags the row.
- Endpoint: 403 without the secret.
- Telegram handlers with stub `update`/`context`:
  - `/plan` start, top-up, withdraw and stop
  - the Done, Price and Skip buttons
  - a Done records a tagged `Trade`
- Regression: the alert loop ignores plan-tagged trades.
- Warnings: −5 % steps fire once each, and the red-flag thresholds work.
- CI: `ruff check .`, `pytest`, `boot-like-heroku`. Run `16-eyes` and `deep-security-check` before the PR.

## Left to the builder

- Exact wording of messages, within the sketch and the copy rules in CLAUDE.md (sentence case, specific
  numbers, no hype).
- Retry and backoff for the callback, and the reporting mechanism for a missing nightly snapshot (e.g. a
  check in `prod_smoke.yml`).
- How to fetch SPY for the weekly comparison: reuse `fetch_latest_prices` / the provider.
- Rounding and display precision: prices 2 dp, shares 4 dp, percentages 1 dp.
- The 2027 universe roll. Propose it separately before January 2027, re-running the pre-registered test
  for the new period.
