"""
quantify.execution.portfolio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Portfolio tracks all positions, cash, P&L, and the equity curve.

The :class:`Portfolio` is the source of truth for what the system owns.
It is updated by :meth:`update_from_fill` (called by the order manager's
fill callback) and :meth:`update_market_prices` (called by the engine on
each bar).

Design principles
-----------------
* **Single responsibility** — the portfolio only tracks state; it does not
  submit orders or generate signals.
* **Full audit trail** — every fill that changes the portfolio is recorded
  so the equity curve and P&L can be reconstructed at any point.
* **Correct P&L accounting** — realized P&L is booked on position reduction;
  unrealized P&L is mark-to-market via :meth:`update_market_prices`.

Thread safety
-------------
Not thread-safe by default.  If fills arrive from a background WebSocket
thread, the caller should protect updates with a lock.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from quantify.execution.order import Fill, OrderSide, Position

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


class Portfolio:
    """
    Real-time portfolio state tracker.

    Parameters
    ----------
    initial_capital:
        Starting cash balance in USD.

    Attributes
    ----------
    cash:
        Current cash balance (net of all fills and commissions).
    positions:
        Mapping of ``symbol → Position`` for currently open positions.
    fills:
        Complete list of all :class:`~quantify.execution.order.Fill`
        objects applied to this portfolio.
    equity_curve:
        List of ``(timestamp, equity)`` tuples recorded on every call to
        :meth:`update_market_prices` and :meth:`update_from_fill`.
    """

    def __init__(self, initial_capital: float = 100_000.0) -> None:
        if initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {initial_capital}")

        self._initial_capital: float = initial_capital
        self._cash: float = initial_capital

        # symbol → Position (including flat positions for history)
        self._positions: dict[str, Position] = {}

        # Fill history
        self._fills: list[Fill] = []

        # Equity curve: list of (timestamp, equity) tuples
        self._equity_curve: list[tuple[datetime, float]] = [
            (datetime.utcnow(), initial_capital)
        ]

        # Daily P&L tracking
        self._start_of_day_equity: float = initial_capital
        self._last_snapshot_date: Optional[datetime] = None

        log.info("Portfolio initialised: initial_capital=%.2f", initial_capital)

    # ------------------------------------------------------------------
    # Public update methods
    # ------------------------------------------------------------------

    def update_from_fill(self, fill: Fill) -> None:
        """
        Update portfolio state when a fill arrives from the order manager.

        Steps:
        1. Locate or create the position for the symbol.
        2. Apply the fill (updates quantity, avg_cost, realized P&L).
        3. Adjust cash (deduct for buys, credit for sells).
        4. Record the fill.
        5. Append an equity snapshot to the curve.

        Parameters
        ----------
        fill:
            The :class:`~quantify.execution.order.Fill` to apply.
        """
        # Get or create position
        if fill.symbol not in self._positions:
            self._positions[fill.symbol] = Position(symbol=fill.symbol)

        pos = self._positions[fill.symbol]
        pos.apply_fill(fill)

        # Adjust cash
        if fill.side == OrderSide.BUY:
            self._cash -= fill.notional + fill.commission
        else:
            self._cash += fill.notional - fill.commission

        self._fills.append(fill)

        # Snapshot equity
        equity = self._compute_equity()
        self._equity_curve.append((fill.timestamp, equity))

        log.debug(
            "Fill applied: %s %s × %.4f @ %.4f | cash=%.2f equity=%.2f",
            fill.side.value, fill.symbol, fill.quantity, fill.price,
            self._cash, equity,
        )

    def update_market_prices(self, prices: dict[str, float], timestamp: Optional[datetime] = None) -> None:
        """
        Mark all positions to market with updated prices.

        Call this once per bar (after processing fills for that bar) to
        update unrealized P&L and append an equity snapshot.

        Parameters
        ----------
        prices:
            Mapping of ``symbol → current_price``.  Symbols not in this
            dict are left at their last known price.
        timestamp:
            Bar timestamp for the equity curve entry.  Defaults to
            ``datetime.utcnow()``.
        """
        ts = timestamp or datetime.utcnow()

        for symbol, price in prices.items():
            if symbol in self._positions:
                self._positions[symbol].mark_to_market(price)

        equity = self._compute_equity()
        self._equity_curve.append((ts, equity))

        # Daily P&L reset logic
        if self._last_snapshot_date is None or ts.date() != self._last_snapshot_date.date():
            self._start_of_day_equity = equity
            self._last_snapshot_date = ts

    # ------------------------------------------------------------------
    # Allocation & exposure
    # ------------------------------------------------------------------

    def get_allocation(self) -> dict[str, float]:
        """
        Return the current allocation as a fraction of total equity.

        Returns
        -------
        dict[str, float]
            Mapping of ``symbol → allocation_pct`` (0.0 – 1.0).
            Only non-flat positions are included.  Values are signed
            (negative for short positions).

        Examples
        --------
        >>> portfolio.get_allocation()
        {'AAPL': 0.15, 'MSFT': 0.12, 'TSLA': -0.05}
        """
        equity = self._compute_equity()
        if equity == 0:
            return {}
        return {
            sym: pos.market_value / equity
            for sym, pos in self._positions.items()
            if not pos.is_flat
        }

    def get_sector_exposure(self, sector_map: dict[str, str]) -> dict[str, float]:
        """
        Aggregate position allocations by sector.

        Parameters
        ----------
        sector_map:
            Mapping of ``symbol → sector_name`` (e.g. ``{"AAPL": "Technology"}``).
            Symbols not in the map are grouped under ``"Unknown"``.

        Returns
        -------
        dict[str, float]
            Mapping of ``sector → net_allocation_pct``.

        Examples
        --------
        >>> sector_map = {"AAPL": "Technology", "JPM": "Financials"}
        >>> portfolio.get_sector_exposure(sector_map)
        {'Technology': 0.15, 'Financials': 0.08, 'Unknown': 0.0}
        """
        alloc = self.get_allocation()
        exposure: dict[str, float] = defaultdict(float)
        for sym, pct in alloc.items():
            sector = sector_map.get(sym, "Unknown")
            exposure[sector] += pct
        return dict(exposure)

    # ------------------------------------------------------------------
    # P&L properties
    # ------------------------------------------------------------------

    @property
    def daily_pnl(self) -> float:
        """
        P&L since the start of the current trading day.

        Resets to zero each time :meth:`update_market_prices` is called
        with a new date.
        """
        return self._compute_equity() - self._start_of_day_equity

    @property
    def total_pnl(self) -> float:
        """Total P&L since portfolio inception."""
        return self._compute_equity() - self._initial_capital

    @property
    def total_return(self) -> float:
        """Total return as a fraction (e.g. 0.15 = +15%)."""
        if self._initial_capital == 0:
            return 0.0
        return self.total_pnl / self._initial_capital

    @property
    def realized_pnl(self) -> float:
        """Sum of realized P&L across all positions."""
        return sum(pos.realized_pnl for pos in self._positions.values())

    @property
    def unrealized_pnl(self) -> float:
        """Sum of unrealized P&L across all open positions."""
        return sum(pos.unrealized_pnl for pos in self._positions.values())

    @property
    def drawdown(self) -> float:
        """
        Current drawdown from the peak equity as a fraction (0.0 to 1.0).

        A value of 0.10 means the portfolio is currently 10% below its
        all-time high.

        Returns
        -------
        float
            Always non-negative.  Returns 0.0 if there is no equity history
            or if we are at a new high.
        """
        if len(self._equity_curve) < 2:
            return 0.0
        equities = [e for _, e in self._equity_curve]
        peak = max(equities)
        current = equities[-1]
        if peak == 0:
            return 0.0
        return max(0.0, (peak - current) / peak)

    @property
    def max_drawdown(self) -> float:
        """
        Maximum historical drawdown as a fraction.

        Computed over the entire equity curve recorded since inception.
        """
        if len(self._equity_curve) < 2:
            return 0.0
        equities = [e for _, e in self._equity_curve]
        peak = equities[0]
        max_dd = 0.0
        for e in equities:
            if e > peak:
                peak = e
            dd = (peak - e) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    # ------------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------------

    @property
    def cash(self) -> float:
        """Current cash balance."""
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        """All positions (including flat ones for history)."""
        return dict(self._positions)

    @property
    def open_positions(self) -> dict[str, Position]:
        """Only non-flat positions."""
        return {sym: pos for sym, pos in self._positions.items() if not pos.is_flat}

    @property
    def equity(self) -> float:
        """Current total equity (cash + mark-to-market positions value)."""
        return self._compute_equity()

    @property
    def positions_value(self) -> float:
        """Total market value of all open positions (net, signed)."""
        return sum(pos.market_value for pos in self._positions.values() if not pos.is_flat)

    @property
    def gross_exposure(self) -> float:
        """Absolute sum of all position market values."""
        return sum(abs(pos.market_value) for pos in self._positions.values() if not pos.is_flat)

    @property
    def net_exposure(self) -> float:
        """Net signed market value of all positions."""
        return self.positions_value

    @property
    def leverage(self) -> float:
        """Gross exposure divided by equity."""
        eq = self.equity
        return self.gross_exposure / eq if eq > 0 else 0.0

    @property
    def fills(self) -> list[Fill]:
        """All fills recorded on this portfolio."""
        return list(self._fills)

    @property
    def equity_curve(self) -> list[tuple[datetime, float]]:
        """
        Equity curve as a list of ``(timestamp, equity)`` tuples.

        The first entry is always ``(inception_time, initial_capital)``.
        """
        return list(self._equity_curve)

    # ------------------------------------------------------------------
    # Position helpers
    # ------------------------------------------------------------------

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Return the position for *symbol*, or ``None`` if no position exists.

        Parameters
        ----------
        symbol:
            Ticker symbol.
        """
        return self._positions.get(symbol)

    def get_position_quantity(self, symbol: str) -> float:
        """Return the current signed quantity for *symbol* (0.0 if flat/unknown)."""
        pos = self._positions.get(symbol)
        return pos.quantity if pos else 0.0

    def get_position_side(self, symbol: str) -> str:
        """
        Return ``"long"``, ``"short"``, or ``"flat"`` for *symbol*.

        Returns ``"flat"`` for unknown symbols.
        """
        pos = self._positions.get(symbol)
        return pos.side if pos else "flat"

    # ------------------------------------------------------------------
    # Snapshot / serialization helpers
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """
        Return a dict snapshot of the portfolio's current state.

        Useful for logging, persisting to a database, or comparing states
        in tests.

        Returns
        -------
        dict
            Keys: ``cash``, ``equity``, ``positions_value``, ``realized_pnl``,
            ``unrealized_pnl``, ``total_pnl``, ``daily_pnl``, ``drawdown``,
            ``leverage``, ``positions`` (list of position dicts).
        """
        return {
            "cash": self._cash,
            "equity": self.equity,
            "positions_value": self.positions_value,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "total_return_pct": self.total_return * 100,
            "daily_pnl": self.daily_pnl,
            "drawdown_pct": self.drawdown * 100,
            "max_drawdown_pct": self.max_drawdown * 100,
            "leverage": self.leverage,
            "positions": [
                {
                    "symbol": pos.symbol,
                    "side": pos.side,
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                    "market_price": pos.market_price,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
                for pos in self._positions.values()
                if not pos.is_flat
            ],
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_equity(self) -> float:
        """Compute total equity from current cash and position MTM values."""
        return self._cash + sum(pos.market_value for pos in self._positions.values())

    def __repr__(self) -> str:
        return (
            f"Portfolio(equity={self.equity:.2f}, cash={self._cash:.2f}, "
            f"positions={len(self.open_positions)}, "
            f"total_pnl={self.total_pnl:.2f})"
        )


__all__ = ["Portfolio"]
