"""
quantify.execution.order
~~~~~~~~~~~~~~~~~~~~~~~~
Core domain objects for the execution layer.

Provides immutable-by-convention dataclasses for orders, fills, positions,
and account information.  These are the lingua franca between strategies,
the order manager, and broker adapters.

Hierarchy
---------
Signal (strategy) → Order (order manager) → Fill (broker) → Position (portfolio)
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class OrderType(enum.Enum):
    """Supported order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(enum.Enum):
    """Whether an order is a buy or a sell."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(enum.Enum):
    """Lifecycle states of an order."""

    PENDING = "pending"       # Created locally, not yet sent to broker
    SUBMITTED = "submitted"   # Sent to broker, awaiting acknowledgement
    PARTIAL = "partial"       # Partially filled, still open
    FILLED = "filled"         # Fully filled
    CANCELLED = "cancelled"   # Cancelled before full fill
    REJECTED = "rejected"     # Rejected by broker or risk checks


class TimeInForce(enum.Enum):
    """Order duration / time-in-force codes."""

    DAY = "day"         # Cancel at end of regular session
    GTC = "gtc"         # Good-till-cancelled
    IOC = "ioc"         # Immediate-or-cancel
    FOK = "fok"         # Fill-or-kill
    OPG = "opg"         # At the open
    CLS = "cls"         # At the close


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------


@dataclass
class Order:
    """
    Represents an order in its full lifecycle from creation to fill.

    Parameters
    ----------
    symbol:
        Ticker symbol (e.g. ``"AAPL"``).
    side:
        :class:`OrderSide` — ``BUY`` or ``SELL``.
    order_type:
        :class:`OrderType` — ``MARKET``, ``LIMIT``, ``STOP``, or
        ``STOP_LIMIT``.
    quantity:
        Number of shares (or contracts).  Must be positive.
    limit_price:
        Limit price for ``LIMIT`` and ``STOP_LIMIT`` orders.  ``None``
        for market and stop orders.
    stop_price:
        Stop trigger price for ``STOP`` and ``STOP_LIMIT`` orders.
        ``None`` for other order types.
    time_in_force:
        :class:`TimeInForce` — defaults to ``DAY``.
    strategy_name:
        Name of the strategy that generated this order.  Used for P&L
        attribution and duplicate detection.
    status:
        Current :class:`OrderStatus`.  Starts as ``PENDING``.
    id:
        UUID string, auto-generated if not provided.
    created_at:
        When the order was created.  Defaults to ``datetime.utcnow()``.
    filled_at:
        When the order was fully filled.  ``None`` until then.
    filled_price:
        Average fill price across all partial fills.  ``None`` until filled.
    filled_quantity:
        Shares filled so far (across partial fills).
    commission:
        Total commission charged, accumulated across partial fills.
    notes:
        Free-text field for rejection reasons, broker messages, etc.
    """

    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    strategy_name: str

    # Optional pricing
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY

    # Lifecycle state — mutated by the order manager / broker adapter
    status: OrderStatus = field(default=OrderStatus.PENDING)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0
    commission: float = 0.0
    notes: str = ""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(
                f"Order quantity must be positive, got {self.quantity}"
            )
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT):
            if self.limit_price is None:
                raise ValueError(
                    f"limit_price is required for {self.order_type.value} orders"
                )
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            if self.stop_price is None:
                raise ValueError(
                    f"stop_price is required for {self.order_type.value} orders"
                )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        """True if the order can still be filled or cancelled."""
        return self.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)

    @property
    def is_closed(self) -> bool:
        """True if the order is in a terminal state."""
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED)

    @property
    def remaining_quantity(self) -> float:
        """Shares yet to be filled."""
        return self.quantity - self.filled_quantity

    @property
    def fill_rate(self) -> float:
        """Fraction of the order that has been filled (0.0 – 1.0)."""
        return self.filled_quantity / self.quantity if self.quantity else 0.0

    @property
    def notional_value(self) -> Optional[float]:
        """
        Estimated notional value.

        Uses ``filled_price`` if available, otherwise ``limit_price``.
        Returns ``None`` for unfilled market orders where no price anchor exists.
        """
        price = self.filled_price or self.limit_price
        if price is None:
            return None
        return price * self.quantity

    def apply_fill(self, fill: "Fill") -> None:
        """
        Update the order's state when a (partial) fill arrives.

        Parameters
        ----------
        fill:
            The :class:`Fill` to apply.

        Raises
        ------
        ValueError
            If the fill exceeds the remaining quantity or references a
            different order ID.
        """
        if fill.order_id != self.id:
            raise ValueError(
                f"Fill order_id {fill.order_id!r} does not match this order {self.id!r}"
            )
        if fill.quantity > self.remaining_quantity + 1e-9:
            raise ValueError(
                f"Fill quantity {fill.quantity} exceeds remaining {self.remaining_quantity}"
            )

        # Update running weighted-average fill price
        prev_notional = (self.filled_price or 0.0) * self.filled_quantity
        new_notional = fill.price * fill.quantity
        self.filled_quantity += fill.quantity
        self.filled_price = (prev_notional + new_notional) / self.filled_quantity
        self.commission += fill.commission

        # Transition status
        if abs(self.filled_quantity - self.quantity) < 1e-9:
            self.status = OrderStatus.FILLED
            self.filled_at = fill.timestamp
        else:
            self.status = OrderStatus.PARTIAL

    def __repr__(self) -> str:
        return (
            f"Order(id={self.id[:8]}, {self.side.value} {self.quantity} {self.symbol} "
            f"@ {self.order_type.value}, status={self.status.value})"
        )


# ---------------------------------------------------------------------------
# Fill
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fill:
    """
    Immutable record of an executed trade (partial or full fill).

    Parameters
    ----------
    order_id:
        ID of the :class:`Order` this fill belongs to.
    symbol:
        Ticker symbol.
    side:
        :class:`OrderSide` — direction of the trade.
    quantity:
        Number of shares executed in this fill event.
    price:
        Execution price for this fill.
    commission:
        Commission charged for this fill.
    timestamp:
        When the fill occurred.
    strategy_name:
        Originating strategy name, copied from the order for convenience.
    """

    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    timestamp: datetime
    strategy_name: str = ""

    @property
    def notional(self) -> float:
        """Gross notional value of this fill (quantity × price)."""
        return self.quantity * self.price

    @property
    def net_notional(self) -> float:
        """Net cash flow: notional + commission (commission is always positive)."""
        return self.notional + self.commission

    def __repr__(self) -> str:
        ts_str = self.timestamp.isoformat(timespec="seconds")
        return (
            f"Fill({self.side.value} {self.quantity} {self.symbol} "
            f"@ {self.price:.4f}, comm={self.commission:.4f}, ts={ts_str})"
        )


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


@dataclass
class Position:
    """
    Live position for a single symbol.

    Tracks both the entry cost basis and current market value so that both
    unrealized and realized P&L can be reported accurately.

    Parameters
    ----------
    symbol:
        Ticker symbol.
    quantity:
        Current signed position size.  Positive = long, negative = short.
    avg_cost:
        Volume-weighted average cost per share of the *current* position.
    market_price:
        Most recent market price (used for mark-to-market valuation).
    unrealized_pnl:
        Mark-to-market P&L on the open position.
    realized_pnl:
        Cumulative realized P&L from closed portions of this position.
    """

    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    market_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def side(self) -> str:
        """``"long"``, ``"short"``, or ``"flat"`` based on quantity sign."""
        if self.quantity > 1e-9:
            return "long"
        if self.quantity < -1e-9:
            return "short"
        return "flat"

    @property
    def market_value(self) -> float:
        """Current market value of the position (signed: negative for shorts)."""
        return self.quantity * self.market_price

    @property
    def cost_basis(self) -> float:
        """Total cost basis of the open position."""
        return self.quantity * self.avg_cost

    @property
    def total_pnl(self) -> float:
        """Sum of realized and unrealized P&L."""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def is_flat(self) -> bool:
        """True if the position has zero quantity."""
        return abs(self.quantity) < 1e-9

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def apply_fill(self, fill: Fill) -> None:
        """
        Update position state based on an incoming fill.

        Handles four cases:
        1. Opening a new position (flat → long or short).
        2. Adding to an existing position (same direction).
        3. Partially closing a position (reduces quantity).
        4. Reversing a position (crosses zero).

        Parameters
        ----------
        fill:
            The :class:`Fill` to apply.
        """
        qty_delta = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity

        if abs(self.quantity) < 1e-9:
            # Flat → new position
            self.quantity = qty_delta
            self.avg_cost = fill.price
            self.unrealized_pnl = 0.0

        elif (self.quantity > 0) == (qty_delta > 0):
            # Adding to existing position (same direction)
            total_cost = self.avg_cost * self.quantity + fill.price * qty_delta
            self.quantity += qty_delta
            self.avg_cost = total_cost / self.quantity if self.quantity else 0.0

        else:
            # Reducing or reversing
            closed_qty = min(abs(qty_delta), abs(self.quantity))
            # Realized P&L on the closed portion
            if self.quantity > 0:
                # Long position being reduced/reversed
                self.realized_pnl += closed_qty * (fill.price - self.avg_cost)
            else:
                # Short position being reduced/reversed
                self.realized_pnl += closed_qty * (self.avg_cost - fill.price)

            residual = qty_delta + self.quantity  # signed residual after close
            if abs(residual) < 1e-9:
                # Position fully closed
                self.quantity = 0.0
                self.avg_cost = 0.0
            elif (residual > 0) != (self.quantity > 0):
                # Position reversed — start fresh on the other side
                self.avg_cost = fill.price
                self.quantity = residual
            else:
                self.quantity += qty_delta

        self.mark_to_market(fill.price)

    def mark_to_market(self, price: float) -> None:
        """
        Update unrealized P&L at the given market price.

        Parameters
        ----------
        price:
            Current market price of the symbol.
        """
        self.market_price = price
        if abs(self.quantity) < 1e-9:
            self.unrealized_pnl = 0.0
        elif self.quantity > 0:
            self.unrealized_pnl = self.quantity * (price - self.avg_cost)
        else:
            self.unrealized_pnl = self.quantity * (price - self.avg_cost)

    def __repr__(self) -> str:
        return (
            f"Position({self.symbol}, {self.side}, qty={self.quantity:.2f}, "
            f"avg_cost={self.avg_cost:.4f}, mkt={self.market_price:.4f}, "
            f"upnl={self.unrealized_pnl:.2f})"
        )


# ---------------------------------------------------------------------------
# AccountInfo
# ---------------------------------------------------------------------------


@dataclass
class AccountInfo:
    """
    Snapshot of broker account state.

    Parameters
    ----------
    cash:
        Available cash balance (settled).
    equity:
        Total account equity (cash + positions market value).
    buying_power:
        Available buying power (may exceed cash for margin accounts).
    positions_value:
        Aggregate market value of all open positions.
    """

    cash: float
    equity: float
    buying_power: float
    positions_value: float

    @property
    def leverage(self) -> float:
        """Gross leverage = positions_value / equity.  0.0 if equity is zero."""
        return abs(self.positions_value) / self.equity if self.equity > 0 else 0.0

    def __repr__(self) -> str:
        return (
            f"AccountInfo(cash={self.cash:.2f}, equity={self.equity:.2f}, "
            f"buying_power={self.buying_power:.2f}, "
            f"positions_value={self.positions_value:.2f})"
        )


__all__ = [
    "OrderType",
    "OrderSide",
    "OrderStatus",
    "TimeInForce",
    "Order",
    "Fill",
    "Position",
    "AccountInfo",
]
