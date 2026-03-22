"""
quantify.execution.order_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Order lifecycle management: queuing, deduplication, risk checks, and
routing to a :class:`~quantify.execution.broker.base.Broker`.

The :class:`OrderManager` sits between strategy signals and the broker.
It enforces pre-trade risk checks, prevents duplicate orders, and maintains
a complete audit trail of every order in the system.

Responsibilities
----------------
1. **Deduplication** — one open order per (strategy, symbol) pair.
   A second order for the same pair is silently dropped unless the first
   is in a terminal state.
2. **Pre-trade risk checks** — pluggable validators (position size,
   buying-power, order-level limits).
3. **Routing** — submits validated orders to the configured broker.
4. **Lifecycle tracking** — keeps a full history of all orders and their
   state transitions.
5. **Fill distribution** — registers as the broker's fill callback and
   forwards fills to registered listeners (e.g. the portfolio).

Usage
-----
::

    broker = SimulatedBroker(initial_capital=100_000)
    portfolio = Portfolio(initial_capital=100_000)
    om = OrderManager(broker=broker)
    om.register_fill_listener(portfolio.update_from_fill)

    # Submit an order from a signal
    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        strategy_name="momentum",
    )
    om.submit(order)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from quantify.execution.broker.base import Broker, BrokerError
from quantify.execution.order import (
    AccountInfo,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Risk check result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskCheckResult:
    """
    Outcome of a pre-trade risk check.

    Parameters
    ----------
    passed:
        ``True`` if the order passed all checks.
    reason:
        Human-readable explanation when ``passed`` is ``False``.
    """

    passed: bool
    reason: str = ""

    @classmethod
    def ok(cls) -> "RiskCheckResult":
        """Return a passing result."""
        return cls(passed=True)

    @classmethod
    def fail(cls, reason: str) -> "RiskCheckResult":
        """Return a failing result with the given reason."""
        return cls(passed=False, reason=reason)


# ---------------------------------------------------------------------------
# OrderManager
# ---------------------------------------------------------------------------


class OrderManager:
    """
    Manages order lifecycle for all strategies.

    Parameters
    ----------
    broker:
        The :class:`~quantify.execution.broker.base.Broker` to route orders to.
    max_order_value:
        Maximum USD notional for a single order.  ``None`` disables this check.
    max_position_pct:
        Maximum allowed position as a fraction of account equity (0.0 – 1.0).
        ``None`` disables this check.
    """

    def __init__(
        self,
        broker: Broker,
        max_order_value: Optional[float] = None,
        max_position_pct: Optional[float] = 0.10,
    ) -> None:
        self._broker = broker
        self._max_order_value = max_order_value
        self._max_position_pct = max_position_pct

        # order_id → Order (complete history, including closed)
        self._orders: dict[str, Order] = {}
        # (strategy_name, symbol) → order_id  — only open orders
        self._open_order_index: dict[tuple[str, str], str] = {}
        # Fill listeners
        self._fill_listeners: list[Callable[[Fill], None]] = []

        # Register ourselves to receive fills from the broker
        broker.register_fill_callback(self._on_fill)

        log.info(
            "OrderManager initialised with broker=%r, max_order_value=%s, "
            "max_position_pct=%s",
            broker,
            max_order_value,
            max_position_pct,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, order: Order) -> Optional[str]:
        """
        Validate and submit an order to the broker.

        Steps:
        1. Check for duplicate open order (same strategy + symbol).
        2. Run pre-trade risk checks.
        3. Store the order.
        4. Call ``broker.submit_order``.

        Parameters
        ----------
        order:
            The order to submit.  Its ``id`` must be set.

        Returns
        -------
        str or None
            The order ID if the order was submitted successfully; ``None``
            if it was rejected (duplicate or risk check failure).
        """
        # --- Duplicate check ---
        key = (order.strategy_name, order.symbol)
        existing_id = self._open_order_index.get(key)
        if existing_id is not None:
            existing = self._orders.get(existing_id)
            if existing is not None and existing.is_open:
                log.warning(
                    "Duplicate order dropped: %s/%s already has open order %s",
                    order.strategy_name,
                    order.symbol,
                    existing_id[:8],
                )
                return None

        # --- Risk checks ---
        check = self._run_risk_checks(order)
        if not check.passed:
            order.status = OrderStatus.REJECTED
            order.notes = check.reason
            self._orders[order.id] = order
            log.warning(
                "Order %s rejected by risk check: %s", order.id[:8], check.reason
            )
            return None

        # --- Store and submit ---
        self._orders[order.id] = order
        self._open_order_index[key] = order.id

        try:
            broker_id = self._broker.submit_order(order)
            log.info("Order submitted: %r -> broker_id=%s", order, broker_id)
            return order.id
        except BrokerError as exc:
            order.status = OrderStatus.REJECTED
            order.notes = str(exc)
            self._open_order_index.pop(key, None)
            log.error("Broker submission failed for %s: %s", order.id[:8], exc)
            return None

    def cancel(self, order_id: str) -> bool:
        """
        Cancel an order by its internal ID.

        Parameters
        ----------
        order_id:
            Internal order ID.

        Returns
        -------
        bool
            ``True`` if the cancellation was accepted.
        """
        order = self._orders.get(order_id)
        if order is None:
            log.warning("cancel: unknown order_id %s", order_id)
            return False
        if order.is_closed:
            log.debug("cancel: order %s already closed", order_id[:8])
            return False

        success = self._broker.cancel_order(order_id)
        if success:
            order.status = OrderStatus.CANCELLED
            self._remove_from_open_index(order_id)
            log.info("Order cancelled: %s", order_id[:8])
        return success

    def cancel_all(self, strategy_name: Optional[str] = None) -> int:
        """
        Cancel all open orders, optionally filtered by strategy.

        Parameters
        ----------
        strategy_name:
            If provided, only cancel orders from this strategy.

        Returns
        -------
        int
            Number of successfully cancelled orders.
        """
        cancelled = 0
        targets = [
            oid
            for oid, o in self._orders.items()
            if o.is_open and (strategy_name is None or o.strategy_name == strategy_name)
        ]
        for oid in targets:
            if self.cancel(oid):
                cancelled += 1
        return cancelled

    def cancel_for_symbol(self, symbol: str, strategy_name: Optional[str] = None) -> int:
        """
        Cancel all open orders for a specific symbol.

        Parameters
        ----------
        symbol:
            Ticker symbol.
        strategy_name:
            Optional strategy filter.

        Returns
        -------
        int
            Number of successfully cancelled orders.
        """
        cancelled = 0
        targets = [
            oid
            for oid, o in self._orders.items()
            if o.is_open
            and o.symbol == symbol
            and (strategy_name is None or o.strategy_name == strategy_name)
        ]
        for oid in targets:
            if self.cancel(oid):
                cancelled += 1
        return cancelled

    def replace(self, order_id: str, new_order: Order) -> Optional[str]:
        """
        Cancel an existing order and submit a replacement.

        Parameters
        ----------
        order_id:
            ID of the order to replace.
        new_order:
            Replacement order.  Must have the same symbol and strategy.

        Returns
        -------
        str or None
            New order ID if successful.
        """
        order = self._orders.get(order_id)
        if order is None:
            log.warning("replace: unknown order_id %s", order_id)
            return None

        if new_order.symbol != order.symbol or new_order.strategy_name != order.strategy_name:
            log.error(
                "replace: symbol/strategy mismatch: existing=(%s/%s) new=(%s/%s)",
                order.strategy_name, order.symbol,
                new_order.strategy_name, new_order.symbol,
            )
            return None

        self.cancel(order_id)
        return self.submit(new_order)

    # ------------------------------------------------------------------
    # Fill callback
    # ------------------------------------------------------------------

    def _on_fill(self, fill: Fill) -> None:
        """
        Handle a fill from the broker.

        Updates the order state and forwards the fill to registered
        listeners.
        """
        order = self._orders.get(fill.order_id)
        if order is not None:
            if not order.is_closed:
                try:
                    order.apply_fill(fill)
                except ValueError as exc:
                    log.error("Failed to apply fill to order: %s — %s", fill, exc)
            if order.is_closed:
                self._remove_from_open_index(fill.order_id)
        else:
            log.warning("_on_fill: received fill for unknown order_id %s", fill.order_id)

        # Dispatch to external listeners
        for listener in self._fill_listeners:
            try:
                listener(fill)
            except Exception:  # noqa: BLE001
                log.exception("Fill listener raised an exception: %r", fill)

    # ------------------------------------------------------------------
    # Fill listener registration
    # ------------------------------------------------------------------

    def register_fill_listener(self, listener: Callable[[Fill], None]) -> None:
        """
        Register a callable to be invoked on every fill.

        Parameters
        ----------
        listener:
            A callable that accepts a :class:`~quantify.execution.order.Fill`.
        """
        self._fill_listeners.append(listener)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_order(self, order_id: str) -> Optional[Order]:
        """Return the order with the given ID, or ``None`` if unknown."""
        return self._orders.get(order_id)

    def get_open_orders(
        self, strategy_name: Optional[str] = None
    ) -> list[Order]:
        """
        Return all open orders.

        Parameters
        ----------
        strategy_name:
            Optional filter by strategy.
        """
        return [
            o
            for o in self._orders.values()
            if o.is_open and (strategy_name is None or o.strategy_name == strategy_name)
        ]

    def get_orders_for_symbol(
        self, symbol: str, strategy_name: Optional[str] = None
    ) -> list[Order]:
        """Return all orders (open and closed) for a given symbol."""
        return [
            o
            for o in self._orders.values()
            if o.symbol == symbol
            and (strategy_name is None or o.strategy_name == strategy_name)
        ]

    def has_open_order(self, symbol: str, strategy_name: str) -> bool:
        """Return ``True`` if there is an open order for this strategy/symbol pair."""
        key = (strategy_name, symbol)
        oid = self._open_order_index.get(key)
        if oid is None:
            return False
        order = self._orders.get(oid)
        return order is not None and order.is_open

    def order_count(self, status: Optional[OrderStatus] = None) -> int:
        """Count orders, optionally filtered by status."""
        if status is None:
            return len(self._orders)
        return sum(1 for o in self._orders.values() if o.status == status)

    def get_all_orders(self) -> list[Order]:
        """Return a list of all tracked orders (open + closed)."""
        return list(self._orders.values())

    # ------------------------------------------------------------------
    # Risk checks
    # ------------------------------------------------------------------

    def _run_risk_checks(self, order: Order) -> RiskCheckResult:
        """
        Run all configured pre-trade risk checks.

        Checks are short-circuit: the first failing check returns
        immediately.

        Parameters
        ----------
        order:
            The order to validate.

        Returns
        -------
        RiskCheckResult
        """
        # --- Basic validation ---
        if order.quantity <= 0:
            return RiskCheckResult.fail(f"Quantity must be positive, got {order.quantity}")

        # --- Max order value ---
        if self._max_order_value is not None:
            reference_price = (
                order.limit_price
                or order.stop_price
                or 0.0
            )
            if reference_price > 0:
                estimated_value = order.quantity * reference_price
                if estimated_value > self._max_order_value:
                    return RiskCheckResult.fail(
                        f"Order notional {estimated_value:.2f} exceeds "
                        f"max_order_value {self._max_order_value:.2f}"
                    )

        # --- Max position size as fraction of equity ---
        if self._max_position_pct is not None:
            try:
                account = self._broker.get_account()
                equity = account.equity
                if equity > 0:
                    reference_price = order.limit_price or order.stop_price
                    if reference_price is not None:
                        proposed_value = order.quantity * reference_price
                        if proposed_value / equity > self._max_position_pct:
                            return RiskCheckResult.fail(
                                f"Proposed order value {proposed_value:.2f} "
                                f"({100*proposed_value/equity:.1f}% of equity) exceeds "
                                f"max_position_pct {100*self._max_position_pct:.1f}%"
                            )
            except Exception:  # noqa: BLE001
                # Don't block the order if we can't fetch account info
                log.warning("Could not fetch account info for risk check; skipping pct check")

        return RiskCheckResult.ok()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove_from_open_index(self, order_id: str) -> None:
        """Remove an order from the open-order index if it's in there."""
        order = self._orders.get(order_id)
        if order is not None:
            key = (order.strategy_name, order.symbol)
            if self._open_order_index.get(key) == order_id:
                del self._open_order_index[key]

    def __repr__(self) -> str:
        open_count = len([o for o in self._orders.values() if o.is_open])
        total = len(self._orders)
        return (
            f"OrderManager(broker={self._broker!r}, "
            f"open_orders={open_count}/{total})"
        )


__all__ = ["OrderManager", "RiskCheckResult"]
