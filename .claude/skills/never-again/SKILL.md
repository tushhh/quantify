---
name: never-again
description: Regression-test workflow for bug fixes in Quantify. Use whenever fixing a bug, such as wrong backtest numbers, a crashing Telegram handler, a malformed API payload, a broken or unauthenticated endpoint, or a test that only passes in CI. Write a test that fails without the fix, prove it with the bundled script, then fix and commit both together, so the bug can't quietly return in a later session.
---

# never-again: every fixed bug gets a test that would have caught it

1. **Write the test first.** Make it the smallest test that shows the bug, in the test module that mirrors the source path (`src/quantify/data/provider_router.py` → `tests/test_data/test_provider_router.py`, `api/routers/x.py` → `tests/test_api/test_x.py`). Start it with `# Regression: <what broke, in one line>`.
2. **Prove it catches the bug:**
   ```bash
   python ${CLAUDE_SKILL_DIR}/prove_regression.py tests/test_data/test_x.py::test_name
   ```
   This runs the test against `--base` (default `HEAD`, the code before your uncommitted fix) and against the working tree. You want **fails on base, passes with the fix**. If it says the base failure was a collection/import error, the test only leans on new code. Rework it so it fails on the bug itself. If the fix is already committed, pass `--base <commit-before-fix>`.
3. **Fix the bug, then run what CI runs:** `ruff check .` and `pytest`.
4. **Commit the test and the fix together.**

## Keep the test hermetic

- **No network.** Monkeypatch `urllib.request.urlopen`, `backtest_router._fetch_data`, the provider, or `yfinance`.
- **No CI-only environment.** Set what the code reads with `monkeypatch.setenv("GITHUB_REPOSITORY", ...)`. Never rely on GitHub Actions providing it.
- **No real database.** Swap in a fake `SessionLocal`, as `tests/test_api/test_internal_auth.py` does.
- **Prices come from fixtures.** Use `sample_ohlcv_data`, `long_ohlcv_data` or `long_multi_stock_data` from `tests/conftest.py`.
- **Telegram handlers** (python-telegram-bot, `async def handler(update, context)`): call the handler with stub `update`/`context` objects whose `reply_text`/`send_message` record their calls, and assert on those. Never contact Telegram.

## Examples in the suite

- `tests/test_backtest/test_manifest.py::test_config_changes_change_run_id`: runs with different capital or sizing shared one `run_id`.
- `tests/test_data/test_provider_router.py::test_fetch_market_data_does_not_refetch_symbols_the_provider_omitted`: failed symbols were downloaded twice under rate limiting.
- `tests/test_api/test_backtest.py::test_backtest_endpoint_instantiates_strategies`: nested metadata rendered as "[object Object]" in the web UI.
- `tests/test_api/test_internal_auth.py`: unauthenticated internal endpoints.
- `tests/test_api/test_predict.py`: a test that only passed where CI set `GITHUB_REPOSITORY`.

For environment setup, see the crosscheck skill.
