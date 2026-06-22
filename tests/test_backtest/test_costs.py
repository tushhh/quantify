"""
tests/test_backtest/test_costs.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for quantify.backtest.costs.CostModel.

Covers:
- calculate_commission: per-share and minimum enforcement
- calculate_execution_price: BUY raises price, SELL lowers price
- calculate_execution_price: MARKET vs LIMIT order type differences
- calculate_total_cost: always positive, increases with quantity
- Convenience constructors: zero(), retail(), institutional()
- Validation: negative parameters raise ValueError
- Edge cases: zero price, zero quantity
"""

from __future__ import annotations

import pytest

from quantify.backtest.costs import CostModel
from quantify.execution.order import OrderSide, OrderType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _buy_market() -> tuple[OrderSide, OrderType]:
    return OrderSide.BUY, OrderType.MARKET


def _sell_market() -> tuple[OrderSide, OrderType]:
    return OrderSide.SELL, OrderType.MARKET


def _buy_limit() -> tuple[OrderSide, OrderType]:
    return OrderSide.BUY, OrderType.LIMIT


def _sell_limit() -> tuple[OrderSide, OrderType]:
    return OrderSide.SELL, OrderType.LIMIT


# ---------------------------------------------------------------------------
# Commission tests
# ---------------------------------------------------------------------------


class TestCalculateCommission:
    def test_per_share_rate(self) -> None:
        model = CostModel(commission_per_share=0.005, min_commission=0.0)
        assert model.calculate_commission(200, 100.0) == pytest.approx(1.0)

    def test_minimum_commission_enforced(self) -> None:
        model = CostModel(commission_per_share=0.001, min_commission=1.0)
        # 5 shares × $0.001 = $0.005 < $1.00 → minimum applies
        assert model.calculate_commission(5, 50.0) == pytest.approx(1.0)

    def test_commission_scales_with_quantity(self) -> None:
        model = CostModel(commission_per_share=0.01, min_commission=0.0)
        c100 = model.calculate_commission(100, 50.0)
        c200 = model.calculate_commission(200, 50.0)
        assert c200 == pytest.approx(2 * c100)

    def test_zero_quantity_returns_minimum(self) -> None:
        model = CostModel(commission_per_share=0.005, min_commission=1.0)
        result = model.calculate_commission(0, 100.0)
        assert result == pytest.approx(1.0)

    def test_commission_alias(self) -> None:
        """commission() is an alias for calculate_commission()."""
        model = CostModel(commission_per_share=0.005, min_commission=1.0)
        assert model.commission(100, 50.0) == model.calculate_commission(100, 50.0)


# ---------------------------------------------------------------------------
# Execution price tests
# ---------------------------------------------------------------------------


class TestCalculateExecutionPrice:
    def test_buy_market_raises_price(self) -> None:
        model = CostModel(spread_bps=10.0, market_impact_bps=10.0, slippage_pct=0.001)
        price = 100.0
        exec_price = model.calculate_execution_price(price, OrderSide.BUY, OrderType.MARKET)
        assert exec_price > price

    def test_sell_market_lowers_price(self) -> None:
        model = CostModel(spread_bps=10.0, market_impact_bps=10.0, slippage_pct=0.001)
        price = 100.0
        exec_price = model.calculate_execution_price(price, OrderSide.SELL, OrderType.MARKET)
        assert exec_price < price

    def test_buy_limit_raises_price_less_than_market(self) -> None:
        model = CostModel(spread_bps=10.0, market_impact_bps=10.0, slippage_pct=0.001)
        price = 100.0
        exec_market = model.calculate_execution_price(price, OrderSide.BUY, OrderType.MARKET)
        exec_limit = model.calculate_execution_price(price, OrderSide.BUY, OrderType.LIMIT)
        assert exec_market > exec_limit >= price

    def test_sell_limit_lowers_price_less_than_market(self) -> None:
        model = CostModel(spread_bps=10.0, market_impact_bps=10.0, slippage_pct=0.001)
        price = 100.0
        exec_market = model.calculate_execution_price(price, OrderSide.SELL, OrderType.MARKET)
        exec_limit = model.calculate_execution_price(price, OrderSide.SELL, OrderType.LIMIT)
        assert exec_market < exec_limit <= price

    def test_zero_cost_model_returns_same_price(self) -> None:
        model = CostModel.zero()
        price = 150.0
        assert model.calculate_execution_price(
            price, OrderSide.BUY, OrderType.MARKET
        ) == pytest.approx(price)
        assert model.calculate_execution_price(
            price, OrderSide.SELL, OrderType.MARKET
        ) == pytest.approx(price)

    def test_slippage_alias(self) -> None:
        """slippage() is an alias for calculate_execution_price()."""
        model = CostModel(spread_bps=5.0, market_impact_bps=5.0, slippage_pct=0.0005)
        price = 100.0
        assert model.slippage(price, OrderSide.BUY, OrderType.MARKET) == \
               model.calculate_execution_price(price, OrderSide.BUY, OrderType.MARKET)


# ---------------------------------------------------------------------------
# Total cost tests
# ---------------------------------------------------------------------------


class TestCalculateTotalCost:
    def test_total_cost_always_positive(self) -> None:
        model = CostModel()
        for qty, price in [(10, 50.0), (100, 200.0), (1, 10.0)]:
            for side in (OrderSide.BUY, OrderSide.SELL):
                cost = model.calculate_total_cost(qty, price, side, OrderType.MARKET)
                assert cost > 0.0

    def test_total_cost_scales_with_quantity(self) -> None:
        model = CostModel()
        cost_100 = model.calculate_total_cost(100, 50.0, OrderSide.BUY, OrderType.MARKET)
        cost_200 = model.calculate_total_cost(200, 50.0, OrderSide.BUY, OrderType.MARKET)
        assert cost_200 > cost_100

    def test_market_order_costs_more_than_limit(self) -> None:
        model = CostModel(spread_bps=10.0, market_impact_bps=10.0, slippage_pct=0.001)
        qty, price = 100, 100.0
        market_cost = model.calculate_total_cost(qty, price, OrderSide.BUY, OrderType.MARKET)
        limit_cost = model.calculate_total_cost(qty, price, OrderSide.BUY, OrderType.LIMIT)
        assert market_cost > limit_cost

    def test_zero_cost_model_only_commissions(self) -> None:
        """Zero-cost model has no price impact; total cost = commission only."""
        model = CostModel.zero()
        qty, price = 100, 50.0
        cost = model.calculate_total_cost(qty, price, OrderSide.BUY, OrderType.MARKET)
        assert cost == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestCostModelValidation:
    @pytest.mark.parametrize("param,value", [
        ("commission_per_share", -0.01),
        ("min_commission", -1.0),
        ("spread_bps", -5.0),
        ("market_impact_bps", -1.0),
        ("slippage_pct", -0.001),
    ])
    def test_negative_params_raise(self, param: str, value: float) -> None:
        kwargs = {
            "commission_per_share": 0.005,
            "min_commission": 1.0,
            "spread_bps": 5.0,
            "market_impact_bps": 10.0,
            "slippage_pct": 0.0005,
        }
        kwargs[param] = value
        with pytest.raises(ValueError):
            CostModel(**kwargs)


# ---------------------------------------------------------------------------
# Convenience constructor tests
# ---------------------------------------------------------------------------


class TestCostModelConstructors:
    def test_zero_model_has_zero_costs(self) -> None:
        m = CostModel.zero()
        assert m.commission_per_share == 0.0
        assert m.min_commission == 0.0
        assert m.spread_bps == 0.0
        assert m.market_impact_bps == 0.0
        assert m.slippage_pct == 0.0

    def test_retail_model_has_positive_costs(self) -> None:
        m = CostModel.retail()
        assert m.commission_per_share > 0
        assert m.spread_bps > 0
        assert m.market_impact_bps > 0

    def test_institutional_model_cheaper_than_retail(self) -> None:
        retail = CostModel.retail()
        inst = CostModel.institutional()
        assert inst.commission_per_share < retail.commission_per_share
        assert inst.spread_bps < retail.spread_bps

    def test_repr_contains_class_name(self) -> None:
        m = CostModel()
        assert "CostModel" in repr(m)


# ---------------------------------------------------------------------------
# Parametrised spread/impact tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spread_bps,impact_bps,slippage", [
    (0, 0, 0),
    (5, 10, 0.0005),
    (20, 30, 0.002),
])
def test_buy_execution_price_increases_with_costs(
    spread_bps: float, impact_bps: float, slippage: float
) -> None:
    model = CostModel(spread_bps=spread_bps, market_impact_bps=impact_bps, slippage_pct=slippage)
    base_price = 100.0
    exec_price = model.calculate_execution_price(base_price, OrderSide.BUY, OrderType.MARKET)
    assert exec_price >= base_price


@pytest.mark.parametrize("spread_bps,impact_bps,slippage", [
    (0, 0, 0),
    (5, 10, 0.0005),
    (20, 30, 0.002),
])
def test_sell_execution_price_decreases_with_costs(
    spread_bps: float, impact_bps: float, slippage: float
) -> None:
    model = CostModel(spread_bps=spread_bps, market_impact_bps=impact_bps, slippage_pct=slippage)
    base_price = 100.0
    exec_price = model.calculate_execution_price(base_price, OrderSide.SELL, OrderType.MARKET)
    assert exec_price <= base_price


# ---------------------------------------------------------------------------
# Slippage sanity guard
# ---------------------------------------------------------------------------


def test_implausible_slippage_warns(caplog):
    """slippage_pct far above the default is flagged as a likely units error."""
    import logging

    with caplog.at_level(logging.WARNING, logger="quantify.backtest.costs"):
        CostModel(slippage_pct=0.05)  # 5% per fill — 100x the 5 bps default

    assert any("likely a units error" in r.message for r in caplog.records)


def test_normal_slippage_does_not_warn(caplog):
    """A realistic slippage value produces no units-error warning."""
    import logging

    with caplog.at_level(logging.WARNING, logger="quantify.backtest.costs"):
        CostModel(slippage_pct=0.0005)  # 5 bps — the default

    assert not any("likely a units error" in r.message for r in caplog.records)
