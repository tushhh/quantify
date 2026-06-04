"""
quantify.execution.broker.alpaca_broker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Alpaca broker adapter for paper and live trading.

Uses the official ``alpaca-py`` SDK (``alpaca.trading``) and reads
credentials from environment variables:

    ALPACA_API_KEY      — required
    ALPACA_SECRET_KEY   — required
    ALPACA_PAPER        — optional, "true"/"false", defaults to "true"

Paper trading uses ``paper-api.alpaca.markets``; live trading uses
``api.alpaca.markets``.

Thread safety
-------------
``alpaca-py``'s ``TradingClient`` is stateless and thread-safe for concurrent
REST calls.  The WebSocket stream (``TradingStream``) runs in a background
thread; fills are dispatched to registered callbacks from that thread.
Callers should ensure their callbacks are thread-safe.

Dependencies
------------
::

    pip install alpaca-py

Type conversions
----------------
Internal :class:`~quantify.execution.order.Order` objects use our enums.
This module converts between them and Alpaca's enumerations / classes.
"""

from __future__ import annotations

import logging
import os
import threading
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
# Lazy SDK imports — avoids hard dependency at import time if alpaca-py is
# not installed (allows the rest of the system to work without it).
# ---------------------------------------------------------------------------

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import (
        OrderSide as AlpacaOrderSide,
        OrderStatus as AlpacaOrderStatus,
        OrderType as AlpacaOrderType,
        TimeInForce as AlpacaTimeInForce,
        PositionSide,
    )
    from alpaca.trading.models import (
        Order as AlpacaOrder,
        Position as AlpacaPosition,
        TradeAccount,
    )
    from alpaca.trading.requests import (
        LimitOrderRequest,
        MarketOrderRequest,
        StopLimitOrderRequest,
        StopOrderRequest,
    )
    from alpaca.trading.stream import TradingStream

    _ALPACA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ALPACA_AVAILABLE = False
    log.warning(
        "alpaca-py not installed.  AlpacaBroker will raise ImportError on use. "
        "Install with: pip install alpaca-py"
    )


def _require_alpaca() -> None:
    """Raise ImportError if alpaca-py is not installed."""
    if not _ALPACA_AVAILABLE:
        raise ImportError(
            "alpaca-py is required for AlpacaBroker.  "
            "Install with: pip install alpaca-py"
        )


# ---------------------------------------------------------------------------
# Enum conversion helpers
# ---------------------------------------------------------------------------


def _to_alpaca_side(side: OrderSide) -> "AlpacaOrderSide":
    _require_alpaca()
    return (
        AlpacaOrderSide.BUY if side == OrderSide.BUY else AlpacaOrderSide.SELL
    )


def _from_alpaca_side(side: "AlpacaOrderSide") -> OrderSide:
    return OrderSide.BUY if side == AlpacaOrderSide.BUY else OrderSide.SELL


def _to_alpaca_tif(tif: TimeInForce) -> "AlpacaTimeInForce":
    _require_alpaca()
    mapping = {
        TimeInForce.DAY: AlpacaTimeInForce.DAY,
        TimeInForce.GTC: AlpacaTimeInForce.GTC,
        TimeInForce.IOC: AlpacaTimeInForce.IOC,
        TimeInForce.FOK: AlpacaTimeInForce.FOK,
        TimeInForce.OPG: AlpacaTimeInForce.OPG,
        TimeInForce.CLS: AlpacaTimeInForce.CLS,
    }
    return mapping.get(tif, AlpacaTimeInForce.DAY)


def _from_alpaca_status(status: "AlpacaOrderStatus") -> OrderStatus:
    mapping = {
        AlpacaOrderStatus.NEW: OrderStatus.SUBMITTED,
        AlpacaOrderStatus.ACCEPTED: OrderStatus.SUBMITTED,
        AlpacaOrderStatus.PENDING_NEW: OrderStatus.PENDING,
        AlpacaOrderStatus.PARTIALLY_FILLED: OrderStatus.PARTIAL,
        AlpacaOrderStatus.FILLED: OrderStatus.FILLED,
        AlpacaOrderStatus.CANCELED: OrderStatus.CANCELLED,
        AlpacaOrderStatus.EXPIRED: OrderStatus.CANCELLED,
        AlpacaOrderStatus.REJECTED: OrderStatus.REJECTED,
        AlpacaOrderStatus.HELD: OrderStatus.SUBMITTED,
        AlpacaOrderStatus.ACCEPTED_FOR_BIDDING: OrderStatus.SUBMITTED,
        AlpacaOrderStatus.STOPPED: OrderStatus.CANCELLED,
        AlpacaOrderStatus.SUSPENDED: OrderStatus.CANCELLED,
        AlpacaOrderStatus.CALCULATED: OrderStatus.SUBMITTED,
        AlpacaOrderStatus.REPLACED: OrderStatus.CANCELLED,
        AlpacaOrderStatus.PENDING_REPLACE: OrderStatus.SUBMITTED,
        AlpacaOrderStatus.PENDING_CANCEL: OrderStatus.SUBMITTED,
        AlpacaOrderStatus.DONE_FOR_DAY: OrderStatus.CANCELLED,
    }
    return mapping.get(status, OrderStatus.SUBMITTED)


def _alpaca_order_to_internal(alpaca_order: "AlpacaOrder", strategy_name: str = "") -> Order:
    """Convert an Alpaca order object to our internal :class:`Order`."""
    side = _from_alpaca_side(alpaca_order.side)

    # Determine order type
    alpaca_type = alpaca_order.order_type
    if alpaca_type == AlpacaOrderType.MARKET:
        order_type = OrderType.MARKET
    elif alpaca_type == AlpacaOrderType.LIMIT:
        order_type = OrderType.LIMIT
    elif alpaca_type == AlpacaOrderType.STOP:
        order_type = OrderType.STOP
    elif alpaca_type == AlpacaOrderType.STOP_LIMIT:
        order_type = OrderType.STOP_LIMIT
    else:
        order_type = OrderType.MARKET

    qty = float(alpaca_order.qty or alpaca_order.notional or 0)

    order = Order(
        symbol=alpaca_order.symbol,
        side=side,
        order_type=order_type,
        quantity=qty,
        strategy_name=strategy_name,
        limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
        stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
        id=str(alpaca_order.id),
        created_at=alpaca_order.created_at,
    )

    order.status = _from_alpaca_status(alpaca_order.status)
    order.filled_quantity = float(alpaca_order.filled_qty or 0)
    if alpaca_order.filled_avg_price:
        order.filled_price = float(alpaca_order.filled_avg_price)
    if alpaca_order.filled_at:
        order.filled_at = alpaca_order.filled_at

    return order


def _alpaca_position_to_internal(ap: "AlpacaPosition") -> Position:
    """Convert an Alpaca position to our internal :class:`Position`."""
    qty = float(ap.qty)
    if ap.side == PositionSide.SHORT:
        qty = -abs(qty)

    pos = Position(
        symbol=ap.symbol,
        quantity=qty,
        avg_cost=float(ap.avg_entry_price),
        market_price=float(ap.current_price),
        unrealized_pnl=float(ap.unrealized_pl),
    )
    return pos


# ---------------------------------------------------------------------------
# AlpacaBroker
# ---------------------------------------------------------------------------


class AlpacaBroker(Broker):
    """
    Broker adapter for Alpaca paper and live trading.

    Parameters
    ----------
    paper:
        If ``True`` (default), connects to the Alpaca paper trading API.
        Set to ``False`` for live trading — use with extreme caution.
    api_key:
        Alpaca API key.  Defaults to the ``ALPACA_API_KEY`` environment
        variable.
    secret_key:
        Alpaca secret key.  Defaults to the ``ALPACA_SECRET_KEY``
        environment variable.
    enable_stream:
        If ``True``, start a WebSocket stream for real-time fill
        notifications.  Defaults to ``False`` — callers can poll via
        :meth:`get_order_status` instead.

    Raises
    ------
    ImportError
        If ``alpaca-py`` is not installed.
    ValueError
        If API credentials are not provided.
    """

    def __init__(
        self,
        paper: bool = True,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        enable_stream: bool = False,
    ) -> None:
        _require_alpaca()
        super().__init__()

        _api_key = api_key or os.environ.get("ALPACA_API_KEY", "")
        _secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY", "")

        if not _api_key or not _secret_key:
            raise ValueError(
                "Alpaca API credentials are required.  Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass them explicitly."
            )

        self._paper = paper
        self._client = TradingClient(
            api_key=_api_key,
            secret_key=_secret_key,
            paper=paper,
        )

        # Internal cache: internal_order_id → alpaca_order_id mapping
        self._order_id_map: dict[str, str] = {}
        # Internal cache: internal_order_id → strategy_name
        self._order_strategy_map: dict[str, str] = {}

        # WebSocket stream (optional)
        self._stream: Optional["TradingStream"] = None
        self._stream_thread: Optional[threading.Thread] = None
        if enable_stream:
            self._start_stream(_api_key, _secret_key)

        mode = "paper" if paper else "LIVE"
        log.info("AlpacaBroker connected (%s mode)", mode)

    # ------------------------------------------------------------------
    # Broker ABC implementation
    # ------------------------------------------------------------------

    def submit_order(self, order: Order) -> str:
        """
        Submit an order to Alpaca.

        Returns
        -------
        str
            The internal order ID (``order.id``).
        """
        _require_alpaca()
        try:
            request = self._build_alpaca_request(order)
            alpaca_order = self._client.submit_order(order_data=request)

            alpaca_id = str(alpaca_order.id)
            self._order_id_map[order.id] = alpaca_id
            self._order_strategy_map[order.id] = order.strategy_name

            order.status = _from_alpaca_status(alpaca_order.status)
            log.info(
                "Order submitted to Alpaca: internal=%s alpaca=%s %s",
                order.id[:8],
                alpaca_id[:8],
                order,
            )
            return order.id

        except Exception as exc:
            order.status = OrderStatus.REJECTED
            order.notes = str(exc)
            log.error("Order submission failed: %s — %s", order, exc)
            raise BrokerError(f"Alpaca order submission failed: {exc}") from exc

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order on Alpaca.

        Returns
        -------
        bool
            ``True`` if the cancellation was accepted.
        """
        _require_alpaca()
        alpaca_id = self._order_id_map.get(order_id)
        if alpaca_id is None:
            log.warning("cancel_order: no Alpaca ID for internal ID %s", order_id)
            return False
        try:
            self._client.cancel_order_by_id(alpaca_id)
            log.info("Order cancelled on Alpaca: internal=%s", order_id[:8])
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("cancel_order failed for %s: %s", order_id[:8], exc)
            return False

    def get_positions(self) -> dict[str, Position]:
        """Fetch all open positions from Alpaca."""
        _require_alpaca()
        try:
            alpaca_positions = self._client.get_all_positions()
            return {
                ap.symbol: _alpaca_position_to_internal(ap)
                for ap in alpaca_positions
            }
        except Exception as exc:
            log.error("get_positions failed: %s", exc)
            raise BrokerError(f"Failed to fetch positions: {exc}") from exc

    def get_account(self) -> AccountInfo:
        """Fetch account balances from Alpaca."""
        _require_alpaca()
        try:
            acct: "TradeAccount" = self._client.get_account()
            return AccountInfo(
                cash=float(acct.cash),
                equity=float(acct.equity),
                buying_power=float(acct.buying_power),
                positions_value=float(acct.long_market_value) - float(acct.short_market_value),
            )
        except Exception as exc:
            log.error("get_account failed: %s", exc)
            raise BrokerError(f"Failed to fetch account: {exc}") from exc

    def get_order_status(self, order_id: str) -> Order:
        """Fetch the current state of an order from Alpaca."""
        _require_alpaca()
        alpaca_id = self._order_id_map.get(order_id)
        if alpaca_id is None:
            raise KeyError(f"Unknown order_id: {order_id}")
        try:
            alpaca_order = self._client.get_order_by_id(alpaca_id)
            strategy = self._order_strategy_map.get(order_id, "")
            return _alpaca_order_to_internal(alpaca_order, strategy)
        except Exception as exc:
            log.error("get_order_status failed for %s: %s", order_id[:8], exc)
            raise BrokerError(f"Failed to fetch order status: {exc}") from exc

    def get_open_orders(self) -> dict[str, Order]:
        """Fetch all open orders from Alpaca."""
        _require_alpaca()
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus

            request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            alpaca_orders = self._client.get_orders(filter=request)

            # Build reverse map: alpaca_id → internal_id
            reverse_map = {v: k for k, v in self._order_id_map.items()}

            result: dict[str, Order] = {}
            for ao in alpaca_orders:
                alpaca_id = str(ao.id)
                internal_id = reverse_map.get(alpaca_id, alpaca_id)
                strategy = self._order_strategy_map.get(internal_id, "")
                order = _alpaca_order_to_internal(ao, strategy)
                order.id = internal_id
                result[internal_id] = order
            return result
        except Exception as exc:
            log.error("get_open_orders failed: %s", exc)
            raise BrokerError(f"Failed to fetch open orders: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_alpaca_request(self, order: Order):
        """Convert an internal :class:`Order` to an alpaca-py request object."""
        _require_alpaca()
        side = _to_alpaca_side(order.side)
        tif = _to_alpaca_tif(order.time_in_force)
        qty = str(int(order.quantity)) if order.quantity == int(order.quantity) else str(order.quantity)

        if order.order_type == OrderType.MARKET:
            return MarketOrderRequest(
                symbol=order.symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
            )
        elif order.order_type == OrderType.LIMIT:
            assert order.limit_price is not None
            return LimitOrderRequest(
                symbol=order.symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                limit_price=order.limit_price,
            )
        elif order.order_type == OrderType.STOP:
            assert order.stop_price is not None
            return StopOrderRequest(
                symbol=order.symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                stop_price=order.stop_price,
            )
        elif order.order_type == OrderType.STOP_LIMIT:
            assert order.stop_price is not None
            assert order.limit_price is not None
            return StopLimitOrderRequest(
                symbol=order.symbol,
                qty=qty,
                side=side,
                time_in_force=tif,
                stop_price=order.stop_price,
                limit_price=order.limit_price,
            )
        else:
            raise BrokerError(f"Unsupported order type: {order.order_type}")

    # ------------------------------------------------------------------
    # WebSocket stream (real-time fills)
    # ------------------------------------------------------------------

    def _start_stream(self, api_key: str, secret_key: str) -> None:
        """Start the Alpaca WebSocket trade update stream in a background thread."""
        _require_alpaca()
        self._stream = TradingStream(api_key=api_key, secret_key=secret_key, paper=self._paper)
        self._stream.subscribe_trade_updates(self._on_trade_update)

        self._stream_thread = threading.Thread(
            target=self._stream.run,
            name="alpaca-stream",
            daemon=True,
        )
        self._stream_thread.start()
        log.info("Alpaca TradingStream started in background thread")

    async def _on_trade_update(self, data: object) -> None:
        """
        Handle real-time trade updates from the Alpaca WebSocket.

        Converts the update to a :class:`Fill` and dispatches to callbacks
        when the event represents a (partial) fill.
        """
        try:
            event = data.event  # type: ignore[attr-defined]
            if event not in ("fill", "partial_fill"):
                return

            ao = data.order  # type: ignore[attr-defined]
            alpaca_id = str(ao.id)
            reverse_map = {v: k for k, v in self._order_id_map.items()}
            internal_id = reverse_map.get(alpaca_id, alpaca_id)
            strategy = self._order_strategy_map.get(internal_id, "")

            fill_qty = float(data.qty)  # type: ignore[attr-defined]
            fill_price = float(data.price)  # type: ignore[attr-defined]
            fill_ts = data.timestamp  # type: ignore[attr-defined]

            fill = Fill(
                order_id=internal_id,
                symbol=ao.symbol,
                side=_from_alpaca_side(ao.side),
                quantity=fill_qty,
                price=fill_price,
                commission=0.0,  # Alpaca paper trading has zero commission
                timestamp=fill_ts,
                strategy_name=strategy,
            )
            log.info("Trade update received: %r", fill)
            self._notify_fill(fill)

        except Exception:  # noqa: BLE001
            log.exception("Error processing trade update: %r", data)

    def shutdown(self) -> None:
        """Stop the WebSocket stream and clean up."""
        if self._stream is not None:
            try:
                self._stream.stop()
                log.info("Alpaca TradingStream stopped")
            except Exception:  # noqa: BLE001
                log.exception("Error stopping TradingStream")
        if self._stream_thread is not None:
            self._stream_thread.join(timeout=5.0)

    def __repr__(self) -> str:
        mode = "paper" if self._paper else "live"
        return f"AlpacaBroker(mode={mode!r})"


__all__ = ["AlpacaBroker"]
