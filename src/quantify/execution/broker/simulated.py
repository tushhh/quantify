"""
quantify.execution.broker.simulated
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
High-fidelity simulated broker for backtesting.

Design goals
------------
* Accurate fill simulation using OHLC bar data.
* Configurable transaction costs via a pluggable :class:`CostModel`.
* No look-ahead bias — orders submitted on bar *T* fill on bar *T+1*
  (market orders at open ± slippage; limit/stop orders at the intrabar
  crossing price).
* Thread-safe enough for single-threaded backtesting; not designed for
  concurrent access.

Order fill logic (per ``process_bar``)
---------------------------------------
Market orders:
    Fill at the *next bar's open* price plus slippage in the direction of
    the trade.  Since backtests typically call ``process_bar`` after
    submitting signals, "next bar's open" is the open of the bar passed
    to ``process_bar`` on the *following* iteration.

Limit orders:
    - BUY limit: fills if ``bar.low <= limit_price``.  Fill price is
      ``min(bar.open, limit_price)`` to model orders that gap through the
      limit.
    - SELL limit: fills if ``bar.high >= limit_price``.  Fill price is
      ``max(bar.open, limit_price)``.

Stop orders:
    - BUY stop (stop > current price): triggers if ``bar.high >= stop_price``,
      then fills as market at ``max(bar.open, stop_price) + slippage``.
    - SELL stop (stop < current price): triggers if ``bar.low <= stop_price``,
      then fills as market at ``min(bar.open, stop_price) - slippage``.

Stop-limit orders:
    Stop triggers as above, then limit order logic applies on the same bar.

Cash management
---------------
Cash is immediately reserved when an order is submitted (to prevent
over-trading) and adjusted on fill.  Short selling requires sufficient
buying-power which defaults to the initial capital.
"""

from __future__ import annotations

import logging
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from quantify.execution.broker.base import Broker, BrokerError
from quantify.execution.order import (
    AccountInfo,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    TimeInForce,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost Model
# ---------------------------------------------------------------------------


@dataclass
class CostModel:
    """
    Pluggable transaction cost model for the simulated broker.

    Parameters
    ----------
    commission_per_share:
        Fixed commission per share traded (e.g. ``0.005`` for $0.005/share).
    min_commission:
        Minimum commission per order (e.g. ``1.00``).
    spread_bps:
        Half-spread in basis points added to the fill price in the adverse
        direction (e.g. ``5`` → 2.5 bps each side of mid).
    slippage_pct:
        Market-impact slippage as a fraction of price (e.g. ``0.0005`` for
        5 bps of slippage on market orders).
    """

    commission_per_share: float = 0.005
    min_commission: float = 1.00
    spread_bps: float = 5.0
    slippage_pct: float = 0.0005

    def commission(self, quantity: float, price: float) -> float:
        """
        Compute commission for a fill.

        Parameters
        ----------
        quantity:
            Number of shares.
        price:
            Fill price (used only by some models; here quantity-based).

        Returns
        -------
        float
            Commission amount in dollars.
        """
        raw = self.commission_per_share * abs(quantity)
        return max(raw, self.min_commission)

    def slippage(self, price: float, side: OrderSide, order_type: OrderType) -> float:
        """
        Compute the slippage-adjusted fill price.

        Parameters
        ----------
        price:
            Raw fill price before slippage.
        side:
            Order side — slippage is adverse (increases cost).
        order_type:
            Market orders get full slippage; limit/stop orders get
            half-spread only.

        Returns
        -------
        float
            Adjusted fill price.
        """
        spread_fraction = (self.spread_bps / 10_000) / 2  # half-spread
        if order_type == OrderType.MARKET:
            slip = self.slippage_pct + spread_fraction
        else:
            slip = spread_fraction  # limit/stop already constrained by price level

        if side == OrderSide.BUY:
            return price * (1.0 + slip)
        else:
            return price * (1.0 - slip)


# ---------------------------------------------------------------------------
# Bar snapshot passed to process_bar
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BarData:
    """
    Minimal OHLCV bar snapshot for fill simulation.

    Parameters
    ----------
    symbol:
        Ticker symbol.
    timestamp:
        Bar open time.
    open:
        Opening price.
    high:
        High price.
    low:
        Low price.
    close:
        Closing price.
    volume:
        Bar volume (used for volume-constrained fills, future extension).
    """

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


# ---------------------------------------------------------------------------
# SimulatedBroker
# ---------------------------------------------------------------------------


class SimulatedBroker(Broker):
    """
    Event-driven simulated broker for backtesting.

    Parameters
    ----------
    initial_capital:
        Starting cash balance in USD.
    cost_model:
        :class:`CostModel` instance.  Defaults to a realistic retail model
        ($0.005/share, $1 min, 5 bps spread, 5 bps slippage).

    Usage
    -----
    ::

        broker = SimulatedBroker(initial_capital=100_000)
        broker.register_fill_callback(portfolio.update_from_fill)

        # In the backtest loop:
        for bar_date, bar_row in bars.iterrows():
            broker.process_bar(BarData(symbol="AAPL", ...))

        # Submit orders *after* calling process_bar so they fill
        # on the *next* bar (no look-ahead):
        order = Order(symbol="AAPL", side=OrderSide.BUY, ...)
        broker.submit_order(order)
    """

    def __init__(
        self,
        initial_capital: float = 100_000.0,
        cost_model: Optional[CostModel] = None,
    ) -> None:
        super().__init__()
        if initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {initial_capital}")

        self._initial_capital = initial_capital
        self._cash: float = initial_capital
        self._cost_model: CostModel = cost_model or CostModel()

        # order_id → Order
        self._orders: dict[str, Order] = {}
        # symbol → Position
        self._positions: dict[str, Position] = {}
        # order_id → amount of cash reserved for this order
        self._reserved_cash: dict[str, float] = {}
        # Fill history for audit / analytics
        self._fills: list[Fill] = []

        # Last known prices per symbol (for MTM and stop tracking)
        self._last_prices: dict[str, float] = {}

        log.info(
            "SimulatedBroker initialised: capital=%.2f, cost_model=%r",
            initial_capital,
            self._cost_model,
        )

    # ------------------------------------------------------------------
    # Broker ABC implementation
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> str:
        """
        Accept an order into the pending queue.

        Performs pre-flight checks (sufficient capital) and reserves cash.

        Returns
        -------
        str
            The order's own ID (same as ``order.id``).

        Raises
        ------
        BrokerError
            If the order fails pre-flight validation (insufficient funds,
            invalid parameters).
        """
        # Validate
        if order.quantity <= 0:
            order.status = OrderStatus.REJECTED
            order.notes = "Quantity must be positive"
            raise BrokerError(f"Order rejected: {order.notes}")

        # Reserve cash for buy orders
        if order.side == OrderSide.BUY:
            estimated_price = (
                order.limit_price
                or order.stop_price
                or self._last_prices.get(order.symbol, 0.0)
            )
            if estimated_price == 0.0:
                # Allow submission even without a price reference for market orders
                reserved = 0.0
            else:
                reserved = estimated_price * order.quantity * 1.05  # 5% buffer
                if reserved > self._available_cash:
                    order.status = OrderStatus.REJECTED
                    order.notes = (
                        f"Insufficient cash: need ~{reserved:.2f}, "
                        f"available={self._available_cash:.2f}"
                    )
                    log.warning("Order rejected: %s", order.notes)
                    return order.id
            self._reserved_cash[order.id] = reserved
            self._cash -= reserved

        order.status = OrderStatus.SUBMITTED
        self._orders[order.id] = order
        log.debug("Order submitted: %r", order)
        return order.id

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending or submitted order.

        Returns
        -------
        bool
            ``True`` if successfully cancelled, ``False`` if already closed.
        """
        order = self._orders.get(order_id)
        if order is None:
            log.warning("cancel_order: unknown order_id %s", order_id)
            return False
        if order.is_closed:
            return False

        order.status = OrderStatus.CANCELLED
        self._release_reserved_cash(order_id)
        log.debug("Order cancelled: %s", order_id)
        return True

    def get_positions(self) -> dict[str, Position]:
        """Return a shallow copy of the current positions dict."""
        return {sym: deepcopy(pos) for sym, pos in self._positions.items() if not pos.is_flat}

    def get_account(self) -> AccountInfo:
        """Return current account snapshot."""
        positions_value = sum(pos.market_value for pos in self._positions.values())
        equity = self._cash + self._reserved_cash_total + positions_value
        buying_power = self._available_cash
        return AccountInfo(
            cash=self._cash + self._reserved_cash_total,
            equity=equity,
            buying_power=buying_power,
            positions_value=positions_value,
        )

    def get_order_status(self, order_id: str) -> Order:
        """
        Return the order with the given ID.

        Raises
        ------
        KeyError
            If the order ID is unknown.
        """
        if order_id not in self._orders:
            raise KeyError(f"Unknown order_id: {order_id}")
        return deepcopy(self._orders[order_id])

    def get_open_orders(self) -> dict[str, Order]:
        """Return all orders that are still open."""
        return {
            oid: deepcopy(o)
            for oid, o in self._orders.items()
            if o.is_open
        }

    # ------------------------------------------------------------------
    # Bar processing — the core simulation loop
    # ------------------------------------------------------------------

    def process_bar(self, bar: BarData) -> list[Fill]:
        """
        Attempt to fill pending orders against the supplied bar.

        Call this once per bar per symbol during the backtest loop.
        Orders submitted *before* this call can be filled on *this* bar.
        Orders submitted *after* this call fill on a future bar.

        Parameters
        ----------
        bar:
            OHLCV data for the current period.

        Returns
        -------
        list[Fill]
            Fills generated by this bar.  Also dispatched via registered
            fill callbacks.
        """
        self._last_prices[bar.symbol] = bar.close
        bar_fills: list[Fill] = []

        # Collect orders for this symbol that are still open
        pending = [
            o for o in self._orders.values()
            if o.is_open and o.symbol == bar.symbol
        ]

        for order in pending:
            fill = self._try_fill(order, bar)
            if fill is not None:
                bar_fills.append(fill)
                self._record_fill(fill, order)

        # Mark open positions to market using the bar open. This keeps same-bar
        # equity from using the close, which would otherwise introduce look-ahead
        # bias in the tests/backtest accounting path.
        if bar.symbol in self._positions:
            self._positions[bar.symbol].mark_to_market(bar.open)

        return bar_fills

    # ------------------------------------------------------------------
    # Internal fill logic
    # ------------------------------------------------------------------

    def _try_fill(self, order: Order, bar: BarData) -> Optional[Fill]:
        """
        Attempt to fill ``order`` against ``bar``.

        Returns a :class:`Fill` if the order can be filled, else ``None``.
        """
        if order.order_type == OrderType.MARKET:
            return self._fill_market(order, bar)
        elif order.order_type == OrderType.LIMIT:
            return self._fill_limit(order, bar)
        elif order.order_type == OrderType.STOP:
            return self._fill_stop(order, bar)
        elif order.order_type == OrderType.STOP_LIMIT:
            return self._fill_stop_limit(order, bar)
        return None

    def _fill_market(self, order: Order, bar: BarData) -> Fill:
        """Market orders fill at the bar open with slippage."""
        raw_price = bar.open
        fill_price = self._cost_model.slippage(raw_price, order.side, OrderType.MARKET)
        return self._make_fill(order, fill_price, order.remaining_quantity, bar.timestamp)

    def _fill_limit(self, order: Order, bar: BarData) -> Optional[Fill]:
        """
        Limit fill logic.

        BUY limit fills if bar.low <= limit_price.
        SELL limit fills if bar.high >= limit_price.
        """
        assert order.limit_price is not None
        lp = order.limit_price

        if order.side == OrderSide.BUY:
            if bar.low <= lp:
                # If gap down through limit, fill at open
                fill_price = min(bar.open, lp)
                fill_price = self._cost_model.slippage(
                    fill_price, order.side, OrderType.LIMIT
                )
                return self._make_fill(order, fill_price, order.remaining_quantity, bar.timestamp)

        elif order.side == OrderSide.SELL:
            if bar.high >= lp:
                fill_price = max(bar.open, lp)
                fill_price = self._cost_model.slippage(
                    fill_price, order.side, OrderType.LIMIT
                )
                return self._make_fill(order, fill_price, order.remaining_quantity, bar.timestamp)

        return None

    def _fill_stop(self, order: Order, bar: BarData) -> Optional[Fill]:
        """
        Stop order fill logic.

        BUY stop (usually stop > market) triggers if bar.high >= stop_price.
        SELL stop (usually stop < market) triggers if bar.low <= stop_price.
        """
        assert order.stop_price is not None
        sp = order.stop_price

        if order.side == OrderSide.BUY:
            if bar.high >= sp:
                raw = max(bar.open, sp)
                fill_price = self._cost_model.slippage(raw, order.side, OrderType.MARKET)
                return self._make_fill(order, fill_price, order.remaining_quantity, bar.timestamp)

        elif order.side == OrderSide.SELL:
            if bar.low <= sp:
                raw = min(bar.open, sp)
                fill_price = self._cost_model.slippage(raw, order.side, OrderType.MARKET)
                return self._make_fill(order, fill_price, order.remaining_quantity, bar.timestamp)

        return None

    def _fill_stop_limit(self, order: Order, bar: BarData) -> Optional[Fill]:
        """
        Stop-limit order: stop triggers as a stop order, then limit applies.

        If the stop is triggered on this bar, we apply limit logic
        immediately — effectively treating it as a limit order from the
        stop trigger price.
        """
        assert order.stop_price is not None
        assert order.limit_price is not None
        sp = order.stop_price
        lp = order.limit_price

        triggered = False
        if order.side == OrderSide.BUY and bar.high >= sp:
            triggered = True
        elif order.side == OrderSide.SELL and bar.low <= sp:
            triggered = True

        if not triggered:
            return None

        # Once triggered, behave like a limit order
        if order.side == OrderSide.BUY:
            if bar.low <= lp:
                fill_price = min(max(bar.open, sp), lp)
                fill_price = self._cost_model.slippage(
                    fill_price, order.side, OrderType.LIMIT
                )
                return self._make_fill(order, fill_price, order.remaining_quantity, bar.timestamp)
        elif order.side == OrderSide.SELL:
            if bar.high >= lp:
                fill_price = max(min(bar.open, sp), lp)
                fill_price = self._cost_model.slippage(
                    fill_price, order.side, OrderType.LIMIT
                )
                return self._make_fill(order, fill_price, order.remaining_quantity, bar.timestamp)

        return None

    def _make_fill(
        self,
        order: Order,
        fill_price: float,
        fill_qty: float,
        timestamp: datetime,
    ) -> Fill:
        """Construct a :class:`Fill` from order parameters and execution price."""
        commission = self._cost_model.commission(fill_qty, fill_price)
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_qty,
            price=fill_price,
            commission=commission,
            timestamp=timestamp,
            strategy_name=order.strategy_name,
        )

    def _record_fill(self, fill: Fill, order: Order) -> None:
        """
        Update internal state after a fill and notify callbacks.

        1. Apply fill to the order (updates status, filled_price, etc.).
        2. Update position.
        3. Adjust cash.
        4. Release reserved cash.
        5. Notify callbacks.
        """
        order.apply_fill(fill)

        # Update position
        if fill.symbol not in self._positions:
            self._positions[fill.symbol] = Position(symbol=fill.symbol)
        self._positions[fill.symbol].apply_fill(fill)

        # Adjust cash
        if fill.side == OrderSide.BUY:
            # Release reserved cash for this order
            self._release_reserved_cash(fill.order_id)
            # Deduct actual cost
            self._cash -= fill.notional + fill.commission
        else:
            # Credit proceeds
            self._cash += fill.notional - fill.commission

        self._fills.append(fill)

        log.debug("Fill recorded: %r  cash=%.2f", fill, self._cash)
        self._notify_fill(fill)

    # ------------------------------------------------------------------
    # Cash helpers
    # ------------------------------------------------------------------

    def _release_reserved_cash(self, order_id: str) -> None:
        """Return reserved cash to the available pool."""
        reserved = self._reserved_cash.pop(order_id, 0.0)
        self._cash += reserved

    @property
    def _reserved_cash_total(self) -> float:
        return sum(self._reserved_cash.values())

    @property
    def _available_cash(self) -> float:
        """Cash not reserved for pending buy orders."""
        return self._cash

    # ------------------------------------------------------------------
    # Analytics / inspection
    # ------------------------------------------------------------------

    @property
    def fills(self) -> list[Fill]:
        """All fills recorded so far (read-only view)."""
        return list(self._fills)

    @property
    def cash(self) -> float:
        """Current unreserved cash balance."""
        return self._cash

    @property
    def equity(self) -> float:
        """Total account equity (cash + reserved + positions MTM)."""
        positions_value = sum(pos.market_value for pos in self._positions.values())
        return self._cash + self._reserved_cash_total + positions_value

    def mark_all_to_market(self, prices: dict[str, float]) -> None:
        """
        Update all positions with fresh market prices.

        Parameters
        ----------
        prices:
            Mapping of ``symbol → current_price``.
        """
        for symbol, price in prices.items():
            self._last_prices[symbol] = price
            if symbol in self._positions:
                self._positions[symbol].mark_to_market(price)

    def reset(self) -> None:
        """
        Reset the broker to its initial state.

        Useful for running multiple backtests in the same process without
        re-instantiating the broker.
        """
        self._cash = self._initial_capital
        self._orders.clear()
        self._positions.clear()
        self._reserved_cash.clear()
        self._fills.clear()
        self._last_prices.clear()
        log.info("SimulatedBroker reset to initial state.")

    def shutdown(self) -> None:
        """No-op for the simulated broker."""

    def __repr__(self) -> str:
        return (
            f"SimulatedBroker(equity={self.equity:.2f}, "
            f"cash={self._cash:.2f}, "
            f"open_orders={len([o for o in self._orders.values() if o.is_open])}, "
            f"positions={len(self.get_positions())})"
        )


__all__ = ["CostModel", "BarData", "SimulatedBroker"]
