---
name: crosscheck
description: Backtest parity check for Quantify. Runs one fixed, offline backtest on a base revision and on the working tree (or another revision) and diffs equity, return, Sharpe, drawdown, signals and trades per strategy. Use before committing any change under src/quantify/backtest, strategy, risk or execution, when refactoring trading logic, when reviewing a PR that touches it, or when the user asks whether a change moves backtest results.
argument-hint: "[--base REF] [--head REF] [--strategies a,b|all]"
---

# crosscheck: backtest parity

A refactor should leave backtest results bit-for-bit identical. An intended logic change should move them only the way you expect. This runs the same deterministic backtest (seeded synthetic prices for 20 symbols, SPY and a `^VIX` series, no network) on two code versions and diffs the outcome.

## Run it

From the repo root, with the project environment (see below):

```bash
python ${CLAUDE_SKILL_DIR}/parity.py --base origin/main
```

- `--base REF`: the version to compare against (default `origin/main`).
- `--head REF`: the version to test. Default is the working tree, uncommitted changes included. To check a PR branch without checking it out: `--base origin/main --head origin/<branch>`.
- `--strategies`: comma-separated, or `all`. The default is `trend_following,cross_sectional_momentum,pairs_mean_reversion,volatility_regime`. `quality_value` (fetches live yfinance fundamentals, so it isn't reproducible) and `ml_return_predictor` (walk-forward training, several minutes) only run when named or with `all`.
- Exit code: 0 identical, 1 results differ, 2 a run failed. A default run takes about a minute.

## Read the result

- **Identical after a refactor**: done. Say so, with the trade count.
- **Different after a refactor**: treat it as a bug until it's explained. Narrow it down with one strategy at a time (`--strategies trend_following`), then bisect the files you changed.
- **Different after an intended change**: show the user the before/after table and explain why each metric moved. Never edit `parity.py` to make a difference go away.
- **Run failed**: the error tail is printed. If the base side fails, the base usually predates an API the runner uses (for example, before the engine existed).

Identical results can also mean a parameter has no effect in this setup. For example, trend-following's `vol_target` doesn't change trades under the default equal-weight sizer. If a change was supposed to matter and didn't, say so.

## Environment

The scripts need the project's dependencies. If there is no `.venv`:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt pytest
```

Then run with `.venv/Scripts/python` (Windows) or `.venv/bin/python`.

## Limits

- Synthetic data catches logic drift, not data-pipeline changes (providers, fundamentals, earnings, caching). For those, run one real backtest before and after and compare `run_id` and `skipped_symbols`.
- Production backtests don't include `^VIX` in their data, so `volatility_regime` fetches the latest live VIX and applies it to every historical date. The parity data includes `^VIX`, so these runs stay offline and repeatable. Don't take that as proof that live backtests are.
