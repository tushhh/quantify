"""
quantify.backtest.costs
~~~~~~~~~~~~~~~~~~~~~~~
Transaction cost modeling for the backtesting engine.

This module provides a standalone :class:`CostModel` that mirrors the structure
of the one in :mod:`quantify.execution.broker.simulated` but adds market-impact
modelling and a richer ``calculate_total_cost`` API for pre-trade cost estimates.

The two cost models coexist intentionally:
* ``simulated.CostModel`` — used *inside* the broker fill loop for slippage.
* ``backtest.CostModel``  — used for pre-trade analytics, reports, and as a
  configuration object that the engine passes into the simulated broker.

Design
------
* All monetary amounts are in USD.
* Costs are computed *per side* (every order pays commissions + spread + impact).
* ``market_impact_bps`` models temporary price impact from order flow, while
  ``spread_bps`` models the bid-ask spread cost.
* ``slippage_pct`` is an additional random-walk-style execution shortfall (5 bps
  by default) applied to market orders.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from quantify.execution.order import OrderSide, OrderType

log = logging.getLogger(__name__)

# Per-fill slippage above this fraction of price (1% = 200x the 5 bps default)
# is treated as a probable units error and triggers a loud warning.
_SLIPPAGE_SANITY_THRESHOLD = 0.01


@dataclass
class CostModel:
    """
    Configurable transaction cost model for backtesting.

    Parameters
    ----------
    commission_per_share:
        Fixed commission per share traded (default: $0.005/share).
    min_commission:
        Minimum commission per order (default: $1.00).
    spread_bps:
        Full bid-ask spread in basis points.  Half is charged per trade in
        the adverse direction (default: 5 bps total → 2.5 bps each side).
    market_impact_bps:
        Estimated market impact in basis points.  Models temporary price
        impact from order flow (default: 10 bps).  Applied to market orders.
    slippage_pct:
        Additional execution shortfall as a fraction of price (default: 0.0005
        = 5 bps).  Applied to market orders only.
    """

    commission_per_share: float = 0.005
    min_commission: float = 1.0
    spread_bps: float = 5.0
    market_impact_bps: float = 10.0
    slippage_pct: float = 0.0005

    def __post_init__(self) -> None:
        if self.commission_per_share < 0:
            raise ValueError("commission_per_share must be >= 0")
        if self.min_commission < 0:
            raise ValueError("min_commission must be >= 0")
        if self.spread_bps < 0:
            raise ValueError("spread_bps must be >= 0")
        if self.market_impact_bps < 0:
            raise ValueError("market_impact_bps must be >= 0")
        if self.slippage_pct < 0:
            raise ValueError("slippage_pct must be >= 0")

        # slippage_pct is a *fraction* of price (0.0005 = 5 bps). Anything above
        # ~1% per fill is almost certainly a units error — e.g. a caller passing
        # 0.05 meaning "0.05%" but sending the raw fraction (100x too large),
        # which silently bleeds the portfolio on every trade. Warn loudly rather
        # than clamp, so the explicit value is honoured but the likely mistake is
        # visible in the logs.
        if self.slippage_pct > _SLIPPAGE_SANITY_THRESHOLD:
            log.warning(
                "CostModel: slippage_pct=%.4f is %.0fx the 5 bps default and "
                "implies %.1f%% cost per fill — likely a units error "
                "(expected a fraction of price, e.g. 0.0005 for 5 bps).",
                self.slippage_pct,
                self.slippage_pct / 0.0005,
                self.slippage_pct * 100.0,
            )

    # ------------------------------------------------------------------
    # Core pricing methods
    # ------------------------------------------------------------------

    def calculate_execution_price(
        self,
        price: float,
        side: OrderSide,
        order_type: OrderType,
    ) -> float:
        """
        Return the expected execution price after spread, slippage, and
        market impact adjustments.

        For **buy** orders the execution price is pushed *above* the quoted
        price (adverse fill); for **sell** orders it is pushed *below*.

        Parameters
        ----------
        price:
            Mid-market (or limit) reference price.
        side:
            :class:`~quantify.execution.order.OrderSide` — BUY or SELL.
        order_type:
            :class:`~quantify.execution.order.OrderType`.  MARKET orders
            incur the full slippage and market-impact adjustment; limit/stop
            orders incur only the half-spread.

        Returns
        -------
        float
            Adjusted execution price.
        """
        if price <= 0:
            log.warning("calculate_execution_price: price=%s is non-positive, returning 0", price)
            return price

        half_spread = (self.spread_bps / 10_000.0) / 2.0

        if order_type == OrderType.MARKET:
            total_adverse_frac = (
                half_spread
                + self.market_impact_bps / 10_000.0
                + self.slippage_pct
            )
        else:
            # Limit/stop orders already pin a price; only spread applies
            total_adverse_frac = half_spread

        if side == OrderSide.BUY:
            adjusted = price * (1.0 + total_adverse_frac)
        else:
            adjusted = price * (1.0 - total_adverse_frac)

        log.debug(
            "calculate_execution_price: side=%s type=%s price=%.4f adj=%.4f (frac=%.6f)",
            side.value, order_type.value, price, adjusted, total_adverse_frac,
        )
        return adjusted

    def calculate_commission(self, quantity: float, price: float) -> float:
        """
        Compute brokerage commission for a fill.

        The commission is ``max(quantity × commission_per_share, min_commission)``.

        Parameters
        ----------
        quantity:
            Absolute number of shares traded (must be positive).
        price:
            Fill price (accepted for API consistency; not used in this model
            but may be used in percentage-based commission models).

        Returns
        -------
        float
            Commission amount in USD.
        """
        if quantity <= 0:
            log.warning("calculate_commission: quantity=%s must be positive", quantity)
            return self.min_commission
        raw = abs(quantity) * self.commission_per_share
        commission = max(raw, self.min_commission)
        log.debug(
            "calculate_commission: qty=%.2f price=%.4f commission=%.4f",
            quantity, price, commission,
        )
        return commission

    def calculate_total_cost(
        self,
        quantity: float,
        price: float,
        side: OrderSide,
        order_type: OrderType,
    ) -> float:
        """
        Compute the total all-in transaction cost (commission + spread cost +
        slippage/impact cost) in USD.

        This is the *incremental* cost relative to trading at the mid-price:

            total_cost = |execution_price - mid_price| × |quantity| + commission

        Parameters
        ----------
        quantity:
            Number of shares (positive).
        price:
            Mid-market reference price.
        side:
            Order side — determines which direction the price moves adversely.
        order_type:
            Affects how much slippage is applied.

        Returns
        -------
        float
            Total transaction cost in USD (always positive).
        """
        exec_price = self.calculate_execution_price(price, side, order_type)
        price_impact_cost = abs(exec_price - price) * abs(quantity)
        commission = self.calculate_commission(quantity, price)
        total = price_impact_cost + commission

        log.debug(
            "calculate_total_cost: qty=%.2f mid=%.4f exec=%.4f "
            "impact_cost=%.4f commission=%.4f total=%.4f",
            quantity, price, exec_price, price_impact_cost, commission, total,
        )
        return total

    # ------------------------------------------------------------------
    # Compatibility shim for SimulatedBroker.CostModel interface
    # ------------------------------------------------------------------

    def commission(self, quantity: float, price: float) -> float:
        """Alias for :meth:`calculate_commission` (SimulatedBroker interface)."""
        return self.calculate_commission(quantity, price)

    def slippage(self, price: float, side: OrderSide, order_type: OrderType) -> float:
        """
        Return the slippage-adjusted fill price (SimulatedBroker interface).

        Delegates to :meth:`calculate_execution_price`.
        """
        return self.calculate_execution_price(price, side, order_type)

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def zero(cls) -> "CostModel":
        """No-cost model for ideal-world benchmarking."""
        return cls(
            commission_per_share=0.0,
            min_commission=0.0,
            spread_bps=0.0,
            market_impact_bps=0.0,
            slippage_pct=0.0,
        )

    @classmethod
    def retail(cls) -> "CostModel":
        """Typical retail broker costs ($0.005/share, 5 bps spread, 10 bps impact)."""
        return cls()

    @classmethod
    def institutional(cls) -> "CostModel":
        """Lower-cost institutional model ($0.001/share, 2 bps spread, 5 bps impact)."""
        return cls(
            commission_per_share=0.001,
            min_commission=0.50,
            spread_bps=2.0,
            market_impact_bps=5.0,
            slippage_pct=0.0002,
        )

    def __repr__(self) -> str:
        return (
            f"CostModel(commission_per_share={self.commission_per_share}, "
            f"min_commission={self.min_commission}, "
            f"spread_bps={self.spread_bps}, "
            f"market_impact_bps={self.market_impact_bps}, "
            f"slippage_pct={self.slippage_pct})"
        )


__all__ = ["CostModel"]
