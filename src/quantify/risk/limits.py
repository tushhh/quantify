"""
quantify.risk.limits
~~~~~~~~~~~~~~~~~~~~~
Hard-limit enforcement for the Quantify trading system.

This module provides a configurable :class:`RiskLimits` dataclass and a
:class:`LimitsEnforcer` class that validates and adjusts orders before they
reach the broker.  All checks are synchronous and designed to run inline in
the order-submission path with negligible overhead.

Limits enforced
---------------
* ``max_single_position``   — maximum fraction of NAV in any one symbol (10 %)
* ``max_sector_exposure``   — maximum fraction of NAV in any one sector (30 %)
* ``max_gross_leverage``    — maximum sum(|position weights|) (1.5×)
* ``max_open_orders``       — maximum concurrent open/pending orders (50)
* ``max_daily_trades``      — maximum round-trip trades in a calendar day (200)

All thresholds are configurable via :class:`RiskLimits` or loaded from the
:mod:`quantify.config` settings singleton.

Usage
-----
    from quantify.risk.limits import LimitsEnforcer, RiskLimits

    enforcer = LimitsEnforcer(limits=RiskLimits())
    allowed, reason = enforcer.can_open_position(order, portfolio)
    safe_order = enforcer.adjust_order_size(order, portfolio)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Protocol, runtime_checkable


log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Order / Position protocols
# ---------------------------------------------------------------------------
# The execution module does not yet expose concrete Order / Position classes.
# We define duck-typed protocols here so the enforcer works with any
# compatible implementation, including the real Alpaca-backed classes when
# they land.


@runtime_checkable
class PositionProtocol(Protocol):
    """Minimal position interface consumed by the enforcer."""

    @property
    def symbol(self) -> str: ...

    @property
    def quantity(self) -> float: ...

    @property
    def market_value(self) -> float: ...


@runtime_checkable
class OrderProtocol(Protocol):
    """Minimal order interface consumed by the enforcer."""

    @property
    def symbol(self) -> str: ...

    @property
    def quantity(self) -> float:
        """Absolute share count; sign carries direction."""
        ...

    @property
    def side(self) -> str:
        """``"buy"`` or ``"sell"``."""
        ...

    @property
    def limit_price(self) -> float | None: ...


@runtime_checkable
class PortfolioProtocol(Protocol):
    """Minimal portfolio interface consumed by the enforcer."""

    @property
    def nav(self) -> float: ...

    @property
    def cash(self) -> float: ...

    @property
    def positions(self) -> dict[str, PositionProtocol]: ...


# ---------------------------------------------------------------------------
# Concrete minimal Order / Fill / Position dataclasses
# ---------------------------------------------------------------------------
# These lightweight dataclasses satisfy the protocols above and are the
# canonical types used throughout the risk module until the execution layer
# provides its own concrete implementations.


@dataclass
class Position:
    """
    Represents an open equity position.

    Attributes
    ----------
    symbol:
        Ticker symbol.
    quantity:
        Signed share count (positive = long, negative = short).
    average_entry_price:
        Volume-weighted average fill price.
    current_price:
        Latest mark price used for market_value.
    """

    symbol: str
    quantity: float
    average_entry_price: float
    current_price: float

    @property
    def market_value(self) -> float:
        """Signed market value (positive for long, negative for short)."""
        return self.quantity * self.current_price

    @property
    def unrealised_pnl(self) -> float:
        """Unrealised P&L = (current_price - avg_entry) × quantity."""
        return (self.current_price - self.average_entry_price) * self.quantity

    def __repr__(self) -> str:
        return (
            f"Position({self.symbol!r}, qty={self.quantity:+.0f}, "
            f"entry={self.average_entry_price:.4f}, mark={self.current_price:.4f})"
        )


@dataclass
class Fill:
    """
    Represents a single execution fill.

    Attributes
    ----------
    order_id:
        Unique identifier of the parent order.
    symbol:
        Ticker symbol.
    quantity:
        Filled share count (signed).
    fill_price:
        Execution price.
    commission:
        Total commission charged for this fill.
    filled_at:
        UTC timestamp of the fill.
    """

    order_id: str
    symbol: str
    quantity: float
    fill_price: float
    commission: float
    filled_at: datetime

    @property
    def gross_value(self) -> float:
        """Absolute dollar value of the fill (|quantity| × fill_price)."""
        return abs(self.quantity) * self.fill_price

    @property
    def net_value(self) -> float:
        """Gross value minus commission."""
        return self.gross_value - self.commission


@dataclass
class Order:
    """
    Represents a pending or submitted order.

    Attributes
    ----------
    order_id:
        Unique identifier (UUID string recommended).
    symbol:
        Ticker symbol.
    quantity:
        Signed share count (positive = buy, negative = sell/short).
    side:
        ``"buy"`` or ``"sell"``.
    order_type:
        ``"market"``, ``"limit"``, or ``"stop"``.
    limit_price:
        Required for ``"limit"`` orders; ``None`` for market orders.
    stop_price:
        Required for ``"stop"`` orders; ``None`` otherwise.
    strategy_name:
        The strategy that generated this order (for attribution).
    created_at:
        UTC creation timestamp.
    metadata:
        Arbitrary key/value pairs for diagnostics.
    """

    order_id: str
    symbol: str
    quantity: float
    side: str
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    strategy_name: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.side not in ("buy", "sell"):
            raise ValueError(f"Order.side must be 'buy' or 'sell', got '{self.side}'")
        if self.order_type not in ("market", "limit", "stop"):
            raise ValueError(
                f"Order.order_type must be 'market', 'limit', or 'stop', "
                f"got '{self.order_type}'"
            )
        if self.quantity == 0:
            raise ValueError("Order.quantity must be non-zero")

    def with_quantity(self, new_quantity: float) -> "Order":
        """Return a copy of this order with a modified quantity."""
        import dataclasses
        return dataclasses.replace(self, quantity=new_quantity)

    def __repr__(self) -> str:
        lp = f" @ {self.limit_price:.4f}" if self.limit_price is not None else ""
        return (
            f"Order({self.order_id!r}, {self.symbol!r}, "
            f"{self.side} {abs(self.quantity):.0f}{lp})"
        )


# ---------------------------------------------------------------------------
# RiskLimits dataclass
# ---------------------------------------------------------------------------


@dataclass
class RiskLimits:
    """
    All configurable hard-limit thresholds.

    All fraction-based limits are expressed as decimals (0.10 = 10 %).

    Parameters
    ----------
    max_single_position:
        Maximum fractional NAV exposure in any single symbol.  Default: 0.10.
    max_sector_exposure:
        Maximum fractional NAV exposure in any single GICS sector.  Default: 0.30.
    max_gross_leverage:
        Maximum sum of absolute position weights.  Default: 1.5.
    max_open_orders:
        Maximum number of orders that may be pending simultaneously.  Default: 50.
    max_daily_trades:
        Maximum number of new orders (one-way) submitted in a single calendar
        day.  Default: 200.
    min_order_size:
        Minimum absolute share count; orders below this are rejected.
        Default: 1.
    """

    max_single_position: float = 0.10
    max_sector_exposure: float = 0.30
    max_gross_leverage: float = 1.50
    max_open_orders: int = 50
    max_daily_trades: int = 200
    min_order_size: float = 1.0

    def __post_init__(self) -> None:
        if not 0 < self.max_single_position <= 1:
            raise ValueError(f"max_single_position must be in (0, 1], got {self.max_single_position}")
        if not 0 < self.max_sector_exposure <= 1:
            raise ValueError(f"max_sector_exposure must be in (0, 1], got {self.max_sector_exposure}")
        if self.max_gross_leverage < 1:
            raise ValueError(f"max_gross_leverage must be >= 1, got {self.max_gross_leverage}")
        if self.max_open_orders < 1:
            raise ValueError(f"max_open_orders must be >= 1, got {self.max_open_orders}")
        if self.max_daily_trades < 1:
            raise ValueError(f"max_daily_trades must be >= 1, got {self.max_daily_trades}")

    @classmethod
    def from_settings(cls) -> "RiskLimits":
        """
        Load limits from the module-level settings singleton.

        Falls back gracefully to defaults if settings are unavailable.
        """
        try:
            from quantify.config import settings  # type: ignore[attr-defined]
            if settings is not None:
                r = settings.risk
                return cls(
                    max_single_position=r.max_single_position,
                    max_sector_exposure=r.max_sector_exposure,
                    max_gross_leverage=r.max_gross_leverage,
                )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "RiskLimits.from_settings: could not load config (%s) — using defaults", exc
            )
        return cls()


# ---------------------------------------------------------------------------
# LimitsEnforcer
# ---------------------------------------------------------------------------


class LimitsEnforcer:
    """
    Validates and adjusts orders to comply with :class:`RiskLimits`.

    The enforcer is stateful: it tracks open-order count and daily trade
    count internally.  Callers should use a single long-lived enforcer
    instance per trading session.

    Parameters
    ----------
    limits:
        :class:`RiskLimits` instance defining all thresholds.  If ``None``
        the enforcer loads limits from the settings singleton.
    sector_map:
        Optional mapping from symbol to sector name used for sector-exposure
        checks.  Can be updated at runtime via the ``sector_map`` attribute.
    """

    def __init__(
        self,
        limits: RiskLimits | None = None,
        sector_map: dict[str, str] | None = None,
    ) -> None:
        self.limits: RiskLimits = limits or RiskLimits.from_settings()
        self.sector_map: dict[str, str] = sector_map or {}

        # Internal counters (reset at start of each trading day)
        self._daily_trade_count: int = 0
        self._trade_day: date | None = None
        self._open_order_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def can_open_position(
        self,
        order: Any,
        portfolio: Any,
        *,
        limits: RiskLimits | None = None,
    ) -> tuple[bool, str]:
        """
        Determine whether submitting *order* would violate any hard limit.

        Parameters
        ----------
        order:
            The order to validate (must satisfy :class:`OrderProtocol`).
        portfolio:
            Current portfolio state (must satisfy :class:`PortfolioProtocol`).
        limits:
            Override the enforcer's own limits for this call.

        Returns
        -------
        (bool, str)
            ``(True, "OK")`` if all limits pass.
            ``(False, reason)`` where *reason* is a human-readable
            explanation of the first violated limit.
        """
        lim = limits or self.limits
        self._refresh_daily_counter()

        # --- Daily trade count ------------------------------------------
        if self._daily_trade_count >= lim.max_daily_trades:
            reason = (
                f"Daily trade limit reached: {self._daily_trade_count} / "
                f"{lim.max_daily_trades} orders submitted today."
            )
            log.warning("can_open_position: REJECTED %s — %s", order.symbol, reason)
            return False, reason

        # --- Open order count -------------------------------------------
        if self._open_order_count >= lim.max_open_orders:
            reason = (
                f"Open order limit reached: {self._open_order_count} / "
                f"{lim.max_open_orders} orders currently open."
            )
            log.warning("can_open_position: REJECTED %s — %s", order.symbol, reason)
            return False, reason

        nav = float(portfolio.nav)
        if nav <= 0:
            reason = "Portfolio NAV is zero or negative — cannot size orders."
            log.warning("can_open_position: REJECTED %s — %s", order.symbol, reason)
            return False, reason

        # --- Single position size ---------------------------------------
        order_value = abs(order.quantity) * self._estimate_price(order, portfolio)
        existing_mv = abs(
            portfolio.positions.get(order.symbol, _ZeroPosition()).market_value
        )
        projected_mv = existing_mv + order_value
        projected_weight = projected_mv / nav

        if projected_weight > lim.max_single_position:
            reason = (
                f"Single-position limit: projected weight {projected_weight:.2%} "
                f"for {order.symbol} exceeds limit {lim.max_single_position:.2%}."
            )
            log.warning("can_open_position: REJECTED %s — %s", order.symbol, reason)
            return False, reason

        # --- Gross leverage -------------------------------------------
        total_exposure = sum(
            abs(p.market_value) for p in portfolio.positions.values()
        )
        projected_gross = (total_exposure + order_value) / nav

        if projected_gross > lim.max_gross_leverage:
            reason = (
                f"Gross leverage limit: projected {projected_gross:.3f}x "
                f"exceeds limit {lim.max_gross_leverage:.3f}x."
            )
            log.warning("can_open_position: REJECTED %s — %s", order.symbol, reason)
            return False, reason

        # --- Sector exposure --------------------------------------------
        if self.sector_map:
            sector = self.sector_map.get(order.symbol, "Unknown")
            sector_mv = sum(
                abs(p.market_value)
                for sym, p in portfolio.positions.items()
                if self.sector_map.get(sym, "Unknown") == sector
            )
            projected_sector_weight = (sector_mv + order_value) / nav
            if projected_sector_weight > lim.max_sector_exposure:
                reason = (
                    f"Sector-exposure limit: projected weight {projected_sector_weight:.2%} "
                    f"for sector '{sector}' exceeds limit {lim.max_sector_exposure:.2%}."
                )
                log.warning("can_open_position: REJECTED %s — %s", order.symbol, reason)
                return False, reason

        log.debug(
            "can_open_position: ALLOWED %s qty=%+.0f projected_weight=%.2%%",
            order.symbol, order.quantity, projected_weight * 100,
        )
        return True, "OK"

    def adjust_order_size(
        self,
        order: Order,
        portfolio: Any,
        *,
        limits: RiskLimits | None = None,
    ) -> Order:
        """
        Reduce the order's quantity to the largest size that satisfies all
        hard limits.

        If the order would violate a non-size limit (daily count, open
        orders) the original order is returned unchanged and a warning is
        logged — callers should call :meth:`can_open_position` first to
        detect those cases.

        Parameters
        ----------
        order:
            The order whose size should be adjusted (must be an
            :class:`Order` instance so we can call ``with_quantity``).
        portfolio:
            Current portfolio state.
        limits:
            Override the enforcer's own limits for this call.

        Returns
        -------
        Order
            A (possibly modified) copy with the adjusted quantity.
            Returns a copy with ``quantity=0`` if no positive size is
            permissible — callers should discard zero-quantity orders.
        """
        lim = limits or self.limits
        nav = float(portfolio.nav)
        if nav <= 0:
            log.warning(
                "adjust_order_size: NAV <= 0 for %s — returning zero-qty order",
                order.symbol,
            )
            return order.with_quantity(0.0)

        price = self._estimate_price(order, portfolio)
        if price <= 0:
            log.warning(
                "adjust_order_size: cannot estimate price for %s — returning original order",
                order.symbol,
            )
            return order

        sign = 1.0 if order.quantity > 0 else -1.0

        # --- Single position cap ----------------------------------------
        existing_mv = abs(
            portfolio.positions.get(order.symbol, _ZeroPosition()).market_value
        )
        max_mv_for_symbol = nav * lim.max_single_position
        available_mv_for_symbol = max(0.0, max_mv_for_symbol - existing_mv)
        max_shares_single = available_mv_for_symbol / price

        # --- Gross leverage cap -----------------------------------------
        total_exposure = sum(
            abs(p.market_value) for p in portfolio.positions.values()
        )
        max_total_exposure = nav * lim.max_gross_leverage
        available_exposure = max(0.0, max_total_exposure - total_exposure)
        max_shares_leverage = available_exposure / price

        # --- Sector cap -------------------------------------------------
        max_shares_sector = float("inf")
        if self.sector_map:
            sector = self.sector_map.get(order.symbol, "Unknown")
            sector_mv = sum(
                abs(p.market_value)
                for sym, p in portfolio.positions.items()
                if self.sector_map.get(sym, "Unknown") == sector
            )
            max_sector_mv = nav * lim.max_sector_exposure
            available_sector_mv = max(0.0, max_sector_mv - sector_mv)
            max_shares_sector = available_sector_mv / price

        # Apply the binding constraint
        max_shares = min(
            abs(order.quantity),
            max_shares_single,
            max_shares_leverage,
            max_shares_sector,
        )
        # Enforce minimum order size
        if max_shares < lim.min_order_size:
            log.warning(
                "adjust_order_size: %s adjusted to 0 (max_shares=%.2f < min_order_size=%.2f)",
                order.symbol, max_shares, lim.min_order_size,
            )
            return order.with_quantity(0.0)

        import math as _math
        final_qty = sign * _math.floor(max_shares)

        if final_qty != order.quantity:
            log.info(
                "adjust_order_size: %s qty %+.0f → %+.0f "
                "(cap: single=%.0f leverage=%.0f sector=%.0f)",
                order.symbol,
                order.quantity, final_qty,
                max_shares_single, max_shares_leverage,
                max_shares_sector if max_shares_sector != float("inf") else -1,
            )

        return order.with_quantity(final_qty)

    # ------------------------------------------------------------------
    # Daily counter management
    # ------------------------------------------------------------------

    def record_order_submitted(self) -> None:
        """
        Increment the daily trade counter and open-order counter.

        Call this once per order successfully submitted to the broker.
        """
        self._refresh_daily_counter()
        self._daily_trade_count += 1
        self._open_order_count += 1
        log.debug(
            "LimitsEnforcer.record_order_submitted: "
            "daily=%d open=%d",
            self._daily_trade_count, self._open_order_count,
        )

    def record_order_filled(self) -> None:
        """
        Decrement the open-order counter when an order is fully filled
        or cancelled.
        """
        self._open_order_count = max(0, self._open_order_count - 1)
        log.debug(
            "LimitsEnforcer.record_order_filled: open=%d", self._open_order_count
        )

    def record_order_cancelled(self) -> None:
        """Alias for :meth:`record_order_filled` (decrements open-order count)."""
        self.record_order_filled()

    def reset_daily_counts(self) -> None:
        """
        Manually reset the daily trade counter and the trade date.

        Useful for testing or for explicitly resetting counters at
        market open without waiting for the auto-reset logic.
        """
        self._daily_trade_count = 0
        self._trade_day = datetime.now(tz=timezone.utc).date()
        log.info(
            "LimitsEnforcer.reset_daily_counts: counters reset for %s",
            self._trade_day,
        )

    def _refresh_daily_counter(self) -> None:
        """Auto-reset the daily trade counter at the start of each calendar day."""
        today = datetime.now(tz=timezone.utc).date()
        if self._trade_day != today:
            self._daily_trade_count = 0
            self._trade_day = today
            log.debug(
                "LimitsEnforcer._refresh_daily_counter: new trading day %s", today
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _estimate_price(self, order: Any, portfolio: Any) -> float:
        """
        Best-effort price estimate for sizing calculations.

        Priority:
        1. ``order.limit_price`` (for limit orders)
        2. existing position's ``current_price`` attribute
        3. ``market_value / quantity`` from existing position
        4. Falls back to 1.0 with a warning if no data is available.
        """
        if order.limit_price is not None and order.limit_price > 0:
            return float(order.limit_price)

        pos = portfolio.positions.get(order.symbol)
        if pos is not None:
            if hasattr(pos, "current_price") and pos.current_price > 0:
                return float(pos.current_price)
            if pos.quantity != 0:
                estimated = abs(pos.market_value / pos.quantity)
                if estimated > 0:
                    return estimated

        log.warning(
            "_estimate_price: no price available for %s — using 1.0 (sizing may be wrong)",
            order.symbol,
        )
        return 1.0

    # ------------------------------------------------------------------
    # Properties / introspection
    # ------------------------------------------------------------------

    @property
    def daily_trade_count(self) -> int:
        """Number of orders submitted so far today."""
        self._refresh_daily_counter()
        return self._daily_trade_count

    @property
    def open_order_count(self) -> int:
        """Number of currently open / pending orders."""
        return self._open_order_count

    def __repr__(self) -> str:
        return (
            f"LimitsEnforcer("
            f"daily_trades={self.daily_trade_count}/{self.limits.max_daily_trades}, "
            f"open_orders={self.open_order_count}/{self.limits.max_open_orders})"
        )


# ---------------------------------------------------------------------------
# Internal zero-position sentinel
# ---------------------------------------------------------------------------


class _ZeroPosition:
    """Sentinel used when a symbol has no open position."""

    symbol: str = ""
    quantity: float = 0.0
    market_value: float = 0.0


__all__ = [
    "RiskLimits",
    "LimitsEnforcer",
    "Order",
    "Fill",
    "Position",
]
