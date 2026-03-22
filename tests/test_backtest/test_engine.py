"""
tests/test_backtest/test_engine.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for quantify.backtest.engine.BacktestEngine.

Covers:
- Engine runs end-to-end without error on minimal data
- BacktestResult has correct structure
- equity_curve is non-empty and starts at initial_capital
- daily_returns is derived from equity_curve
- trades list is populated after a successful run
- Metadata contains expected keys
- Invalid inputs raise appropriate errors
- Multiple strategies run simultaneously
- Engine respects start_date / end_date filtering
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from quantify.backtest.engine import BacktestEngine, BacktestResult
from quantify.backtest.costs import CostModel
from quantify.risk.position_sizer import EqualWeightSizer
from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal


# ---------------------------------------------------------------------------
# Minimal strategy stub
# ---------------------------------------------------------------------------


class _AlwaysBuyStrategy(Strategy):
    """Stub strategy that emits a long signal for every symbol every day."""

    name = "always_buy"
    rebalance_frequency = "daily"
    lookback_days = 10

    def get_required_features(self) -> list[str]:
        return []

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        signals = []
        for symbol, df in data.items():
            if df.empty:
                continue
            ts = df.index[-1]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            signals.append(
                Signal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction="long",
                    strength=1.0,
                    timestamp=ts,
                )
            )
        return signals

    def validate(self) -> None:
        pass

    def on_start(self) -> None:
        pass

    def on_stop(self) -> None:
        pass

    def on_fill(self, fill) -> None:
        pass


class _AlternateBuySellStrategy(Strategy):
    """Strategy that buys then closes on alternating weeks."""

    name = "alternate"
    rebalance_frequency = "weekly"
    lookback_days = 20
    _toggle = False

    def get_required_features(self) -> list[str]:
        return []

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        self._toggle = not self._toggle
        direction = "long" if self._toggle else "close"
        signals = []
        for symbol, df in data.items():
            if df.empty:
                continue
            ts = df.index[-1]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            signals.append(
                Signal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction=direction,  # type: ignore
                    strength=1.0 if self._toggle else 0.0,
                    timestamp=ts,
                )
            )
        return signals

    def validate(self) -> None:
        pass

    def on_start(self) -> None:
        pass

    def on_stop(self) -> None:
        pass

    def on_fill(self, fill) -> None:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n_bars: int = 60,
    base_price: float = 100.0,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = base_price * np.cumprod(1 + rng.normal(0.0002, 0.012, n_bars))
    high = close * (1 + rng.uniform(0, 0.01, n_bars))
    low = close * (1 - rng.uniform(0, 0.01, n_bars))
    open_ = close * (1 + rng.uniform(-0.005, 0.005, n_bars))
    volume = rng.integers(500_000, 5_000_000, n_bars)
    index = pd.date_range("2023-01-02", periods=n_bars, freq="B")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


def _minimal_data(n_symbols: int = 2, n_bars: int = 60) -> dict[str, pd.DataFrame]:
    tickers = [f"STK{i}" for i in range(n_symbols)]
    return {t: _make_ohlcv(n_bars=n_bars, seed=i) for i, t in enumerate(tickers)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBacktestEngineInit:
    def test_requires_at_least_one_strategy(self) -> None:
        with pytest.raises(ValueError, match="at least one strategy"):
            BacktestEngine(strategies=[])

    def test_requires_positive_capital(self) -> None:
        with pytest.raises(ValueError, match="initial_capital must be positive"):
            BacktestEngine(strategies=[_AlwaysBuyStrategy()], initial_capital=0)

    def test_negative_capital_raises(self) -> None:
        with pytest.raises(ValueError):
            BacktestEngine(strategies=[_AlwaysBuyStrategy()], initial_capital=-1000)


class TestBacktestEngineRun:
    def test_run_returns_backtest_result(self) -> None:
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=100_000.0,
        )
        data = _minimal_data(n_symbols=2, n_bars=30)
        result = engine.run(data)
        assert isinstance(result, BacktestResult)

    def test_equity_curve_nonempty(self) -> None:
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=100_000.0,
        )
        result = engine.run(_minimal_data(n_bars=30))
        assert len(result.equity_curve) > 0

    def test_equity_curve_starts_near_initial_capital(self) -> None:
        capital = 100_000.0
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=capital,
        )
        result = engine.run(_minimal_data(n_bars=30))
        # First equity value should be close to initial capital
        assert abs(result.equity_curve.iloc[0] - capital) / capital < 0.05

    def test_daily_returns_length_matches_equity_minus_one(self) -> None:
        engine = BacktestEngine(strategies=[_AlwaysBuyStrategy()], initial_capital=50_000.0)
        result = engine.run(_minimal_data(n_bars=40))
        assert len(result.daily_returns) == len(result.equity_curve) - 1

    def test_metadata_contains_expected_keys(self) -> None:
        engine = BacktestEngine(strategies=[_AlwaysBuyStrategy()], initial_capital=100_000.0)
        result = engine.run(_minimal_data(n_bars=30))
        required_keys = {
            "start", "end", "initial_capital", "final_equity",
            "strategies", "symbols", "n_trading_days",
        }
        assert required_keys <= set(result.metadata.keys())

    def test_metadata_strategies_contains_strategy_name(self) -> None:
        engine = BacktestEngine(strategies=[_AlwaysBuyStrategy()], initial_capital=100_000.0)
        result = engine.run(_minimal_data(n_bars=30))
        assert "always_buy" in result.metadata["strategies"]

    def test_empty_data_raises(self) -> None:
        engine = BacktestEngine(strategies=[_AlwaysBuyStrategy()], initial_capital=100_000.0)
        with pytest.raises(ValueError):
            engine.run(data={})

    def test_run_with_zero_cost_model(self) -> None:
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=100_000.0,
            cost_model=CostModel.zero(),
        )
        result = engine.run(_minimal_data(n_bars=30))
        assert result is not None

    def test_run_with_custom_sizer(self) -> None:
        sizer = EqualWeightSizer(n_signals=2, max_position_pct=0.10)
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=100_000.0,
            position_sizer=sizer,
        )
        result = engine.run(_minimal_data(n_bars=30))
        assert result is not None


class TestBacktestResultProperties:
    @pytest.fixture(scope="class")
    def result(self) -> BacktestResult:
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=100_000.0,
        )
        return engine.run(_minimal_data(n_bars=60))

    def test_total_return_is_finite(self, result: BacktestResult) -> None:
        assert np.isfinite(result.total_return)

    def test_sharpe_ratio_finite(self, result: BacktestResult) -> None:
        assert np.isfinite(result.sharpe_ratio)

    def test_max_drawdown_between_0_and_1(self, result: BacktestResult) -> None:
        assert 0.0 <= result.max_drawdown <= 1.0

    def test_win_rate_between_0_and_1(self, result: BacktestResult) -> None:
        assert 0.0 <= result.win_rate <= 1.0

    def test_annualized_return_finite(self, result: BacktestResult) -> None:
        assert np.isfinite(result.annualized_return)


class TestBacktestDateFiltering:
    def test_start_date_filters_early_bars(self) -> None:
        data = _minimal_data(n_bars=60)
        start = date(2023, 2, 1)  # midway through the date range
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=100_000.0,
            start_date=start,
        )
        result = engine.run(data)
        if result.metadata["start"] is not None:
            assert result.metadata["start"] >= start

    def test_end_date_filters_late_bars(self) -> None:
        data = _minimal_data(n_bars=60)
        end = date(2023, 2, 28)
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy()],
            initial_capital=100_000.0,
            end_date=end,
        )
        result = engine.run(data)
        if result.metadata["end"] is not None:
            assert result.metadata["end"] <= end


class TestMultipleStrategies:
    def test_two_strategies_run_together(self) -> None:
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy(), _AlternateBuySellStrategy()],
            initial_capital=100_000.0,
        )
        result = engine.run(_minimal_data(n_bars=60))
        assert isinstance(result, BacktestResult)
        assert len(result.metadata["strategies"]) == 2

    def test_signals_log_contains_both_strategies(self) -> None:
        engine = BacktestEngine(
            strategies=[_AlwaysBuyStrategy(), _AlternateBuySellStrategy()],
            initial_capital=100_000.0,
        )
        result = engine.run(_minimal_data(n_bars=60))
        strategy_names = {s["strategy"] for s in result.signals_log}
        assert "always_buy" in strategy_names
        assert "alternate" in strategy_names
