# Strategy plan via the Quantify Trades bot: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** Each US trading night, run the tested `PLAN_V1` strategy, and through the Quantify Trades bot
tell each user with a plan exactly what to buy and sell for their plan amount. Record what they confirm,
and warn when the plan behaves worse than in testing.

**Architecture:**
- A GitHub Actions job runs the unchanged backtest engine on `PLAN_V1` and POSTs a snapshot to an
  authenticated internal endpoint. The snapshot holds the holdings plus the orders submitted at the last
  close.
- Heroku stores the snapshot, turns its orders into per-plan instructions (fractional shares), and sends
  them through the existing trades bot with Done / Price / Skip buttons.
- No engine code runs on Heroku.

**Tech stack:** Python 3.12, FastAPI, SQLAlchemy (SQLite in tests, Postgres in prod),
python-telegram-bot 22 (`Application`, `CallbackQueryHandler`), APScheduler, GitHub Actions, pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-strategy-plan-telegram-design.md`. Read it first: it defines
`PLAN_V1`, the instruction rules, skip accounting and the warning thresholds.

## Global constraints

- Work on branch `feat/strategy-plan`. Never push to `main`; hand over a PR. The `branch_guard` hook
  blocks pushes to main.
- No new runtime dependencies.
- Nothing on the Heroku web path may import `quantify.backtest`, `quantify.strategy` or pandas-heavy
  modules: Heroku has 512 MB. Only `scripts/run_plan.py` and `quantify.plan.snapshot` import the engine.
- `PLAN_V1` must not change. It uses:
  - the universe in `plan_v1.json`;
  - allocations `trend_following` 0.4615 and `cross_sectional_momentum` 0.5385;
  - start 2022-01-03, data from 2020-01-01;
  - router-builder defaults for costs, sizer and risk;
  - $100,000 notional, benchmark SPY;
  - whole shares in the engine.
- Protected-area permissions (owner-approved on 2026-11-17):
  - `engine.py`: only a read-only accessor (Task 2);
  - Telegram: the plan handlers, plus the alert loop skipping plan rows;
  - schema: tables `plan_snapshots`, `plans`, `plan_instructions`, and columns `trades.plan_id` and
    `trades.plan_strategy`.
- Internal endpoints call `_verify_secret`. The workflow reads `INTERNAL_API_SECRET` and
  `HEROKU_APP_URL` from repo secrets, never from inputs.
- Copy:
  - sentence case;
  - prices 2 dp, shares 4 dp, percentages 1 dp, dollars with commas;
  - errors are specific and say what to do;
  - backtest numbers are always on a separate labelled line, never blended with live numbers.
- No automatic selling. Warnings recommend; the user decides.

## Review focus

1. **Stale or double-tapped Done button.** The second tap must not create a second `Trade`. It answers
   "Already recorded". (Task 7)
2. **Bad price input after ✏️ Price**, e.g. `abc`, `-5`, `0` or `1,234.50`. Commas are accepted; other
   bad input gets a specific error and the bot keeps waiting. A `/cancel` clears the wait. (Task 9)
3. **Bad `/plan` amount**, e.g. `0`, `-100`, `5k`, `abc`, or `/plan withdraw` with more than the plan's
   value. Each gets a specific error and creates no rows. (Task 9)
4. **First snapshot ever, or a snapshot when no plans exist.** It is stored, no messages are sent, and
   the drift check is skipped. A user whose `telegram_chat_id` is now empty is skipped without crashing
   the batch. (Tasks 6, 8)
5. **Plan cash too low for tonight's buys** (after skips or withdrawals). Buys are scaled down
   proportionally, never below zero cash, and buys under $1 are dropped. (Task 6)

---

### Task 1: `PLAN_V1` config package

**Files:**
- Create: `src/quantify/plan/__init__.py` (empty)
- Create: `src/quantify/plan/plan_v1.json`, a byte-for-byte copy of
  `docs/superpowers/specs/plan_v1/plan_v1.json`
- Create: `src/quantify/plan/config.py`
- Test: `tests/test_plan/__init__.py`, `tests/test_plan/test_config.py`

**Interfaces:**
- Produces: `PLAN_V1: PlanConfig`, a frozen dataclass with these fields:
  - `config_id: str` = "PLAN_V1"
  - `universe: tuple[str, ...]` (100 symbols)
  - `allocations: dict[str, float]` = {"trend_following": 0.4615, "cross_sectional_momentum": 0.5385}
  - `start: date` = 2022-01-03
  - `fetch_start: date` = 2020-01-01
  - `notional: float` = 100_000.0
  - `max_drawdown: float` = -0.3095
  - `worst_12m_gap: float` = -0.1945
  - `drops_of_5pct: int` = 23
- This module must import only the stdlib, because Heroku uses it.

- [ ] **Step 1: Write failing tests** `test_plan_v1_matches_the_tested_configuration`. Assert:
  - `len(PLAN_V1.universe) == 100` and `"GOOG" in PLAN_V1.universe and "GOOGL" in PLAN_V1.universe`;
  - `sum(PLAN_V1.allocations.values()) == pytest.approx(1.0, abs=1e-3)`;
  - `PLAN_V1.max_drawdown == -0.3095` and `PLAN_V1.worst_12m_gap == -0.1945`;
  - the JSON file equals the docs copy byte for byte.
- [ ] **Step 2:** Run `.venv/Scripts/python -m pytest tests/test_plan/test_config.py -v`. Expected: FAIL
  (module missing).
- [ ] **Step 3:** Implement `config.py`. It loads `plan_v1.json` with `importlib.resources`. Add
  `"quantify.plan": ["*.json"]` package data to `pyproject.toml` if the package config needs it.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Add the PLAN_V1 config the live plan must follow"`.

### Task 2: Engine read-only accessor for final books and last-bar orders

**Files:**
- Modify: `src/quantify/backtest/engine.py`, at the end of `run()`, before building the result
- Test: `tests/test_backtest/test_engine.py`

**Interfaces:**
- Produces, set by `run()`:
  - `BacktestEngine.final_books: dict[tuple[str, str], float]`, a copy of `self._books`;
  - `BacktestEngine.pending_orders: list[dict]`, one dict per order still open at the end of the run,
    with keys `strategy`, `symbol`, `side` ("buy" | "sell") and `quantity` (float). These are the
    orders submitted on the last bar, read via `broker.get_open_orders()`.
- Both start empty in `__init__`.

- [ ] **Step 1: Write failing tests** in `TestStrategyBooks`.
  - `test_pending_orders_are_the_orders_submitted_on_the_last_bar`: use a `_FixedSignalStrategy`
    subclass that emits `"long"` only when called on the final bar, on
    `_minimal_data(n_symbols=2, n_bars=40)`. Assert:
    - `pending_orders` has exactly 2 orders, both `side == "buy"` and `strategy == "buyer"`;
    - `final_books` has no entry for them, because they fill at the next open, which the run never
      reaches.
  - `test_no_pending_orders_when_positions_are_already_held`: with the daily `"long"` strategy from bar
    one, `pending_orders == []` and `final_books` holds both symbols.
  - `test_final_books_match_open_positions`: every key in `final_books` has a positive quantity.
- [ ] **Step 2:** Run `-k pending_orders or final_books`. Expected: FAIL (`AttributeError`).
- [ ] **Step 3:** Implement. Assign both attributes only; no behaviour change.
- [ ] **Step 4:** Run `tests/test_backtest -q`. Expected: PASS. Then run
  `.venv/Scripts/python .claude/skills/crosscheck/parity.py --base origin/main`. Expected: **identical**
  (exit 0).
- [ ] **Step 5:** Commit: `git commit -m "Expose the engine's final books and last-bar orders"`.

### Task 3: Snapshot builder

**Files:**
- Create: `src/quantify/plan/snapshot.py`
- Test: `tests/test_plan/test_snapshot.py`

**Interfaces:**
- Consumes: `PLAN_V1` (Task 1), and `engine.final_books` / `engine.pending_orders` (Task 2).
- Produces:
  - `class MissingSymbolsError(RuntimeError)`
  - `build_plan_engine(config: PlanConfig, end: date) -> BacktestEngine`. Build it **exactly as
    `docs/superpowers/specs/plan_v1/bar_test.py` does**:
    - Make a `BacktestRequest(start_date=config.start, end_date=end, strategies=…,
      universe=list(config.universe) + ["SPY"])`. In `strategies=`, the two `PLAN_V1` strategies are
      enabled with `config.allocations` and the other four are disabled with allocation 0.
    - Build the strategies with `_build_strategy_instances(req)`. Don't pass `universe=` to the
      strategy constructors: the test didn't, and each strategy keeps its own default list.
    - Build the rest with `_build_cost_model(req)`, `_build_position_sizer(req)` and
      `_build_risk_manager(req)`.
    - Engine settings: `initial_capital=config.notional`, `benchmark_symbol="SPY"`.
    - Task 4's reproduction check is the proof that this matches.
  - `snapshot_from_run(engine, result, data: dict[str, pd.DataFrame], config: PlanConfig) -> dict` with
    these keys:
    - `config_id`
    - `as_of` (ISO date of the last bar)
    - `equity`
    - `holdings` (`{strategy: {symbol: weight}}`, weight = qty × last close / equity, rounded to 6 dp)
    - `orders` (`{strategy: {symbol: {"action": "buy", "weight": w} | {"action": "sell_all"}}}`)
    - `prices` (last close for every universe symbol and SPY, 4 dp)
    - `run_id`
    - `code_sha` (from `GITHUB_SHA`, else `"local"`)
  - `require_complete(data, config) -> None`. It raises `MissingSymbolsError` listing every universe
    symbol or SPY that is missing or empty.

- [ ] **Step 1: Write failing tests** on synthetic data: `_minimal_data`-style frames for a 3-symbol test
  config, plus SPY.
  - `test_snapshot_weights_are_per_strategy_long_only_and_sum_at_most_one`
  - `test_snapshot_orders_come_only_from_pending_orders`: a held position with no order produces no
    entry in `orders`.
  - `test_missing_symbol_raises`: drop one symbol; assert the error message names it.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Pass a test config (a `dataclasses.replace(PLAN_V1, universe=...)`) in the
  tests; production calls use `PLAN_V1`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Build the nightly plan snapshot from the tested engine"`.

### Task 4: Nightly script and workflow

**Files:**
- Create: `scripts/run_plan.py`
- Create: `.github/workflows/plan_cron.yml`
- Test: `tests/test_plan/test_run_plan.py`

**Interfaces:**
- Consumes: Task 3.
- Produces:
  - `scripts/run_plan.py main(argv=None) -> int`. It fetches data with
    `api.routers.backtest._fetch_data(list(universe) + ["SPY"], fetch_start, today)`, then calls
    `require_complete`, runs the engine and builds the snapshot. It POSTs the JSON to
    `$HEROKU_APP_URL/api/internal/plan-snapshot` with header `X-Internal-Secret: $INTERNAL_API_SECRET`.
    It returns 0 only on HTTP 2xx and 1 otherwise. It prints the error.
  - `--dry-run` prints the snapshot and skips the POST.
  - `--reproduce PATH_TO_daily_2022.csv` runs to 2026-11-13 and compares daily returns. It prints the
    max absolute difference and exits 1 if that is above 1e-6.

- [ ] **Step 1: Write failing tests**, monkeypatching `_fetch_data` (synthetic complete or incomplete
  data) and `urllib.request.urlopen`:
  - `test_main_posts_snapshot_with_secret_header`
  - `test_main_returns_1_when_callback_fails`
  - `test_main_returns_1_and_posts_nothing_when_a_symbol_is_missing`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the script, then the workflow. The workflow:
  - is a copy of `backtest.yml`'s checkout / Python 3.12 / pip-cache / install steps;
  - runs on `schedule: cron '30 22 * * 1-5'` and `workflow_dispatch`;
  - has `permissions: contents: read`;
  - passes `HEROKU_APP_URL` and `INTERNAL_API_SECRET` from `secrets`;
  - runs `python scripts/run_plan.py`.
- [ ] **Step 4:** Run the tests. Expected: PASS. Then run the real-data reproduction once, by hand (CA
  bundle per the corporate-proxy memory):
  `.venv/Scripts/python scripts/run_plan.py --reproduce docs/superpowers/specs/plan_v1/daily_2022.csv`.
  Expected: exit 0. Paste the output into the PR description. If it fails, stop and report; don't change
  `PLAN_V1`.
- [ ] **Step 5:** Commit: `git commit -m "Run the plan nightly on GitHub Actions"`.

### Task 5: Schema: plan tables and trade columns

**Files:**
- Modify: `api/models.py` (three new models; two columns on `Trade`)
- Modify: `api/database.py` `ensure_trade_columns()` (two DDL entries)
- Test: `tests/test_api/test_database.py`

**Interfaces:**
- Produces:
  - `PlanSnapshot`, table `plan_snapshots`: `id`, `as_of` (String(10), unique, indexed), `config_id`,
    `equity` (Float), `holdings_json`, `orders_json`, `prices_json`, `drift_json` (nullable), `run_id`,
    `code_sha`, `created_at`.
  - `Plan`, table `plans`:
    - `id`, `user_id` (FK users.id, unique), `config_id`;
    - `amount_in` (Float), `cash` (Float), `status` (String(16): active | stopping | stopped);
    - `started_at`, `start_snapshot_id` (FK);
    - `peak_value` (Float), `last_warning_level` (Integer, default 0, counting −5 % steps);
    - `red_flag_sent_at` (nullable), `created_at`.
  - `PlanInstruction`, table `plan_instructions`:
    - `id`, `plan_id` (FK), `snapshot_id` (FK, nullable for start / top-up / withdraw / stop);
    - `strategy`, `symbol`, `action` (buy | sell), `shares` (Float), `ref_price` (Float);
    - `status` (pending | done | skipped), `fill_price` (nullable), `trade_id` (nullable);
    - `telegram_message_id` (nullable), `created_at`, `done_at`.
  - `Trade.plan_id` (Integer FK plans.id, nullable) and `Trade.plan_strategy` (String(64), nullable).
  - DDL: `ALTER TABLE trades ADD COLUMN plan_id INTEGER` and
    `ALTER TABLE trades ADD COLUMN plan_strategy VARCHAR(64)`.

- [ ] **Step 1: Write failing tests:**
  - `test_create_all_creates_plan_tables`: on a fresh `sqlite://` engine, `Base.metadata.create_all`,
    then the inspector lists all three tables.
  - `test_ensure_trade_columns_adds_plan_columns`: use an old-style `trades` table without them.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/test_api -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Add plan tables and plan columns on trades"`.

### Task 6: Plan service: snapshots, instructions, value

**Files:**
- Create: `api/plan_service.py` (stdlib, SQLAlchemy and `quantify.plan.config` only)
- Test: `tests/test_api/test_plan_service.py`, with an in-memory SQLite session fixture:
  `create_engine("sqlite://")`, `Base.metadata.create_all`, `sessionmaker`.

**Interfaces:**
- Consumes: Task 5 models, `PLAN_V1`.
- Produces:
  - `store_snapshot(db, payload: dict) -> tuple[PlanSnapshot, bool]`. Idempotent on `as_of`: it returns
    the existing row with `created=False`. On create, it fills `drift_json` by comparing
    `previous.holdings + previous.orders` with `payload.holdings`. Drift is a list of
    `{strategy, symbol, expected, got}` with weight differences above 0.002. It stays `None` when there
    is no previous snapshot.
  - `plan_holdings(db, plan) -> dict[tuple[str, str], Trade]`: active `Trade` rows with this `plan_id`,
    keyed by (`plan_strategy`, `symbol`).
  - `plan_value(db, plan, prices: dict[str, float]) -> float`: cash plus the market value of the
    holdings.
  - `instructions_from_snapshot(db, plan, snapshot) -> list[PlanInstruction]`. It applies the spec's
    rules:
    - buys: dollars = weight × plan value, shares rounded down to 4 dp, dropped if under $1, and scaled
      down proportionally when the sum exceeds cash;
    - sells: `sell_all` → the plan shares for that strategy-symbol, skipped if none are held.
    It inserts the instructions as `pending` and returns them.

- [ ] **Step 1: Write failing tests:**
  - `test_store_snapshot_is_idempotent_on_as_of`
  - `test_first_snapshot_has_no_drift`
  - `test_drift_is_recorded_not_acted_on`
  - `test_buy_is_weight_times_plan_value_in_fractional_shares`: weight 0.05, value $5,000, price
    $188.07 → shares `1.3293`, ref_price 188.07.
  - `test_buys_under_one_dollar_are_dropped`
  - `test_buys_scale_down_when_cash_is_short`: total buys $900, cash $600 → each scaled by 2/3, and the
    sum is at most $600.
  - `test_sell_all_sells_only_that_strategys_plan_shares`: the same symbol is held by both strategies
    and by a manual row; only the named strategy's plan row is sold.
  - `test_held_position_without_order_creates_no_instruction`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Turn plan snapshots into sized instructions"`.

### Task 7: Plan service: user actions and confirmations

**Files:**
- Modify: `api/plan_service.py`
- Modify: `api/trade_service.py`. Add `create_plan_trade(db, user_id, plan_id, strategy, symbol, shares,
  price) -> Trade`. It always inserts a new row, or adds to the same plan / strategy / symbol row, and
  never touches manual rows. Change `create_or_aggregate_trade` to aggregate only into rows where
  `plan_id IS NULL`.
- Test: `tests/test_api/test_plan_service.py`, `tests/test_api/test_trades.py`

**Interfaces:**
- Produces:
  - `start_or_top_up(db, user_id, amount: float, snapshot) -> tuple[Plan, list[PlanInstruction]]`. A new
    plan or a top-up adds `amount` to `amount_in` and `cash`. It then buys the current `holdings` in
    proportion: dollars = weight × amount, with the same rounding and $1 rules as Task 6. It raises
    `ValueError("Plan amount must be at least $10")` for amounts under 10.
  - `withdraw(db, plan, amount, prices) -> list[PlanInstruction]`. It sells proportional fractions of
    each holding and lowers `amount_in`. It raises `ValueError` when `amount` is above the plan value.
  - `stop(db, plan, prices) -> list[PlanInstruction]`. It creates sell-all instructions for every plan
    holding and sets status `stopping`. The status becomes `stopped` when none are left pending.
  - `mark_done(db, instruction_id, fill_price: float | None = None) -> tuple[PlanInstruction, bool]`.
    The bool is True if this call recorded the trade. For a buy it calls `create_plan_trade` and
    `cash -= shares × price`; for a sell, `reduce_trade_shares` / `close_trade_full` and
    `cash += shares × price`. If the instruction is already done or skipped, it returns `False` and
    changes nothing.
  - `mark_skipped(db, instruction_id) -> tuple[PlanInstruction, bool]`. For a buy, nothing moves. For a
    sell, `cash += shares × ref_price` and the plan row's `plan_id` and `plan_strategy` are cleared. The
    row stays active as the user's own position.

- [ ] **Step 1: Write failing tests:**
  - `test_start_buys_current_holdings_in_proportion`
  - `test_top_up_adds_cash_and_buys_in_proportion`
  - `test_amount_below_ten_dollars_is_rejected`
  - `test_withdraw_more_than_value_is_rejected`
  - `test_stop_lists_sell_all_for_every_holding`
  - `test_done_buy_creates_tagged_trade_and_debits_cash`
  - `test_done_twice_records_once` (Review focus 1)
  - `test_done_with_fill_price_uses_it`
  - `test_skipped_sell_credits_cash_and_untags_row`
  - in `test_trades.py`: `test_manual_buy_never_merges_into_plan_row`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/test_api -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Plan actions: start, top up, withdraw, stop, done, skip"`.

### Task 8: Snapshot endpoint, nightly messages and warnings

**Files:**
- Modify: `api/routers/internal.py`. Add `POST /plan-snapshot`.
- Create: `api/plan_bot.py`, holding the message formatting and sending. Only this file and
  `telegram_bot.py` import `telegram`.
- Create: `api/plan_warnings.py`, which is pure.
- Test: `tests/test_api/test_plan_snapshot_endpoint.py`, `tests/test_api/test_plan_warnings.py`

**Interfaces:**
- Consumes: Tasks 6 and 7.
- Produces:
  - Endpoint `plan_snapshot(body: dict, background_tasks, x_internal_secret: Optional[str] = Header(None))`.
    It calls `_verify_secret`, then `store_snapshot`. On a new row it schedules
    `plan_bot.notify_snapshot(snapshot_id)` and returns `{"status": "stored"}`; on a duplicate it returns
    `{"status": "duplicate"}`.
  - `plan_warnings.check(plan_peak, value, plan_12m_return: float | None, spy_12m_return: float | None,
    last_level: int, red_flag_sent: bool) -> tuple[str | None, int]`. It returns
    `("heads_up" | "red_flag" | None, new_level)`.
    - Heads-up fires once per new −5 % step from the peak.
    - Red flag fires once when drawdown < `PLAN_V1.max_drawdown`, or when the 12-month return minus
      SPY's is below `PLAN_V1.worst_12m_gap`.
    - The 12-month check only applies when both returns are present, i.e. the plan is at least 12
      months old.
  - `plan_bot.notify_snapshot(snapshot_id) -> None`. For each active plan whose user has a
    `telegram_chat_id`:
    1. build instructions (Task 6);
    2. send one message listing them, each with an inline keyboard
       `plan:done:<id>` / `plan:price:<id>` / `plan:skip:<id>`;
    3. update `peak_value`;
    4. send any warning.
    A send failure for one user is logged and does not stop the others. If there are no instructions
    and no warning, it sends nothing.
  - `plan_bot.format_instruction(instr) -> str`, e.g. `"BUY NVDA ~$382.00 (2.0312 sh @ $188.07)"` and
    `"SELL XOM all 3.4410 sh (~$402.00)"`.

- [ ] **Step 1: Write failing tests:**
  - endpoint: `test_plan_snapshot_requires_secret` (403), `test_plan_snapshot_duplicate_is_ignored`, and
    `test_snapshot_with_no_plans_sends_nothing` (Review focus 4: patch the sender, assert no calls);
  - warnings:
    - `test_heads_up_fires_once_per_five_percent_step` (−5.2 → fires, level 1; −6 → None;
      −10.1 → fires, level 2)
    - `test_red_flag_on_drawdown_beyond_tested_worst`: −31.0 % → red_flag
    - `test_red_flag_on_twelve_month_gap`: plan +2 %, SPY +22 % → red_flag
    - `test_no_twelve_month_check_for_young_plans`
  - `test_format_instruction_precision`
  - `test_user_without_chat_id_is_skipped_and_others_still_notified`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Send through the trades bot token (`TELEGRAM_BOT_TOKEN`) with
  `telegram.Bot(...).send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(...))`. Warning
  copy:
  - heads-up: "Your plan is down 5.0% from its peak. In testing it fell 5% or more 23 times (worst
    −31.0%). No action needed. To exit, send /plan stop."
  - red flag: "Your plan is doing worse than anything seen in testing (…). The strategy may have
    stopped working. I recommend stopping: send /plan stop."
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Store plan snapshots and send nightly plan instructions"`.

### Task 9: `/plan` commands and buttons in the trades bot

**Files:**
- Modify: `api/plan_bot.py` (handlers)
- Modify: `api/telegram_bot.py`. Register handlers in `start_telegram_bot`:
  - `CommandHandler("plan", plan_cmd)`;
  - `CallbackQueryHandler(plan_button, pattern=r"^plan:")`;
  - a `MessageHandler(filters.TEXT & ~filters.COMMAND, plan_price_reply)` in group 1, so the
    `/buy` / `/sell` conversations keep priority.
- Test: `tests/test_api/test_plan_bot.py`, with stub `update` / `context` objects whose `reply_text`
  and `edit_message_text` record calls.

**Interfaces:**
- Consumes: Tasks 6-8.
- Produces:
  - `plan_cmd(update, context)`. Arguments:
    - none → status;
    - `<amount>` → start or top up. A start asks to confirm first, with the backtest line
      "Backtest 2017-2026: +5.3%/yr vs SPY after costs, passed 6 of 8 profit-bar rows, worst drop
      −31.0%", and buttons `plan:confirm:<amount>` / `plan:cancel`;
    - `withdraw <amount>`;
    - `stop`.
    Amount parsing accepts `5000`, `5,000` and `5000.50`, and rejects `0`, negatives, `5k` and `abc` with
    "Send an amount in US dollars, e.g. /plan 5000".
  - `plan_button(update, context)` handles `plan:confirm|cancel|done|price|skip`.
    - Done edits the message line to "✅ recorded", or answers "Already recorded".
    - Price sets `context.user_data["plan_price_for"] = id` and asks "Send the price you got for SYMBOL".
  - `plan_price_reply(update, context)` runs only while `plan_price_for` is set. It accepts `1,234.50`
    and rejects `abc`, `0` and `-5` with "Send the fill price as a number, e.g. 188.07", keeping the
    wait. On success it calls `mark_done(id, price)` and clears the wait. `/cancel` also clears it.
  - `/plan` status text:
    - "Plan: $5,000 in · value $5,214 (+4.3%) · SPY +2.9% since 3 Nov"
    - "Open instructions: 2"

- [ ] **Step 1: Write failing tests:**
  - `test_plan_without_linked_account_asks_to_link`
  - `test_plan_amount_parsing` (Review focus 3, parametrised over the inputs above)
  - `test_start_requires_confirmation_then_sends_buys`
  - `test_withdraw_more_than_value_shows_specific_error`
  - `test_price_reply_rejects_bad_input_and_keeps_waiting` (Review focus 2)
  - `test_price_reply_accepts_commas`
  - `test_cancel_clears_price_wait`
  - `test_done_button_twice_answers_already_recorded`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/test_api -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Add /plan and its buttons to the Quantify Trades bot"`.

### Task 10: Keep the existing bot from contradicting the plan

**Files:**
- Modify: `api/telegram_bot.py`:
  - `check_alerts_loop`: filter `Trade.plan_id.is_(None)`;
  - `sell_got_ticker` / `sell_got_qty`: manual `/sell` looks up only `plan_id IS NULL` rows;
  - `portfolio_cmd`: list plan rows under a "Plan" heading.
- Modify: `api/trade_service.py` `get_portfolio_summary` only if the heading needs a split; keep its
  output keys.
- Test: `tests/test_api/test_trades.py` or a new `tests/test_api/test_telegram_plan_isolation.py`

- [ ] **Step 1: Write failing tests:**
  - `test_alert_loop_skips_plan_trades`: one manual row past `sell_date` and one plan row past
    `sell_date`; patch `Bot.send_message`, `evaluate_hold_health` and `fetch_latest_prices`. Assert
    exactly one alert, for the manual row. Start the test with `# Regression: hold-period alerts must
    not tell users to sell plan positions`.
  - `test_manual_sell_ignores_plan_rows`
  - `test_portfolio_lists_plan_rows_under_plan_heading`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/test_api -q`. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Keep hold alerts and manual sells away from plan positions"`.

### Task 11: Weekly summary

**Files:**
- Modify: `api/plan_bot.py`. Add `send_weekly_summaries() -> None`.
- Modify: `api/main.py`. Add a scheduler job:
  `scheduler.add_job(send_weekly_summaries, 'cron', day_of_week='sat', hour=1, minute=0, timezone='UTC')`.
- Test: `tests/test_api/test_plan_bot.py`

**Interfaces:**
- Produces: `weekly_summary_text(db, plan, latest_snapshot, start_snapshot) -> str`. It shows:
  - the plan value and return since start vs SPY since start, with SPY taken from `prices_json["SPY"]`
    in the two snapshots;
  - the best and worst holding;
  - pending and skipped counts;
  - any drift count, for the owner only (`user.username` equal to env `PLAN_OWNER_USERNAME`; skipped
    when unset);
  - the backtest line on its own row.

- [ ] **Step 1: Write failing tests:**
  - `test_weekly_summary_compares_with_spy_since_start`
  - `test_weekly_summary_keeps_backtest_line_separate`: assert the backtest numbers appear only on the
    line starting "Backtest".
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Send a weekly plan summary against SPY"`.

### Task 12: Track record script

**Files:**
- Create: `scripts/plan_track_record.py`
- Test: `tests/test_plan/test_track_record.py`

**Interfaces:**
- Produces: `score(snapshots: list[dict]) -> dict`, with keys `days`, `strategy_return`, `spy_return`,
  `excess` and `max_drawdown`. It computes these from each snapshot's `equity` and `prices["SPY"]`.
  `main()` reads snapshots from the DB (`DATABASE_URL`) and prints the live table. The backtest table is
  printed separately, from `PLAN_V1`.

- [ ] **Step 1: Write a failing test**,
  `test_score_from_three_snapshots` (equity 100000 → 101000 → 99000, SPY 500 → 505 → 510).
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `git commit -m "Score the plan's live record against SPY"`.

### Task 13: Bring the README up to date

The README still describes June 2026. It needs these changes:
- six "production-ready" strategies → only trend and momentum are on by default;
- momentum "long/short" → long-only by default;
- ML-ensemble picks and sell signals → the picks have come from the trend screen since Oct 2026;
- no mention of the plan → add it.

Facts must match the code and the test artifacts. Read each claim against the code before writing it.

**Files:**
- Modify: `README.md`
- Modify: `api/routers/strategies.py`, the `trend_following` description, only if Step 1 confirms it is
  wrong too. The README and the catalog both say "EMA crossover (fast/slow) filtered by ADX…, ATR-based
  trailing stops", while `TrendFollowingStrategy` enters on a positive 12-1 month return plus a bullish
  SMA crossover.

**Decisions:**
- Replace "What's New (June 2026)" with "What's new (November 2026)". Keep it to 4-5 bullets:
  - each strategy now trades its own book: the shared-position bug made the default backtest lose 26%;
  - long-only by default, with an "Allow shorts" toggle;
  - fractional shares, idle capital invested, and dropped tickers retried;
  - `/predict` picks come from the trend screen (link `src/quantify/trend_screen.py` for its record);
  - the strategy plan in the Quantify Trades bot (`/plan`).
  The June items move under an "Earlier" sub-heading, unchanged.
- Intro and Highlights:
  - "six production-ready strategies" → "six strategies, two of them on by default after testing";
  - the Telegram row: "trade alerts, the strategy plan and stock picks".
- Strategies table:
  - add a "Default" column: on / off, with a one-phrase reason for off ("lost money in testing" for ML
    and pairs; "uses today's fundamentals, so its backtest is optimistic" for quality value; "only
    scales other strategies" for volatility regime);
  - default allocations as on the branch at the time;
  - correct descriptions; momentum says "long top decile (short side opt-in)".
- New section "Tested strategy and the profit bar", placed after Strategies. A short table copied from
  `plan_v1.json` and the spec's "What was tested":
  - 2017-2026, +20.2%/yr vs SPY 14.9%, 6 of 8 bar rows, failed IR 0.41 and months 52%, worst drop
    −31.0%;
  - one sentence on survivorship (today's index members);
  - one sentence that safety overlays were tested and rejected;
  - a link to the spec.
- Telegram section:
  - add the `/plan` commands table (`/plan <amount>`, `/plan`, `/plan withdraw <amount>`,
    `/plan stop`, and the Done / Price / Skip buttons);
  - add the nightly timing (after the US close; place orders at the next open);
  - add the warnings (−5% heads-up steps, red flag);
  - Automatic alerts: the "Sell signal" row now says it uses the hold-health check, and none of the
    alerts apply to plan positions;
  - "Quantify Predictions" description: picks come from the trend screen, while `/predict <SYMBOL>` for
    a single stock still uses the ML model (as CLAUDE.md states).
- Safety and execution boundaries: add "**Strategy plan (`/plan`)**: tells you what to trade; you place
  orders yourself. Nothing is traded automatically."
- Environment setup: add the `HEROKU_APP_URL` and `INTERNAL_API_SECRET` repo secrets used by
  `plan_cron.yml`, and `PLAN_OWNER_USERNAME` (optional).
- Sentence case for new headings, per CLAUDE.md. Leave the existing headings alone.

- [ ] **Step 1:** Verify the trend-following description against `src/quantify/strategy/trend_following.py`
  and its `sma_crossover` feature in `src/quantify/data/features.py`. Note the SMA periods.
- [ ] **Step 2:** Edit `README.md` per the decisions. Fix the `strategies.py` description if Step 1
  showed it is wrong.
- [ ] **Step 3:** Check that every number in the new sections appears in `plan_v1.json`, the spec or
  `trend_screen.py`: `grep -n "20.2\|14.9\|0.41\|52%\|31.0" README.md` and cross-check. Run
  `pytest tests/test_api -q` (the catalog has tests). Expected: PASS.
- [ ] **Step 4:** Commit: `git commit -m "Bring the README up to date with the tested strategy and /plan"`.

### Task 14: Verify and hand over

- [ ] **Step 1:** Run `.venv/Scripts/python -m ruff check .` and `.venv/Scripts/python -m pytest -q`.
  Expected: clean and all passing.
- [ ] **Step 2:** Run crosscheck against `origin/main`. Expected: identical (only the accessor changed in
  `engine.py`).
- [ ] **Step 3:** Run the `deep-security-check` skill (new internal route, new workflow) and the
  `16-eyes` skill on the branch. Fix every finding that is in scope.
- [ ] **Step 4:** Do a manual end-to-end with `--dry-run`. Then POST that snapshot to a local server
  (`uvicorn api.main:app`) with a test secret and a test user. No Telegram token is needed: assert the
  instructions in the DB.
- [ ] **Step 5:** Push `feat/strategy-plan`. Give the owner the compare link
  `https://github.com/tushhh/quantify/compare/main...feat/strategy-plan`. Include the reproduction output
  and these post-merge steps:
  - set the `HEROKU_APP_URL` repo secret (`INTERNAL_API_SECRET` already exists);
  - trigger `plan_cron.yml` once by hand;
  - run `prod-smoke`.
