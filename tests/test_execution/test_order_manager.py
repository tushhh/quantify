"""
tests/test_execution/test_order_manager.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for quantify.execution.order_manager.OrderManager.

Covers:
- Successful order submission → broker receives order
- Duplicate order deduplication (same strategy + symbol)
- Risk check: max_order_value exceeded → rejection
- Risk check: positive quantity validation
- cancel() removes order from open index
- cancel_all() cancels every open order
- cancel_for_symbol() cancels orders for specific symbol
- replace() cancels old order and submits new one
- Fill listener registration and dispatch
- has_open_order() correctness
- order_count() by status
- get_open_orders() filtered by strategy
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock


from quantify.execution.broker.simulated import BarData, SimulatedBroker
from quantify.execution.order import Order, OrderSide, OrderStatus, OrderType
from quantify.execution.order_manager import OrderManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts() -> datetime:
    return datetime(2023, 6, 1, 9, 30, tzinfo=timezone.utc)


def _bar(
    symbol: str = "AAPL",
    open_: float = 150.0,
    high: float = 155.0,
    low: float = 148.0,
    close: float = 152.0,
) -> BarData:
    return BarData(
        symbol=symbol,
        timestamp=_ts(),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1_000_000,
    )


def _market_buy(
    symbol: str = "AAPL",
    qty: float = 10,
    strategy: str = "test_strat",
) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=qty,
        strategy_name=strategy,
    )


def _market_sell(
    symbol: str = "AAPL",
    qty: float = 10,
    strategy: str = "test_strat",
) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=qty,
        strategy_name=strategy,
    )


def _make_broker_and_om(
    capital: float = 100_000.0,
    max_order_value: Optional[float] = None,
    max_position_pct: Optional[float] = None,
) -> tuple[SimulatedBroker, OrderManager]:
    broker = SimulatedBroker(initial_capital=capital)
    om = OrderManager(broker=broker, max_order_value=max_order_value, max_position_pct=max_position_pct)
    return broker, om


# ---------------------------------------------------------------------------
# Basic submission tests
# ---------------------------------------------------------------------------


class TestOrderManagerSubmit:
    def test_submit_returns_order_id(self) -> None:
        broker, om = _make_broker_and_om()
        order = _market_buy()
        result = om.submit(order)
        assert result is not None
        assert isinstance(result, str)

    def test_submitted_order_tracked(self) -> None:
        broker, om = _make_broker_and_om()
        order = _market_buy()
        oid = om.submit(order)
        assert om.get_order(oid) is not None

    def test_submitted_order_reaches_broker(self) -> None:
        broker, om = _make_broker_and_om()
        order = _market_buy()
        om.submit(order)
        # After processing the bar, order should be filled
        fills = broker.process_bar(_bar())
        assert len(fills) == 1

    def test_zero_quantity_rejected(self) -> None:
        broker, om = _make_broker_and_om()
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0,
            strategy_name="test",
        )
        result = om.submit(order)
        assert result is None


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_order_dropped(self) -> None:
        broker, om = _make_broker_and_om()

        order1 = _market_buy(symbol="AAPL", strategy="momentum")
        order2 = _market_buy(symbol="AAPL", strategy="momentum", qty=20)

        oid1 = om.submit(order1)
        oid2 = om.submit(order2)

        assert oid1 is not None
        assert oid2 is None, "Duplicate order should be dropped"

    def test_different_symbols_not_duplicate(self) -> None:
        broker, om = _make_broker_and_om()

        oid1 = om.submit(_market_buy("AAPL", strategy="momentum"))
        oid2 = om.submit(_market_buy("MSFT", strategy="momentum"))

        assert oid1 is not None
        assert oid2 is not None

    def test_different_strategies_not_duplicate(self) -> None:
        broker, om = _make_broker_and_om()

        oid1 = om.submit(_market_buy("AAPL", strategy="strategy_a"))
        oid2 = om.submit(_market_buy("AAPL", strategy="strategy_b"))

        assert oid1 is not None
        assert oid2 is not None

    def test_after_fill_same_key_accepted(self) -> None:
        """After an order is filled, a new order for the same key is accepted."""
        broker, om = _make_broker_and_om()

        order1 = _market_buy(symbol="AAPL", strategy="momentum", qty=10)
        om.submit(order1)
        # Fill the order
        broker.process_bar(_bar())

        # After fill, the key should be free
        order2 = _market_buy(symbol="AAPL", strategy="momentum", qty=5)
        oid2 = om.submit(order2)
        assert oid2 is not None


# ---------------------------------------------------------------------------
# Risk check tests
# ---------------------------------------------------------------------------


class TestRiskChecks:
    def test_max_order_value_exceeded_rejected(self) -> None:
        broker, om = _make_broker_and_om(max_order_value=1_000.0)
        # Order: 100 shares × $150 limit = $15,000 > $1,000
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            limit_price=150.0,
            strategy_name="test",
        )
        result = om.submit(order)
        assert result is None

    def test_max_order_value_within_limit_accepted(self) -> None:
        broker, om = _make_broker_and_om(max_order_value=50_000.0)
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            limit_price=150.0,
            strategy_name="test",
        )
        result = om.submit(order)
        assert result is not None

    def test_market_order_not_blocked_by_value_check_no_price(self) -> None:
        """Market orders without a reference price bypass the value check."""
        broker, om = _make_broker_and_om(max_order_value=100.0)
        # Market order with no limit/stop price — cannot estimate value
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=1000,
            strategy_name="test",
        )
        result = om.submit(order)
        # Should be accepted (no price reference to check against)
        assert result is not None


# ---------------------------------------------------------------------------
# Cancel tests
# ---------------------------------------------------------------------------


class TestCancel:
    def test_cancel_open_order(self) -> None:
        broker, om = _make_broker_and_om()
        # Use a limit order that won't fill immediately
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            limit_price=50.0,  # way below market — won't fill
            strategy_name="test",
        )
        oid = om.submit(order)
        result = om.cancel(oid)
        assert result is True

    def test_cancel_removes_from_open_orders(self) -> None:
        broker, om = _make_broker_and_om()
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            limit_price=50.0,
            strategy_name="test",
        )
        oid = om.submit(order)
        om.cancel(oid)
        open_orders = om.get_open_orders()
        assert all(o.id != oid for o in open_orders)

    def test_cancel_unknown_order_returns_false(self) -> None:
        broker, om = _make_broker_and_om()
        result = om.cancel("not-a-real-id")
        assert result is False

    def test_cancel_all(self) -> None:
        broker, om = _make_broker_and_om()
        for i in range(3):
            order = Order(
                symbol=f"STK{i}",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=10,
                limit_price=1.0,  # won't fill
                strategy_name=f"s{i}",
            )
            om.submit(order)
        n = om.cancel_all()
        assert n == 3
        assert om.get_open_orders() == []

    def test_cancel_for_symbol(self) -> None:
        broker, om = _make_broker_and_om()
        om.submit(Order(
            symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=1.0, strategy_name="s1",
        ))
        om.submit(Order(
            symbol="AAPL", side=OrderSide.SELL, order_type=OrderType.LIMIT,
            quantity=5, limit_price=500.0, strategy_name="s2",
        ))
        om.submit(Order(
            symbol="MSFT", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=1.0, strategy_name="s1",
        ))
        n = om.cancel_for_symbol("AAPL")
        assert n == 2
        # MSFT order should still be open
        msft_orders = [o for o in om.get_open_orders() if o.symbol == "MSFT"]
        assert len(msft_orders) == 1


# ---------------------------------------------------------------------------
# Fill listener tests
# ---------------------------------------------------------------------------


class TestFillListeners:
    def test_fill_listener_called_on_order_fill(self) -> None:
        broker, om = _make_broker_and_om()
        listener = MagicMock()
        om.register_fill_listener(listener)

        om.submit(_market_buy(qty=5))
        broker.process_bar(_bar())

        assert listener.called
        fill = listener.call_args[0][0]
        assert fill.symbol == "AAPL"

    def test_multiple_listeners_all_called(self) -> None:
        broker, om = _make_broker_and_om()
        l1 = MagicMock()
        l2 = MagicMock()
        om.register_fill_listener(l1)
        om.register_fill_listener(l2)

        om.submit(_market_buy(qty=5))
        broker.process_bar(_bar())

        assert l1.called
        assert l2.called


# ---------------------------------------------------------------------------
# has_open_order tests
# ---------------------------------------------------------------------------


class TestHasOpenOrder:
    def test_returns_true_for_open_order(self) -> None:
        broker, om = _make_broker_and_om()
        om.submit(Order(
            symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=1.0, strategy_name="momentum",
        ))
        assert om.has_open_order("AAPL", "momentum") is True

    def test_returns_false_when_no_order(self) -> None:
        broker, om = _make_broker_and_om()
        assert om.has_open_order("AAPL", "momentum") is False

    def test_returns_false_after_fill(self) -> None:
        broker, om = _make_broker_and_om()
        om.submit(_market_buy("AAPL", strategy="momentum"))
        broker.process_bar(_bar())
        assert om.has_open_order("AAPL", "momentum") is False


# ---------------------------------------------------------------------------
# order_count tests
# ---------------------------------------------------------------------------


class TestOrderCount:
    def test_order_count_increases_on_submit(self) -> None:
        broker, om = _make_broker_and_om()
        assert om.order_count() == 0
        om.submit(_market_buy("AAPL", strategy="s1"))
        om.submit(_market_buy("MSFT", strategy="s2"))
        assert om.order_count() == 2

    def test_order_count_by_status(self) -> None:
        broker, om = _make_broker_and_om()
        om.submit(_market_buy("AAPL", strategy="s1"))
        broker.process_bar(_bar())
        filled_count = om.order_count(status=OrderStatus.FILLED)
        assert filled_count >= 1


# ---------------------------------------------------------------------------
# replace() tests
# ---------------------------------------------------------------------------


class TestReplace:
    def test_replace_cancels_old_and_submits_new(self) -> None:
        broker, om = _make_broker_and_om()
        old = Order(
            symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=50.0, strategy_name="test",
        )
        old_id = om.submit(old)

        new = Order(
            symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=20, limit_price=55.0, strategy_name="test",
        )
        new_id = om.replace(old_id, new)

        assert new_id is not None
        assert new_id != old_id
        # Old order should be cancelled
        old_order = om.get_order(old_id)
        assert old_order.status == OrderStatus.CANCELLED

    def test_replace_with_wrong_symbol_fails(self) -> None:
        broker, om = _make_broker_and_om()
        old = Order(
            symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=50.0, strategy_name="test",
        )
        old_id = om.submit(old)

        wrong = Order(
            symbol="MSFT",  # different symbol
            side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=50.0, strategy_name="test",
        )
        result = om.replace(old_id, wrong)
        assert result is None


# ---------------------------------------------------------------------------
# get_open_orders filter tests
# ---------------------------------------------------------------------------


class TestGetOpenOrders:
    def test_filter_by_strategy(self) -> None:
        broker, om = _make_broker_and_om()
        om.submit(Order(
            symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=1.0, strategy_name="alpha",
        ))
        om.submit(Order(
            symbol="MSFT", side=OrderSide.BUY, order_type=OrderType.LIMIT,
            quantity=10, limit_price=1.0, strategy_name="beta",
        ))
        alpha_orders = om.get_open_orders(strategy_name="alpha")
        assert len(alpha_orders) == 1
        assert alpha_orders[0].strategy_name == "alpha"
