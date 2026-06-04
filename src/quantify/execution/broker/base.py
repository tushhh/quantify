"""
quantify.execution.broker.base
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Abstract broker interface that all concrete broker adapters must implement.

The :class:`Broker` ABC provides a uniform API so that strategies and the
order manager are completely decoupled from the underlying execution venue.
Swapping from :class:`~quantify.execution.broker.simulated.SimulatedBroker`
(backtesting) to
:class:`~quantify.execution.broker.alpaca_broker.AlpacaBroker`
(paper/live trading) requires no changes to higher-level code.

Thread safety
-------------
Concrete implementations are responsible for their own thread safety.  The
:class:`~quantify.execution.order_manager.OrderManager` will call broker
methods from a single thread by default, but live brokers may receive
asynchronous fill callbacks.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable

from quantify.execution.order import AccountInfo, Fill, Order, Position

log = logging.getLogger(__name__)


class Broker(ABC):
    """
    Abstract interface for order execution venues.

    All broker adapters (simulated, Alpaca, Interactive Brokers, etc.) must
    implement this interface.  The methods map closely to the FIX protocol
    primitives to keep adapters straightforward.

    Fill callbacks
    --------------
    Register a callable with :meth:`register_fill_callback` to receive
    :class:`~quantify.execution.order.Fill` events as they arrive.
    Simulated brokers invoke the callback synchronously inside
    :meth:`process_bar`; live brokers invoke it from their WebSocket
    thread.
    """

    def __init__(self) -> None:
        self._fill_callbacks: list[Callable[[Fill], None]] = []

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """
        Submit an order to the venue and return the broker-assigned order ID.

        The order's ``status`` field should be updated to ``SUBMITTED`` (or
        ``REJECTED``) upon return.

        Parameters
        ----------
        order:
            The :class:`~quantify.execution.order.Order` to submit.  The
            order's ``id`` field is set by the caller; the broker may use
            its own internal ID but must also store the mapping.

        Returns
        -------
        str
            The broker's native order identifier.  For the simulated broker
            this is the same as ``order.id``.

        Raises
        ------
        BrokerError
            If the submission fails for a non-rejection reason (e.g. network
            error, authentication failure).
        """
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Request cancellation of an open order.

        Parameters
        ----------
        order_id:
            The internal order ID (as stored in ``Order.id``).

        Returns
        -------
        bool
            ``True`` if the cancellation was accepted, ``False`` if the
            order was already filled or in a terminal state.
        """
        ...

    @abstractmethod
    def get_positions(self) -> dict[str, Position]:
        """
        Return all current open positions keyed by symbol.

        Returns
        -------
        dict[str, Position]
            Empty dict if there are no open positions.
        """
        ...

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """
        Return a snapshot of account balances.

        Returns
        -------
        AccountInfo
        """
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> Order:
        """
        Fetch the current state of an order.

        Parameters
        ----------
        order_id:
            Internal order ID.

        Returns
        -------
        Order
            The order object with the most recent status.

        Raises
        ------
        KeyError
            If the order is unknown to this broker instance.
        """
        ...

    # ------------------------------------------------------------------
    # Optional methods with sensible defaults
    # ------------------------------------------------------------------

    def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.

        Default implementation fetches open orders via :meth:`get_open_orders`
        and calls :meth:`cancel_order` on each.

        Returns
        -------
        int
            Number of cancellations accepted.
        """
        cancelled = 0
        for order in self.get_open_orders().values():
            if self.cancel_order(order.id):
                cancelled += 1
        return cancelled

    def get_open_orders(self) -> dict[str, Order]:
        """
        Return all orders that are still open (PENDING, SUBMITTED, PARTIAL).

        Default implementation returns an empty dict.  Concrete classes
        should override this to return live pending orders.

        Returns
        -------
        dict[str, Order]
            Mapping of ``order_id → Order``.
        """
        return {}

    # ------------------------------------------------------------------
    # Fill callback registration
    # ------------------------------------------------------------------

    def register_fill_callback(self, callback: Callable[[Fill], None]) -> None:
        """
        Register a callable to be invoked on every fill event.

        Parameters
        ----------
        callback:
            A callable that accepts a single :class:`Fill` argument.
            Multiple callbacks can be registered; they are called in
            registration order.
        """
        self._fill_callbacks.append(callback)

    def _notify_fill(self, fill: Fill) -> None:
        """
        Dispatch a fill to all registered callbacks.

        Should be called by concrete implementations whenever a fill is
        generated.

        Parameters
        ----------
        fill:
            The fill to broadcast.
        """
        for cb in self._fill_callbacks:
            try:
                cb(fill)
            except Exception:  # noqa: BLE001
                log.exception("Fill callback raised an exception: %r", fill)

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "Broker":
        return self

    def __exit__(self, *_: object) -> None:
        """Called when exiting a ``with`` block.  Override to close connections."""
        self.shutdown()

    def shutdown(self) -> None:
        """
        Clean up broker resources (connections, threads, etc.).

        Default implementation does nothing.  Live broker adapters should
        override to close WebSocket connections and cancel background threads.
        """


class BrokerError(Exception):
    """Raised when a broker operation fails for infrastructure reasons."""


__all__ = ["Broker", "BrokerError"]
