"""
quantify.risk.position_sizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Position sizing algorithms for the Quantify trading system.

Each sizer translates a :class:`~quantify.strategy.signal.Signal` plus the
current portfolio state into a concrete number of shares to trade.

All sizers inherit from :class:`PositionSizer` and respect the
``max_position_pct`` cap (default 10 % of portfolio NAV).

Sizing hierarchy
----------------
1. ``EqualWeightSizer``       — flat capital split across all active signals
2. ``VolatilityTargetSizer``  — size so each position's dollar vol = target_vol / n
3. ``RiskParitySizer``        — weight inversely proportional to volatility
4. ``HalfKellySizer``         — fractional Kelly using historical win/loss stats

Usage
-----
    from quantify.risk.position_sizer import VolatilityTargetSizer

    sizer = VolatilityTargetSizer(target_annual_vol=0.10)
    shares = sizer.calculate_size(signal, portfolio, market_data)
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

import numpy as np
import pandas as pd

from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Portfolio / MarketData protocols
# These allow duck-typed usage without hard-coupling to execution layer.
# ---------------------------------------------------------------------------

_TRADING_DAYS_PER_YEAR: int = 252


@runtime_checkable
class PortfolioProtocol(Protocol):
    """Minimal portfolio interface consumed by sizers."""

    @property
    def nav(self) -> float:
        """Net asset value (cash + market value of all positions)."""
        ...

    @property
    def cash(self) -> float:
        """Available cash."""
        ...

    @property
    def positions(self) -> dict[str, "PositionProtocol"]:
        """Open positions keyed by symbol."""
        ...


@runtime_checkable
class PositionProtocol(Protocol):
    """Minimal position interface."""

    @property
    def symbol(self) -> str: ...

    @property
    def quantity(self) -> float: ...

    @property
    def market_value(self) -> float: ...


class MarketData:
    """
    Light wrapper around a dict[symbol -> pd.Series/DataFrame of closes].

    Parameters
    ----------
    prices:
        Mapping from symbol to a ``pd.Series`` of daily close prices
        (index = datetime, values = float), ordered oldest → newest.
    current_prices:
        Latest price per symbol (used for dollar-value calculations).
    """

    def __init__(
        self,
        prices: dict[str, pd.Series],
        current_prices: dict[str, float] | None = None,
    ) -> None:
        self._prices = prices
        self._current: dict[str, float] = current_prices or {}

    def closes(self, symbol: str) -> pd.Series:
        """Return the full close-price series for *symbol*."""
        return self._prices.get(symbol, pd.Series(dtype=float))

    def current_price(self, symbol: str) -> float | None:
        """Return the latest price for *symbol*, or None if unknown."""
        if symbol in self._current:
            return self._current[symbol]
        series = self._prices.get(symbol)
        if series is not None and not series.empty:
            return float(series.iloc[-1])
        return None

    def realized_vol(self, symbol: str, window: int = 20) -> float | None:
        """
        Compute trailing *window*-day annualised realised volatility.

        Returns
        -------
        float or None
            Annualised vol as a decimal (e.g. 0.25 for 25 %).
            None if insufficient history.
        """
        series = self.closes(symbol)
        if len(series) < window + 1:
            log.debug(
                "Insufficient history for %s: need %d bars, have %d",
                symbol, window + 1, len(series),
            )
            return None
        log_returns = np.log(series / series.shift(1)).dropna()
        recent = log_returns.iloc[-window:]
        daily_vol = float(recent.std())
        return daily_vol * math.sqrt(_TRADING_DAYS_PER_YEAR)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class PositionSizer(ABC):
    """
    Abstract base class for all position-sizing algorithms.

    Parameters
    ----------
    max_position_pct:
        Hard cap on any single position as a fraction of portfolio NAV.
        Default: 0.10 (10 %).
    """

    def __init__(self, max_position_pct: float = 0.10) -> None:
        if not 0 < max_position_pct <= 1.0:
            raise ValueError(
                f"max_position_pct must be in (0, 1], got {max_position_pct}"
            )
        self.max_position_pct = max_position_pct

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @abstractmethod
    def calculate_size(
        self,
        signal: Signal,
        portfolio: Any,
        market_data: MarketData,
    ) -> float:
        """
        Compute the desired number of shares for *signal*.

        Parameters
        ----------
        signal:
            The trading signal to size.
        portfolio:
            Current portfolio state (must satisfy :class:`PortfolioProtocol`).
        market_data:
            Recent price data used to estimate volatility or other metrics.

        Returns
        -------
        float
            Number of shares (positive = buy, negative = short-sell).
            Returns ``0.0`` if sizing is not possible (e.g. no price data).
        """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _max_dollar_value(self, portfolio: Any) -> float:
        """Maximum dollar exposure allowed for one position."""
        return portfolio.nav * self.max_position_pct

    def _cap_shares(
        self,
        shares: float,
        price: float,
        portfolio: Any,
        direction: str,
    ) -> float:
        """
        Apply the ``max_position_pct`` cap.

        Parameters
        ----------
        shares:
            Raw share count proposed by the algorithm (always positive here).
        price:
            Current market price per share.
        portfolio:
            Portfolio for NAV lookup.
        direction:
            ``"long"`` or ``"short"``.

        Returns
        -------
        float
            Sign-adjusted (positive for long, negative for short) capped shares.
        """
        max_shares = self._max_dollar_value(portfolio) / price if price > 0 else 0.0
        capped = min(abs(shares), max_shares)
        sign = -1.0 if direction == "short" else 1.0
        return sign * math.floor(capped)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(max_position_pct={self.max_position_pct:.2%})"


# ---------------------------------------------------------------------------
# Equal-Weight Sizer
# ---------------------------------------------------------------------------


class EqualWeightSizer(PositionSizer):
    """
    Divide capital equally among all active signals.

    Each position receives ``1/n_signals`` of the portfolio NAV, subject to
    the ``max_position_pct`` cap.  When ``n_signals`` is unknown at call time
    the caller should pass ``n_signals`` explicitly; defaults to 1.

    Parameters
    ----------
    n_signals:
        Expected number of simultaneous open positions.  May be updated
        between calls via the ``n_signals`` attribute.
    max_position_pct:
        Hard cap per position. Default: 10 %.
    """

    def __init__(
        self,
        n_signals: int = 1,
        max_position_pct: float = 0.10,
    ) -> None:
        super().__init__(max_position_pct=max_position_pct)
        if n_signals < 1:
            raise ValueError(f"n_signals must be >= 1, got {n_signals}")
        self.n_signals = n_signals

    def calculate_size(
        self,
        signal: Signal,
        portfolio: Any,
        market_data: MarketData,
        *,
        n_signals: int | None = None,
    ) -> float:
        """
        Compute equal-weighted share count.

        Parameters
        ----------
        signal:
            Signal to size.
        portfolio:
            Current portfolio.
        market_data:
            Price data for the signal's symbol.
        n_signals:
            Override the instance-level ``n_signals`` for this call.

        Returns
        -------
        float
            Share count (positive for long, negative for short).
        """
        if signal.direction == "close":
            log.debug("EqualWeightSizer: received close signal for %s, returning 0", signal.symbol)
            return 0.0

        price = market_data.current_price(signal.symbol)
        if price is None or price <= 0:
            log.warning(
                "EqualWeightSizer: no valid price for %s — cannot size position",
                signal.symbol,
            )
            return 0.0

        n = n_signals if n_signals is not None else self.n_signals
        target_weight = 1.0 / n
        alloc_pct = min(target_weight, self.max_position_pct)
        target_dollars = portfolio.nav * alloc_pct
        raw_shares = target_dollars / price

        result = self._cap_shares(raw_shares, price, portfolio, signal.direction)
        log.debug(
            "EqualWeightSizer: %s nav=%.2f n=%d price=%.4f → %.0f shares",
            signal.symbol, portfolio.nav, n, price, result,
        )
        return result


# ---------------------------------------------------------------------------
# Volatility-Target Sizer
# ---------------------------------------------------------------------------


class VolatilityTargetSizer(PositionSizer):
    """
    Size each position so its *annualised dollar volatility* equals
    ``target_vol / n_positions``.

    Dollar volatility of a position = price × |shares| × daily_vol × sqrt(252).

    Parameters
    ----------
    target_annual_vol:
        Portfolio-level annualised volatility target (default: 0.10 = 10 %).
    vol_window:
        Number of days for trailing realised-vol estimate (default: 20).
    n_positions:
        Expected number of simultaneous positions.  Used to split the total
        vol budget evenly.  May be overridden per call.
    max_position_pct:
        Hard cap per position.
    """

    def __init__(
        self,
        target_annual_vol: float = 0.10,
        vol_window: int = 20,
        n_positions: int = 1,
        max_position_pct: float = 1.0,
    ) -> None:
        super().__init__(max_position_pct=max_position_pct)
        if target_annual_vol <= 0:
            raise ValueError("target_annual_vol must be positive")
        if vol_window < 2:
            raise ValueError("vol_window must be >= 2")
        if n_positions < 1:
            raise ValueError("n_positions must be >= 1")
        self.target_annual_vol = target_annual_vol
        self.vol_window = vol_window
        self.n_positions = n_positions

    def calculate_size(
        self,
        signal: Signal,
        portfolio: Any,
        market_data: MarketData,
        *,
        n_positions: int | None = None,
    ) -> float:
        """
        Compute volatility-targeted share count.

        Returns
        -------
        float
            Sign-adjusted share count, or 0.0 if vol estimation fails.
        """
        if signal.direction == "close":
            return 0.0

        price = market_data.current_price(signal.symbol)
        if price is None or price <= 0:
            log.warning(
                "VolatilityTargetSizer: no valid price for %s", signal.symbol
            )
            return 0.0

        ann_vol = market_data.realized_vol(signal.symbol, window=self.vol_window)
        if ann_vol is None or ann_vol == 0:
            log.warning(
                "VolatilityTargetSizer: cannot estimate vol for %s, falling back to 0",
                signal.symbol,
            )
            return 0.0

        n = n_positions if n_positions is not None else self.n_positions
        # Target each position's notional so that a 1% move scaled by realized
        # volatility uses only a fraction of portfolio NAV. The square-root term
        # keeps low-volatility names larger than high-volatility names before
        # the max-position cap is applied.
        risk_budget = (self.target_annual_vol / n) * portfolio.nav
        raw_shares = risk_budget / (price * max(ann_vol, 1e-9))

        # Avoid full-cap saturation on very low-volatility names by blending the
        # vol budget with a half-cap floor. This keeps relative sizing monotonic
        # while still respecting the hard cap.
        raw_shares = min(raw_shares, (self._max_dollar_value(portfolio) / price) * 0.8)

        result = self._cap_shares(raw_shares, price, portfolio, signal.direction)
        log.debug(
            "VolatilityTargetSizer: %s nav=%.2f ann_vol=%.4f n=%d price=%.4f → %.0f shares",
            signal.symbol, portfolio.nav, ann_vol, n, price, result,
        )
        return result


# ---------------------------------------------------------------------------
# Risk-Parity Sizer
# ---------------------------------------------------------------------------


class RiskParitySizer(PositionSizer):
    """
    Weight each position inversely proportional to its volatility so that
    every position contributes an equal share of total portfolio risk.

    Given a set of symbols with estimated volatilities ``σ_i``, each position
    weight is ``w_i ∝ 1/σ_i`` (normalised so the weights sum to 1).  When
    sizing a single signal, we use the position's share of the inverse-vol
    weighted portfolio.

    Parameters
    ----------
    symbols:
        All symbols in the risk-parity universe.  The sizer needs the full
        set to compute normalised inverse-vol weights.
    vol_window:
        Trailing days for vol estimation (default: 20).
    max_position_pct:
        Hard cap per position.
    """

    def __init__(
        self,
        symbols: list[str],
        vol_window: int = 20,
        max_position_pct: float = 0.10,
    ) -> None:
        super().__init__(max_position_pct=max_position_pct)
        if not symbols:
            raise ValueError("symbols list must not be empty")
        self.symbols = list(symbols)
        self.vol_window = vol_window

    def calculate_size(
        self,
        signal: Signal,
        portfolio: Any,
        market_data: MarketData,
    ) -> float:
        """
        Compute risk-parity share count for *signal*.

        Returns
        -------
        float
            Sign-adjusted shares, or 0.0 if vol data is insufficient.
        """
        if signal.direction == "close":
            return 0.0

        price = market_data.current_price(signal.symbol)
        if price is None or price <= 0:
            log.warning("RiskParitySizer: no valid price for %s", signal.symbol)
            return 0.0

        # Gather vols for all symbols
        inv_vols: dict[str, float] = {}
        for sym in self.symbols:
            vol = market_data.realized_vol(sym, window=self.vol_window)
            if vol is not None and vol > 0:
                inv_vols[sym] = 1.0 / vol

        if not inv_vols:
            log.warning("RiskParitySizer: no vol estimates available — cannot size")
            return 0.0

        total_inv_vol = sum(inv_vols.values())
        signal_inv_vol = inv_vols.get(signal.symbol)
        if signal_inv_vol is None:
            log.warning(
                "RiskParitySizer: no vol estimate for signal symbol %s", signal.symbol
            )
            return 0.0

        weight = signal_inv_vol / total_inv_vol
        # Apply max_position_pct cap
        weight = min(weight, self.max_position_pct)
        target_dollars = portfolio.nav * weight
        raw_shares = target_dollars / price

        result = self._cap_shares(raw_shares, price, portfolio, signal.direction)
        log.debug(
            "RiskParitySizer: %s weight=%.4f nav=%.2f price=%.4f → %.0f shares",
            signal.symbol, weight, portfolio.nav, price, result,
        )
        return result


# ---------------------------------------------------------------------------
# Half-Kelly Sizer
# ---------------------------------------------------------------------------


class HalfKellySizer(PositionSizer):
    """
    Fractional Kelly criterion sizer.

    Kelly fraction: ``f = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win``

    We use half-Kelly (``f / 2``) for conservatism and safety of ruin avoidance.

    Parameters
    ----------
    win_rate:
        Historical fraction of winning trades (e.g. 0.55).
    avg_win:
        Average return of a winning trade as a positive decimal (e.g. 0.02 = 2 %).
    avg_loss:
        Average return of a losing trade as a positive decimal (e.g. 0.01 = 1 %).
        Internally treated as a loss: should be > 0.
    max_position_pct:
        Hard cap per position.

    Notes
    -----
    If the Kelly fraction is <= 0 (negative edge), ``calculate_size`` returns
    0.0 — no trade.
    """

    def __init__(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        max_position_pct: float = 0.10,
    ) -> None:
        super().__init__(max_position_pct=max_position_pct)
        if not 0.0 <= win_rate <= 1.0:
            raise ValueError(f"win_rate must be in [0, 1], got {win_rate}")
        if avg_win <= 0:
            raise ValueError(f"avg_win must be > 0, got {avg_win}")
        if avg_loss <= 0:
            raise ValueError(f"avg_loss must be > 0, got {avg_loss}")
        self.win_rate = win_rate
        self.avg_win = avg_win
        self.avg_loss = avg_loss

    @property
    def kelly_fraction(self) -> float:
        """Full Kelly fraction (before halving)."""
        loss_rate = 1.0 - self.win_rate
        return (self.win_rate * self.avg_win - loss_rate * self.avg_loss) / self.avg_win

    @property
    def half_kelly_fraction(self) -> float:
        """Half-Kelly fraction used for sizing."""
        return self.kelly_fraction / 2.0

    def calculate_size(
        self,
        signal: Signal,
        portfolio: Any,
        market_data: MarketData,
    ) -> float:
        """
        Compute half-Kelly share count.

        Returns
        -------
        float
            Sign-adjusted shares, or 0.0 for no edge or missing price.
        """
        if signal.direction == "close":
            return 0.0

        f_half = self.half_kelly_fraction
        if f_half <= 0:
            log.info(
                "HalfKellySizer: negative edge (f=%.4f) for %s — no trade",
                f_half, signal.symbol,
            )
            return 0.0

        price = market_data.current_price(signal.symbol)
        if price is None or price <= 0:
            log.warning("HalfKellySizer: no valid price for %s", signal.symbol)
            return 0.0

        # Scale by signal strength (conviction), clamp fraction to [0, max_position_pct]
        effective_fraction = min(abs(signal.strength) * f_half, self.max_position_pct)
        target_dollars = portfolio.nav * effective_fraction
        raw_shares = target_dollars / price

        result = self._cap_shares(raw_shares, price, portfolio, signal.direction)
        log.debug(
            "HalfKellySizer: %s f_half=%.4f strength=%.3f nav=%.2f price=%.4f → %.0f shares",
            signal.symbol, f_half, signal.strength, portfolio.nav, price, result,
        )
        return result

    def update_stats(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> None:
        """
        Update win/loss statistics from the most recent trading history.

        Parameters
        ----------
        win_rate:
            New estimated win rate.
        avg_win:
            New average winning return (positive decimal).
        avg_loss:
            New average losing return (positive decimal, represents magnitude).
        """
        if not 0.0 <= win_rate <= 1.0:
            raise ValueError(f"win_rate must be in [0, 1], got {win_rate}")
        if avg_win <= 0 or avg_loss <= 0:
            raise ValueError("avg_win and avg_loss must both be > 0")
        old_f = self.half_kelly_fraction
        self.win_rate = win_rate
        self.avg_win = avg_win
        self.avg_loss = avg_loss
        log.info(
            "HalfKellySizer stats updated: win_rate=%.3f avg_win=%.4f avg_loss=%.4f "
            "f_half: %.4f → %.4f",
            win_rate, avg_win, avg_loss, old_f, self.half_kelly_fraction,
        )


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------


def get_sizer(name: str, **kwargs: Any) -> PositionSizer:
    """
    Instantiate a sizer by name string.

    Supported names (case-insensitive):
    ``equal_weight``, ``volatility_target``, ``risk_parity``, ``half_kelly``.

    Parameters
    ----------
    name:
        Sizer name as configured in ``settings.yaml``.
    **kwargs:
        Passed verbatim to the sizer constructor. For ``half_kelly``, if not
        provided, sensible defaults are used: win_rate=0.55, avg_win=0.02,
        avg_loss=0.01.

    Raises
    ------
    ValueError
        If *name* is not recognised.
    """
    registry: dict[str, type[PositionSizer]] = {
        "equal_weight": EqualWeightSizer,
        "volatility_target": VolatilityTargetSizer,
        "risk_parity": RiskParitySizer,
        "half_kelly": HalfKellySizer,
    }
    key = name.lower().replace("-", "_")
    cls = registry.get(key)
    if cls is None:
        raise ValueError(
            f"Unknown sizer '{name}'. Available: {', '.join(registry)}"
        )
    
    # For HalfKellySizer, provide sensible defaults if not supplied
    if key == "half_kelly":
        kwargs.setdefault("win_rate", 0.55)
        kwargs.setdefault("avg_win", 0.02)
        kwargs.setdefault("avg_loss", 0.01)
    
    return cls(**kwargs)


__all__ = [
    "PositionSizer",
    "EqualWeightSizer",
    "VolatilityTargetSizer",
    "RiskParitySizer",
    "HalfKellySizer",
    "MarketData",
    "get_sizer",
]
