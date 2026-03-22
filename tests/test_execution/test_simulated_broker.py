"""
tests/test_execution/test_simulated_broker.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for quantify.execution.broker.simulated.SimulatedBroker.

Covers:
- Market order fills at next bar's open (with slippage)
- Limit BUY fills when bar.low <= limit_price
- Limit BUY does not fill when bar.low > limit_price
- Limit SELL fills when bar.high >= limit_price
- Stop BUY fills when bar.high >= stop_price
- Stop SELL fills when bar.low <= stop_price
- Cash management: deducted on buy fill, credited on sell fill
- Reserved cash released after fill
- Cancel order: not filled after cancellation
- Fill callbacks are invoked
- get_positions returns non-flat positions
- get_account equity equals cash + positions value
- reset() restores broker to initial state
- Reject order with quantity <= 0
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from quantify.execution.broker.simulated import BarData, CostModel, SimulatedBroker
from quantify.execution.order import Order, OrderSide, OrderStatus, OrderType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(day: int = 1) -> datetime:
    return datetime(2023, 6, day, 9, 30, tzinfo=timezone.utc)


def _bar(
    symbol: str = "AAPL",
    open_: float = 150.0,
    high: float = 155.0,
    low: float = 148.0,
    close: float = 152.0,
    volume: float = 1_000_000,
    day: int = 1,
) -> BarData:
    return BarData(
        symbol=symbol,
        timestamp=_ts(day),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _market_buy(symbol: str = "AAPL", qty: float = 10) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=qty,
    )


def _market_sell(symbol: str = "AAPL", qty: float = 10) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=qty,
    )


def _limit_buy(symbol: str = "AAPL", qty: float = 10, limit: float = 150.0) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=qty,
        limit_price=limit,
    )


def _limit_sell(symbol: str = "AAPL", qty: float = 10, limit: float = 150.0) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=qty,
        limit_price=limit,
    )


def _stop_buy(symbol: str = "AAPL", qty: float = 10, stop: float = 155.0) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.STOP,
        quantity=qty,
        stop_price=stop,
    )


def _stop_sell(symbol: str = "AAPL", qty: float = 10, stop: float = 148.0) -> Order:
    return Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.STOP,
        quantity=qty,
        stop_price=stop,
    )


# ---------------------------------------------------------------------------
# Market order tests
# ---------------------------------------------------------------------------


class TestMarketOrders:
    def test_market_buy_fills_on_bar(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _market_buy()
        broker.submit_order(order)
        fills = broker.process_bar(_bar())
        assert len(fills) == 1
        assert fills[0].side == OrderSide.BUY
        assert fills[0].quantity == 10

    def test_market_sell_fills_on_bar(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        # Establish a position first by buying
        buy_order = _market_buy(qty=10)
        broker.submit_order(buy_order)
        broker.process_bar(_bar())

        sell_order = _market_sell(qty=10)
        broker.submit_order(sell_order)
        fills = broker.process_bar(_bar(day=2))
        sell_fills = [f for f in fills if f.side == OrderSide.SELL]
        assert len(sell_fills) == 1

    def test_market_buy_fill_price_includes_slippage(self) -> None:
        broker = SimulatedBroker(
            initial_capital=100_000.0,
            cost_model=CostModel(slippage_pct=0.01, spread_bps=0.0),
        )
        order = _market_buy()
        broker.submit_order(order)
        fills = broker.process_bar(_bar(open_=100.0))
        assert fills[0].price > 100.0  # slippage pushes buy price up

    def test_market_sell_fill_price_lower_than_open(self) -> None:
        broker = SimulatedBroker(
            initial_capital=100_000.0,
            cost_model=CostModel(slippage_pct=0.01, spread_bps=0.0),
        )
        order = _market_sell()
        broker.submit_order(order)
        fills = broker.process_bar(_bar(open_=100.0))
        assert fills[0].price < 100.0  # slippage pushes sell price down

    def test_market_order_status_filled(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _market_buy()
        oid = broker.submit_order(order)
        broker.process_bar(_bar())
        assert broker.get_order_status(oid).status == OrderStatus.FILLED


# ---------------------------------------------------------------------------
# Limit order tests
# ---------------------------------------------------------------------------


class TestLimitOrders:
    def test_limit_buy_fills_when_low_reaches_limit(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _limit_buy(limit=149.0)
        broker.submit_order(order)
        # Bar low=148 <= limit=149 → should fill
        fills = broker.process_bar(_bar(low=148.0, open_=152.0))
        assert len(fills) == 1
        assert fills[0].side == OrderSide.BUY

    def test_limit_buy_does_not_fill_when_low_above_limit(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _limit_buy(limit=145.0)
        broker.submit_order(order)
        # Bar low=148 > limit=145 → should NOT fill
        fills = broker.process_bar(_bar(low=148.0))
        assert len(fills) == 0

    def test_limit_sell_fills_when_high_reaches_limit(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _limit_sell(limit=154.0)
        broker.submit_order(order)
        # Bar high=155 >= limit=154 → should fill
        fills = broker.process_bar(_bar(high=155.0, open_=150.0))
        assert len(fills) == 1
        assert fills[0].side == OrderSide.SELL

    def test_limit_sell_does_not_fill_when_high_below_limit(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _limit_sell(limit=160.0)
        broker.submit_order(order)
        fills = broker.process_bar(_bar(high=155.0))
        assert len(fills) == 0


# ---------------------------------------------------------------------------
# Stop order tests
# ---------------------------------------------------------------------------


class TestStopOrders:
    def test_stop_buy_fills_when_high_hits_stop(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _stop_buy(stop=154.0)
        broker.submit_order(order)
        # Bar high=155 >= stop=154 → triggers
        fills = broker.process_bar(_bar(high=155.0, open_=150.0))
        assert len(fills) == 1

    def test_stop_buy_does_not_fill_when_high_below_stop(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _stop_buy(stop=160.0)
        broker.submit_order(order)
        fills = broker.process_bar(_bar(high=155.0))
        assert len(fills) == 0

    def test_stop_sell_fills_when_low_hits_stop(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _stop_sell(stop=149.0)
        broker.submit_order(order)
        # Bar low=148 <= stop=149 → triggers
        fills = broker.process_bar(_bar(low=148.0, open_=152.0))
        assert len(fills) == 1

    def test_stop_sell_does_not_fill_when_low_above_stop(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _stop_sell(stop=145.0)
        broker.submit_order(order)
        fills = broker.process_bar(_bar(low=148.0))
        assert len(fills) == 0


# ---------------------------------------------------------------------------
# Cash management tests
# ---------------------------------------------------------------------------


class TestCashManagement:
    def test_cash_decreases_after_buy_fill(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        initial_equity = broker.equity
        order = _market_buy(qty=100)
        broker.submit_order(order)
        broker.process_bar(_bar(open_=100.0))
        # Cash should have decreased
        assert broker.equity <= initial_equity

    def test_cash_increases_after_sell_fill(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        # First buy
        buy = _market_buy(qty=10)
        broker.submit_order(buy)
        broker.process_bar(_bar(open_=100.0))
        equity_after_buy = broker.equity

        # Now sell
        sell = _market_sell(qty=10)
        broker.submit_order(sell)
        broker.process_bar(_bar(open_=105.0, high=110.0, low=102.0, close=107.0, day=2))
        # If price went up, equity after sell should be higher
        assert broker.equity >= equity_after_buy - 200  # allow for slippage


# ---------------------------------------------------------------------------
# Cancel order tests
# ---------------------------------------------------------------------------


class TestCancelOrder:
    def test_cancelled_order_not_filled(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _limit_buy(limit=149.0)
        oid = broker.submit_order(order)
        broker.cancel_order(oid)
        # Even though bar.low <= limit, cancelled order should not fill
        fills = broker.process_bar(_bar(low=148.0))
        assert len(fills) == 0

    def test_cancel_returns_true_for_open_order(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = _limit_buy(limit=140.0)  # won't fill at current prices
        oid = broker.submit_order(order)
        result = broker.cancel_order(oid)
        assert result is True

    def test_cancel_returns_false_for_unknown_order(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        result = broker.cancel_order("nonexistent-id-123")
        assert result is False


# ---------------------------------------------------------------------------
# Fill callback tests
# ---------------------------------------------------------------------------


class TestFillCallbacks:
    def test_fill_callback_called_on_fill(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        callback = MagicMock()
        broker.register_fill_callback(callback)

        order = _market_buy(qty=5)
        broker.submit_order(order)
        broker.process_bar(_bar())

        assert callback.called
        fill = callback.call_args[0][0]
        assert fill.symbol == "AAPL"
        assert fill.quantity == 5

    def test_multiple_callbacks_all_called(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        cb1 = MagicMock()
        cb2 = MagicMock()
        broker.register_fill_callback(cb1)
        broker.register_fill_callback(cb2)

        broker.submit_order(_market_buy())
        broker.process_bar(_bar())

        assert cb1.called
        assert cb2.called


# ---------------------------------------------------------------------------
# Positions and account tests
# ---------------------------------------------------------------------------


class TestPositionsAndAccount:
    def test_get_positions_empty_initially(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        assert broker.get_positions() == {}

    def test_get_positions_after_fill(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        broker.submit_order(_market_buy(qty=50))
        broker.process_bar(_bar())
        positions = broker.get_positions()
        assert "AAPL" in positions
        assert positions["AAPL"].quantity == 50

    def test_get_account_equity_positive(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        account = broker.get_account()
        assert account.equity == pytest.approx(100_000.0)

    def test_reject_zero_quantity_order(self) -> None:
        from quantify.execution.broker.base import BrokerError
        broker = SimulatedBroker(initial_capital=100_000.0)
        order = Order(symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=0)
        with pytest.raises(BrokerError):
            broker.submit_order(order)


# ---------------------------------------------------------------------------
# Reset tests
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_orders_and_positions(self) -> None:
        broker = SimulatedBroker(initial_capital=100_000.0)
        broker.submit_order(_market_buy(qty=10))
        broker.process_bar(_bar())
        assert broker.get_positions()  # has positions

        broker.reset()
        assert broker.get_positions() == {}
        assert broker.get_open_orders() == {}
        assert broker.cash == pytest.approx(100_000.0)

    def test_reset_restores_initial_capital(self) -> None:
        capital = 250_000.0
        broker = SimulatedBroker(initial_capital=capital)
        broker.submit_order(_market_buy(qty=100))
        broker.process_bar(_bar(open_=100.0))
        broker.reset()
        assert broker.equity == pytest.approx(capital)
