"""
tests/test_risk/test_position_sizer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for quantify.risk.position_sizer — all four sizer implementations.

Covers:
- EqualWeightSizer: correct share count, direction sign, cap enforcement
- VolatilityTargetSizer: share count scales with vol, zero vol → 0 shares
- RiskParitySizer: inverse-vol weighting, lower vol → more shares
- HalfKellySizer: negative edge → 0 shares, fraction math
- get_sizer() factory: all four names resolve correctly
- max_position_pct cap is respected for all sizers
- close direction → 0 shares for all sizers
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from quantify.risk.position_sizer import (
    EqualWeightSizer,
    HalfKellySizer,
    MarketData,
    RiskParitySizer,
    VolatilityTargetSizer,
    get_sizer,
)
from quantify.strategy.signal import Signal
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


class _Portfolio:
    """Minimal portfolio stub satisfying PortfolioProtocol."""

    def __init__(self, nav: float = 100_000.0, cash: float = 100_000.0) -> None:
        self._nav = nav
        self._cash = cash

    @property
    def nav(self) -> float:
        return self._nav

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> dict:
        return {}


def _signal(
    symbol: str = "AAPL",
    direction: str = "long",
    strength: float = 1.0,
    strategy: str = "test",
) -> Signal:
    return Signal(
        strategy_name=strategy,
        symbol=symbol,
        direction=direction,  # type: ignore[arg-type]
        strength=strength,
        timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )


def _market_data(
    symbols: list[str],
    current_prices: dict[str, float] | None = None,
    n_bars: int = 60,
) -> MarketData:
    """Create MarketData with synthetic price series."""
    rng = np.random.default_rng(42)
    prices: dict[str, pd.Series] = {}
    for sym in symbols:
        base = (current_prices or {}).get(sym, 100.0)
        close = base * np.cumprod(1 + rng.normal(0.0002, 0.012, n_bars))
        idx = pd.date_range("2023-01-01", periods=n_bars, freq="B")
        prices[sym] = pd.Series(close, index=idx)

    return MarketData(
        prices=prices,
        current_prices=current_prices or {sym: prices[sym].iloc[-1] for sym in symbols},
    )


# ---------------------------------------------------------------------------
# EqualWeightSizer tests
# ---------------------------------------------------------------------------


class TestEqualWeightSizer:
    def test_basic_long_size(self) -> None:
        sizer = EqualWeightSizer(n_signals=1, max_position_pct=0.10)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(["AAPL"], {"AAPL": 100.0})
        sig = _signal("AAPL", "long")

        shares = sizer.calculate_size(sig, portfolio, mkt)
        # With 1 signal, 10% max: 10_000 / 100 = 100 shares
        assert shares == 100.0

    def test_long_positive_short_negative(self) -> None:
        sizer = EqualWeightSizer(n_signals=1, max_position_pct=0.10)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(["AAPL"], {"AAPL": 100.0})

        long_shares = sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt)
        short_shares = sizer.calculate_size(_signal("AAPL", "short"), portfolio, mkt)

        assert long_shares > 0
        assert short_shares < 0

    def test_close_signal_returns_zero(self) -> None:
        sizer = EqualWeightSizer(n_signals=1, max_position_pct=0.10)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(["AAPL"], {"AAPL": 100.0})
        assert sizer.calculate_size(_signal("AAPL", "close", 0.0), portfolio, mkt) == 0.0

    def test_cap_respected(self) -> None:
        """With 1 signal the cap should limit to max_position_pct."""
        max_pct = 0.05
        sizer = EqualWeightSizer(n_signals=1, max_position_pct=max_pct)
        portfolio = _Portfolio(nav=100_000.0)
        price = 50.0
        mkt = _market_data(["AAPL"], {"AAPL": price})

        shares = sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt)
        assert abs(shares) * price <= portfolio.nav * max_pct + price  # floor rounding

    def test_n_signals_divides_capital(self) -> None:
        """With 10 signals, each gets 1/10 of NAV (capped at 10%)."""
        sizer = EqualWeightSizer(n_signals=10, max_position_pct=0.10)
        portfolio = _Portfolio(nav=100_000.0)
        price = 100.0
        mkt = _market_data(["AAPL"], {"AAPL": price})

        shares = sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt)
        expected_target = portfolio.nav / 10 / price
        assert shares == math.floor(min(expected_target, portfolio.nav * 0.10 / price))

    def test_no_price_returns_zero(self) -> None:
        sizer = EqualWeightSizer()
        portfolio = _Portfolio()
        mkt = MarketData(prices={}, current_prices={})
        shares = sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt)
        assert shares == 0.0

    def test_invalid_n_signals_raises(self) -> None:
        with pytest.raises(ValueError):
            EqualWeightSizer(n_signals=0)


# ---------------------------------------------------------------------------
# VolatilityTargetSizer tests
# ---------------------------------------------------------------------------


class TestVolatilityTargetSizer:
    def test_returns_nonzero_for_volatile_stock(self) -> None:
        sizer = VolatilityTargetSizer(target_annual_vol=0.10, vol_window=20)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(["AAPL"], {"AAPL": 100.0}, n_bars=60)
        sig = _signal("AAPL", "long")
        shares = sizer.calculate_size(sig, portfolio, mkt)
        assert shares != 0.0

    def test_higher_vol_fewer_shares(self) -> None:
        """Higher volatility stock gets fewer shares for same risk budget."""
        portfolio = _Portfolio(nav=100_000.0)

        # Low vol data
        rng = np.random.default_rng(1)
        n = 60
        close_low = 100.0 * np.cumprod(1 + rng.normal(0, 0.005, n))
        close_high = 100.0 * np.cumprod(1 + rng.normal(0, 0.04, n))
        idx = pd.date_range("2023-01-01", periods=n, freq="B")

        mkt_low = MarketData(
            prices={"AAPL": pd.Series(close_low, index=idx)},
            current_prices={"AAPL": float(close_low[-1])},
        )
        mkt_high = MarketData(
            prices={"AAPL": pd.Series(close_high, index=idx)},
            current_prices={"AAPL": float(close_high[-1])},
        )

        sizer = VolatilityTargetSizer(target_annual_vol=0.10, vol_window=20)
        shares_low = abs(sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt_low))
        shares_high = abs(sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt_high))

        assert shares_low > shares_high, (
            "Low volatility stock should receive more shares"
        )

    def test_close_returns_zero(self) -> None:
        sizer = VolatilityTargetSizer()
        assert sizer.calculate_size(
            _signal("AAPL", "close", 0.0), _Portfolio(), _market_data(["AAPL"])
        ) == 0.0

    def test_invalid_target_vol_raises(self) -> None:
        with pytest.raises(ValueError):
            VolatilityTargetSizer(target_annual_vol=-0.1)


# ---------------------------------------------------------------------------
# RiskParitySizer tests
# ---------------------------------------------------------------------------


class TestRiskParitySizer:
    def test_returns_nonzero(self) -> None:
        symbols = ["AAPL", "MSFT", "GOOGL"]
        sizer = RiskParitySizer(symbols=symbols, vol_window=20)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(symbols, {s: 100.0 for s in symbols}, n_bars=60)
        shares = sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt)
        assert shares != 0.0

    def test_lower_vol_higher_weight(self) -> None:
        """Symbol with lower vol should get more shares than high-vol symbol."""
        rng = np.random.default_rng(7)
        n = 60
        idx = pd.date_range("2023-01-01", periods=n, freq="B")

        # STABLE: very low vol
        stable = 100.0 * np.cumprod(1 + rng.normal(0, 0.002, n))
        # RISKY: high vol
        risky = 100.0 * np.cumprod(1 + rng.normal(0, 0.04, n))

        mkt = MarketData(
            prices={
                "STABLE": pd.Series(stable, index=idx),
                "RISKY": pd.Series(risky, index=idx),
            },
            current_prices={
                "STABLE": float(stable[-1]),
                "RISKY": float(risky[-1]),
            },
        )
        sizer = RiskParitySizer(symbols=["STABLE", "RISKY"], vol_window=20)
        portfolio = _Portfolio(nav=100_000.0)

        # Normalise by price to compare allocation in dollars
        stable_shares = abs(sizer.calculate_size(_signal("STABLE", "long"), portfolio, mkt))
        risky_shares = abs(sizer.calculate_size(_signal("RISKY", "long"), portfolio, mkt))
        stable_dollars = stable_shares * float(stable[-1])
        risky_dollars = risky_shares * float(risky[-1])

        assert stable_dollars >= risky_dollars, (
            "Lower vol symbol should get higher dollar allocation"
        )

    def test_close_returns_zero(self) -> None:
        sizer = RiskParitySizer(symbols=["AAPL"])
        assert sizer.calculate_size(
            _signal("AAPL", "close", 0.0), _Portfolio(), _market_data(["AAPL"])
        ) == 0.0

    def test_empty_symbols_raises(self) -> None:
        with pytest.raises(ValueError):
            RiskParitySizer(symbols=[])


# ---------------------------------------------------------------------------
# HalfKellySizer tests
# ---------------------------------------------------------------------------


class TestHalfKellySizer:
    def test_positive_edge_returns_nonzero(self) -> None:
        sizer = HalfKellySizer(win_rate=0.55, avg_win=0.02, avg_loss=0.01)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(["AAPL"], {"AAPL": 100.0})
        shares = sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt)
        assert shares != 0.0

    def test_negative_edge_returns_zero(self) -> None:
        """win_rate * avg_win < loss_rate * avg_loss → negative Kelly → no trade."""
        sizer = HalfKellySizer(win_rate=0.40, avg_win=0.01, avg_loss=0.05)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(["AAPL"], {"AAPL": 100.0})
        shares = sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt)
        assert shares == 0.0

    def test_kelly_fraction_formula(self) -> None:
        """Verify half-Kelly fraction math."""
        win_rate = 0.60
        avg_win = 0.03
        avg_loss = 0.015
        sizer = HalfKellySizer(win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss)

        full_kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        expected_half_kelly = full_kelly / 2.0
        assert abs(sizer.half_kelly_fraction - expected_half_kelly) < 1e-9

    def test_higher_strength_more_shares(self) -> None:
        sizer = HalfKellySizer(win_rate=0.60, avg_win=0.03, avg_loss=0.01)
        portfolio = _Portfolio(nav=100_000.0)
        mkt = _market_data(["AAPL"], {"AAPL": 100.0})

        shares_low = abs(sizer.calculate_size(_signal("AAPL", "long", 0.3), portfolio, mkt))
        shares_high = abs(sizer.calculate_size(_signal("AAPL", "long", 0.9), portfolio, mkt))
        # Higher conviction → more shares (or at least not fewer)
        assert shares_high >= shares_low

    def test_close_returns_zero(self) -> None:
        sizer = HalfKellySizer(win_rate=0.6, avg_win=0.02, avg_loss=0.01)
        assert sizer.calculate_size(
            _signal("AAPL", "close", 0.0), _Portfolio(), _market_data(["AAPL"])
        ) == 0.0

    def test_invalid_win_rate_raises(self) -> None:
        with pytest.raises(ValueError):
            HalfKellySizer(win_rate=1.5, avg_win=0.02, avg_loss=0.01)

    def test_update_stats(self) -> None:
        sizer = HalfKellySizer(win_rate=0.55, avg_win=0.02, avg_loss=0.01)
        old_fraction = sizer.half_kelly_fraction
        sizer.update_stats(win_rate=0.65, avg_win=0.03, avg_loss=0.01)
        new_fraction = sizer.half_kelly_fraction
        assert new_fraction != old_fraction


# ---------------------------------------------------------------------------
# get_sizer factory tests
# ---------------------------------------------------------------------------


class TestGetSizer:
    @pytest.mark.parametrize("name", ["equal_weight", "volatility_target"])
    def test_known_sizers_resolve(self, name: str) -> None:
        sizer = get_sizer(name)
        assert sizer is not None

    def test_risk_parity_requires_symbols(self) -> None:
        sizer = get_sizer("risk_parity", symbols=["AAPL", "MSFT"])
        assert isinstance(sizer, RiskParitySizer)

    def test_half_kelly_requires_stats(self) -> None:
        sizer = get_sizer("half_kelly", win_rate=0.55, avg_win=0.02, avg_loss=0.01)
        assert isinstance(sizer, HalfKellySizer)

    def test_unknown_sizer_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown sizer"):
            get_sizer("magic_sizer")

    def test_case_insensitive(self) -> None:
        sizer = get_sizer("Equal_Weight")
        assert isinstance(sizer, EqualWeightSizer)


# ---------------------------------------------------------------------------
# Max position cap tests (parametrized across all sizers)
# ---------------------------------------------------------------------------


class TestMaxPositionCap:
    @pytest.mark.parametrize("max_pct", [0.05, 0.10, 0.20])
    def test_equal_weight_cap(self, max_pct: float) -> None:
        sizer = EqualWeightSizer(n_signals=1, max_position_pct=max_pct)
        portfolio = _Portfolio(nav=100_000.0)
        price = 100.0
        mkt = _market_data(["AAPL"], {"AAPL": price})
        shares = abs(sizer.calculate_size(_signal("AAPL", "long"), portfolio, mkt))
        assert shares * price <= portfolio.nav * max_pct + price  # +price for floor rounding

    @pytest.mark.parametrize("max_pct", [0.05, 0.10])
    def test_vol_target_cap(self, max_pct: float) -> None:
        sizer = VolatilityTargetSizer(target_annual_vol=0.50, max_position_pct=max_pct)
        portfolio = _Portfolio(nav=100_000.0)
        price = 10.0  # Low price → more shares without cap
        mkt = _market_data(["CHEAP"], {"CHEAP": price}, n_bars=60)
        shares = abs(sizer.calculate_size(_signal("CHEAP", "long"), portfolio, mkt))
        assert shares * price <= portfolio.nav * max_pct + price
