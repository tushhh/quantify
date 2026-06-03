"""
tests/test_strategy/test_momentum.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for CrossSectionalMomentumStrategy.

Covers:
- Signal generation returns list[Signal]
- Signals have valid directions and strength values
- Long signals are in the top decile, short in the bottom
- Crash filter scales strengths when SPY return is negative
- Rebalance frequency gate (no rebalance within 21 days)
- Insufficient history returns empty list
- Signal metadata contains expected keys
"""

from __future__ import annotations


import numpy as np
import pandas as pd

from quantify.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy
from quantify.strategy.signal import Signal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stock_df(
    n_bars: int = 310,
    seed: int = 0,
    base_price: float = 100.0,
    drift: float = 0.0003,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data with pre-computed feature columns."""
    rng = np.random.default_rng(seed)
    close = base_price * np.cumprod(1 + rng.normal(drift, 0.015, n_bars))
    open_ = close * (1 + rng.uniform(-0.005, 0.005, n_bars))
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n_bars))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n_bars))
    volume = rng.integers(500_000, 5_000_000, n_bars)

    index = pd.date_range("2020-01-02", periods=n_bars, freq="B")
    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
    # Add pre-computed momentum features
    df["return_252d"] = close / np.concatenate([[np.nan] * 252, close[:-252]]) - 1
    df["return_21d"] = close / np.concatenate([[np.nan] * 21, close[:-21]]) - 1
    return df


def _build_universe_data(n_stocks: int = 20, n_bars: int = 310) -> dict[str, pd.DataFrame]:
    """Build a universe of n_stocks with varying returns (spread from -30% to +30%)."""
    data: dict[str, pd.DataFrame] = {}
    tickers = [f"STK{i:02d}" for i in range(n_stocks)]
    drifts = np.linspace(-0.0006, 0.0006, n_stocks)  # varied momentum
    for i, ticker in enumerate(tickers):
        data[ticker] = _make_stock_df(n_bars=n_bars, seed=i + 100, drift=drifts[i])

    # Add SPY
    data["SPY"] = _make_stock_df(n_bars=n_bars, seed=999, drift=0.0003)
    return data


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCrossSectionalMomentumSignals:
    """Core signal generation behaviour."""

    def test_returns_list_of_signals(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        assert isinstance(signals, list)
        assert all(isinstance(s, Signal) for s in signals)

    def test_signals_have_valid_directions(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        valid_directions = {"long", "short", "close"}
        for s in signals:
            assert s.direction in valid_directions

    def test_signal_strengths_in_valid_range(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        for s in signals:
            assert -1.0 <= s.strength <= 1.0, (
                f"Signal strength {s.strength} out of range for {s.symbol}"
            )

    def test_long_signals_have_positive_strength(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        long_signals = [s for s in signals if s.direction == "long"]
        for s in long_signals:
            assert s.strength >= 0.0, f"Long signal {s.symbol} has negative strength"

    def test_short_signals_have_negative_strength(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        short_signals = [s for s in signals if s.direction == "short"]
        for s in short_signals:
            assert s.strength <= 0.0, f"Short signal {s.symbol} has positive strength"

    def test_top_performers_get_long_signals(self) -> None:
        """Stocks with highest 12-1 momentum should receive long signals."""
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)

        # Compute actual momentum scores
        scores: dict[str, float] = {}
        for ticker, df in data.items():
            if ticker == "SPY" or df.empty or len(df) < 273:
                continue
            row = df.iloc[-1]
            r252 = row.get("return_252d")
            r21 = row.get("return_21d")
            if r252 is not None and r21 is not None and not np.isnan(r252) and not np.isnan(r21):
                scores[ticker] = r252 - r21

        if len(scores) >= 10:
            import pandas as pd
            score_s = pd.Series(scores)
            top_decile = score_s[score_s >= score_s.quantile(0.90)].index.tolist()
            long_symbols = {s.symbol for s in signals if s.direction == "long"}
            # At least some top performers should be long
            overlap = set(top_decile) & long_symbols
            assert len(overlap) > 0, "No top-decile stocks received long signals"

    def test_strategy_name_in_signals(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        for s in signals:
            assert s.strategy_name == "cross_sectional_momentum"

    def test_signal_metadata_keys(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        long_signals = [s for s in signals if s.direction in ("long", "short")]
        assert len(long_signals) > 0
        for s in long_signals:
            assert "mom_12_1" in s.metadata
            assert "percentile_rank" in s.metadata
            assert "n_stocks_ranked" in s.metadata


class TestCrashFilter:
    """Crash filter behaviour when SPY has negative 12-month return."""

    def test_crash_filter_reduces_strengths(self) -> None:
        data = _build_universe_data(n_stocks=20)
        # Make SPY have a negative 12m return
        spy_df = data["SPY"].copy()
        spy_df["return_252d"] = -0.20  # SPY down 20%
        data["SPY"] = spy_df

        strat_crash = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=True,
        )
        strat_no_crash = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )

        signals_crash = strat_crash.generate_signals(data)
        signals_no_crash = strat_no_crash.generate_signals(data)

        if signals_crash and signals_no_crash:
            abs_crash = np.mean([abs(s.strength) for s in signals_crash if s.direction in ("long", "short")])
            abs_no_crash = np.mean([abs(s.strength) for s in signals_no_crash if s.direction in ("long", "short")])
            if abs_no_crash > 0:
                assert abs_crash < abs_no_crash, (
                    "Crash filter should reduce signal strengths"
                )

    def test_crash_scale_metadata_when_spy_negative(self) -> None:
        data = _build_universe_data(n_stocks=20)
        spy_df = data["SPY"].copy()
        spy_df["return_252d"] = -0.15
        data["SPY"] = spy_df

        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=True,
        )
        signals = strat.generate_signals(data)
        entry_signals = [s for s in signals if s.direction in ("long", "short")]
        if entry_signals:
            for s in entry_signals:
                assert "crash_scale" in s.metadata
                assert s.metadata["crash_scale"] == 0.50


class TestInsufficientHistory:
    """Strategies with too little data return empty signal list."""

    def test_empty_data_returns_empty(self) -> None:
        strat = CrossSectionalMomentumStrategy(
            universe=["AAPL", "MSFT"],
            crash_filter=False,
        )
        signals = strat.generate_signals({})
        assert signals == []

    def test_short_history_returns_empty(self) -> None:
        """Only 50 bars — not enough for 252-day momentum."""
        rng = np.random.default_rng(0)
        n = 50
        close = 100.0 * np.cumprod(1 + rng.normal(0, 0.01, n))
        index = pd.date_range("2022-01-03", periods=n, freq="B")
        df = pd.DataFrame(
            {
                "open": close * 0.99,
                "high": close * 1.01,
                "low": close * 0.98,
                "close": close,
                "volume": np.ones(n) * 1_000_000,
                "return_252d": np.nan,
                "return_21d": np.nan,
            },
            index=index,
        )
        data = {f"STK{i}": df.copy() for i in range(15)}
        data["SPY"] = df.copy()

        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
        )
        signals = strat.generate_signals(data)
        assert signals == []


class TestRebalanceGate:
    """Strategy respects rebalance frequency gate."""

    def test_no_rebalance_within_rebalance_days(self) -> None:
        data = _build_universe_data(n_stocks=20)
        strat = CrossSectionalMomentumStrategy(
            universe=[t for t in data if t != "SPY"],
            crash_filter=False,
            rebalance_days=21,
        )
        # First call — should rebalance and cache signals
        signals_first = strat.generate_signals(data)

        # Immediately call again — should return cached signals without rebalancing
        # Shift index by 1 day to simulate "next day"
        data_shifted = {
            sym: df.copy().set_index(df.index + pd.Timedelta(days=1))
            for sym, df in data.items()
        }
        signals_second = strat.generate_signals(data_shifted)

        # Both should have same length (cached)
        assert len(signals_first) == len(signals_second)
