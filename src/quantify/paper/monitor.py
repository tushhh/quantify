"""
quantify.paper.monitor
~~~~~~~~~~~~~~~~~~~~~~~
Real-time trading monitor for the paper-trading system.

The :class:`TradingMonitor` polls the broker for the latest account and
position state, checks for concerning conditions, prints formatted status
to the console, and provides structured data for dashboards.

Alert conditions checked
------------------------
* Portfolio drawdown exceeds configurable threshold (default 5 %)
* Daily loss exceeds configurable threshold (default 2 %)
* Gross leverage approaches or exceeds configured limit
* Individual position loss exceeds per-position stop threshold
* Number of open positions approaches configured maximum
* Consecutive monitor cycles with no fills (staleness check)

Dashboard data
--------------
:meth:`get_dashboard_data` returns a structured dict suitable for rendering
with Streamlit or similar tools.

Usage
-----
::

    monitor = TradingMonitor(max_drawdown_alert=0.05, max_daily_loss_alert=0.02)
    monitor.update(portfolio, broker)
    alerts = monitor.check_alerts()
    for alert in alerts:
        print(f"ALERT: {alert}")
    monitor.print_status()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from quantify.execution.portfolio import Portfolio
from quantify.execution.broker.base import Broker

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TradingMonitor
# ---------------------------------------------------------------------------


class TradingMonitor:
    """
    Real-time trading state monitor.

    Fetches the latest broker and portfolio state, evaluates alert conditions,
    and provides formatted output for operators and dashboards.

    Parameters
    ----------
    max_drawdown_alert:
        Drawdown fraction threshold for an alert (default: 0.05 = 5%).
    max_daily_loss_alert:
        Daily loss fraction threshold for an alert (default: 0.02 = 2%).
    max_leverage_alert:
        Gross leverage above which an alert is raised (default: 1.2).
    max_position_loss_alert:
        Single-position loss fraction that triggers an alert (default: 0.05 = 5%).
    max_positions_alert:
        Maximum open positions before a count alert is raised (default: 20).
    """

    def __init__(
        self,
        max_drawdown_alert: float = 0.05,
        max_daily_loss_alert: float = 0.02,
        max_leverage_alert: float = 1.2,
        max_position_loss_alert: float = 0.05,
        max_positions_alert: int = 20,
    ) -> None:
        self.max_drawdown_alert = max_drawdown_alert
        self.max_daily_loss_alert = max_daily_loss_alert
        self.max_leverage_alert = max_leverage_alert
        self.max_position_loss_alert = max_position_loss_alert
        self.max_positions_alert = max_positions_alert

        # Internal state cache
        self._portfolio_snapshot: Optional[dict[str, Any]] = None
        self._account_snapshot: Optional[dict[str, Any]] = None
        self._last_update: Optional[datetime] = None
        self._update_count: int = 0
        self._previous_equity: Optional[float] = None

        log.info(
            "TradingMonitor created: max_drawdown=%.1f%%, max_daily_loss=%.1f%%, "
            "max_leverage=%.2fx",
            max_drawdown_alert * 100,
            max_daily_loss_alert * 100,
            max_leverage_alert,
        )

    # ------------------------------------------------------------------
    # State update
    # ------------------------------------------------------------------

    def update(self, portfolio: Portfolio, broker: Broker) -> None:
        """
        Refresh internal state from the current portfolio and broker account.

        Parameters
        ----------
        portfolio:
            The live :class:`~quantify.execution.portfolio.Portfolio`.
        broker:
            The connected :class:`~quantify.execution.broker.base.Broker`
            instance.  Used to fetch the latest account balance and
            open positions from the venue.
        """
        try:
            self._portfolio_snapshot = portfolio.snapshot()
        except Exception as exc:
            log.error("TradingMonitor.update: failed to get portfolio snapshot: %s", exc)
            self._portfolio_snapshot = None

        try:
            account = broker.get_account()
            self._account_snapshot = {
                "cash": account.cash,
                "equity": account.equity,
                "buying_power": account.buying_power,
                "positions_value": account.positions_value,
                "leverage": account.leverage,
            }
        except Exception as exc:
            log.warning("TradingMonitor.update: could not fetch broker account: %s", exc)
            self._account_snapshot = None

        # Track equity for consecutive-cycle changes
        if self._portfolio_snapshot:
            self._previous_equity = self._portfolio_snapshot.get("equity")

        self._last_update = datetime.now(tz=timezone.utc)
        self._update_count += 1
        log.debug(
            "TradingMonitor.update #%d: equity=%.2f",
            self._update_count,
            self._portfolio_snapshot.get("equity", 0.0) if self._portfolio_snapshot else 0.0,
        )

    # ------------------------------------------------------------------
    # Alert checks
    # ------------------------------------------------------------------

    def check_alerts(self) -> list[str]:
        """
        Evaluate alert conditions against the most recently fetched state.

        Returns
        -------
        list[str]
            Human-readable alert messages.  Empty list if everything is within
            normal thresholds.
        """
        alerts: list[str] = []

        if self._portfolio_snapshot is None:
            alerts.append("WARN: No portfolio snapshot available — monitor not yet updated")
            return alerts

        snap = self._portfolio_snapshot

        # --- Drawdown ---
        drawdown_pct = snap.get("drawdown_pct", 0.0) / 100.0
        if drawdown_pct >= self.max_drawdown_alert:
            alerts.append(
                f"CRITICAL: Portfolio drawdown {drawdown_pct:.2%} exceeds alert "
                f"threshold {self.max_drawdown_alert:.2%}"
            )

        # --- Daily P&L loss ---
        equity = snap.get("equity", 1.0)
        daily_pnl = snap.get("daily_pnl", 0.0)
        if equity > 0:
            daily_loss_pct = daily_pnl / equity
            if daily_loss_pct <= -self.max_daily_loss_alert:
                alerts.append(
                    f"CRITICAL: Daily loss {daily_loss_pct:.2%} exceeds alert "
                    f"threshold -{self.max_daily_loss_alert:.2%}"
                )

        # --- Gross leverage ---
        leverage = snap.get("leverage", 0.0)
        if leverage >= self.max_leverage_alert:
            alerts.append(
                f"WARN: Gross leverage {leverage:.2f}x at or above "
                f"alert threshold {self.max_leverage_alert:.2f}x"
            )

        # --- Individual position losses ---
        positions = snap.get("positions", [])
        for pos in positions:
            mkt_val = pos.get("market_value", 0.0)
            cost_basis_val = pos.get("avg_cost", 0.0) * pos.get("quantity", 0.0)
            if cost_basis_val != 0:
                pos_pnl_pct = (mkt_val - cost_basis_val) / abs(cost_basis_val)
                if pos_pnl_pct <= -self.max_position_loss_alert:
                    alerts.append(
                        f"WARN: Position {pos['symbol']} showing loss of "
                        f"{pos_pnl_pct:.2%} (threshold -{self.max_position_loss_alert:.2%})"
                    )

        # --- Number of open positions ---
        n_positions = len(positions)
        if n_positions >= self.max_positions_alert:
            alerts.append(
                f"WARN: {n_positions} open positions at or above "
                f"alert threshold {self.max_positions_alert}"
            )

        # --- Staleness: if equity hasn't changed in many cycles ---
        if self._update_count > 20 and equity == self._previous_equity:
            alerts.append(
                "INFO: Portfolio equity unchanged for past update cycle — "
                "possible data feed staleness"
            )

        if alerts:
            for alert in alerts:
                log.warning("TradingMonitor alert: %s", alert)
        else:
            log.debug("TradingMonitor.check_alerts: all checks passed")

        return alerts

    # ------------------------------------------------------------------
    # Console output
    # ------------------------------------------------------------------

    def print_status(self) -> None:
        """
        Print a formatted status report to the console (stdout via logger).

        Shows current positions, P&L metrics, risk levels, and any active
        alerts.
        """
        if self._portfolio_snapshot is None:
            print("TradingMonitor: no data available — call update() first")
            return

        snap = self._portfolio_snapshot
        ts = self._last_update.strftime("%Y-%m-%d %H:%M:%S UTC") if self._last_update else "N/A"

        # Header
        print("\n" + "=" * 70)
        print(f"  QUANTIFY PAPER TRADER — Status as of {ts}")
        print("=" * 70)

        # Portfolio summary
        equity = snap.get("equity", 0.0)
        cash = snap.get("cash", 0.0)
        daily_pnl = snap.get("daily_pnl", 0.0)
        total_pnl = snap.get("total_pnl", 0.0)
        total_ret = snap.get("total_return_pct", 0.0)
        drawdown = snap.get("drawdown_pct", 0.0)
        leverage = snap.get("leverage", 0.0)

        print(f"\n  {'Equity:':<20} ${equity:>14,.2f}")
        print(f"  {'Cash:':<20} ${cash:>14,.2f}")
        print(f"  {'Daily P&L:':<20} ${daily_pnl:>+14,.2f}")
        print(f"  {'Total P&L:':<20} ${total_pnl:>+14,.2f}  ({total_ret:>+.2f}%)")
        print(f"  {'Drawdown:':<20} {drawdown:>14.2f}%")
        print(f"  {'Gross Leverage:':<20} {leverage:>14.3f}x")

        # Broker account (if available)
        if self._account_snapshot:
            broker_eq = self._account_snapshot.get("equity", 0.0)
            diff = equity - broker_eq
            status = "OK" if abs(diff) < 1.0 else f"DIFF ${diff:+,.2f}"
            print(f"\n  {'Broker Equity:':<20} ${broker_eq:>14,.2f}  [{status}]")

        # Positions table
        positions = snap.get("positions", [])
        if positions:
            print(f"\n  {'Open Positions':}")
            print(f"  {'Symbol':<8}  {'Side':<6}  {'Qty':>8}  {'AvgCost':>10}  "
                  f"{'MktPrice':>10}  {'MktValue':>12}  {'UnrPnL':>10}")
            print("  " + "-" * 68)
            for pos in sorted(positions, key=lambda p: abs(p.get("market_value", 0.0)), reverse=True):
                print(
                    f"  {pos['symbol']:<8}  {pos['side']:<6}  "
                    f"{pos['quantity']:>8.0f}  "
                    f"{pos['avg_cost']:>10.2f}  "
                    f"{pos['market_price']:>10.2f}  "
                    f"{pos['market_value']:>12,.2f}  "
                    f"{pos['unrealized_pnl']:>+10.2f}"
                )
        else:
            print("\n  No open positions.")

        # Alerts
        alerts = self.check_alerts()
        if alerts:
            print(f"\n  {'ACTIVE ALERTS':}")
            print("  " + "-" * 50)
            for alert in alerts:
                print(f"  {alert}")

        print("=" * 70 + "\n")

    # ------------------------------------------------------------------
    # Dashboard data
    # ------------------------------------------------------------------

    def get_dashboard_data(self) -> dict[str, Any]:
        """
        Return structured data suitable for a Streamlit or similar dashboard.

        Returns
        -------
        dict[str, Any]
            Comprehensive state dictionary with the following sections:

            * ``portfolio`` — equity, cash, P&L, drawdown, leverage
            * ``positions`` — list of open position dicts
            * ``broker_account`` — broker-side account snapshot (or None)
            * ``alerts`` — list of alert strings
            * ``regime`` — current volatility regime (placeholder)
            * ``meta`` — update timestamp, update count
        """
        if self._portfolio_snapshot is None:
            return {
                "portfolio": {},
                "positions": [],
                "broker_account": None,
                "alerts": ["No data available — call update() first"],
                "meta": {
                    "last_update": None,
                    "update_count": self._update_count,
                    "data_available": False,
                },
            }

        snap = self._portfolio_snapshot
        alerts = self.check_alerts()

        portfolio_summary = {
            "equity": snap.get("equity", 0.0),
            "cash": snap.get("cash", 0.0),
            "positions_value": snap.get("positions_value", 0.0),
            "daily_pnl": snap.get("daily_pnl", 0.0),
            "total_pnl": snap.get("total_pnl", 0.0),
            "total_return_pct": snap.get("total_return_pct", 0.0),
            "realized_pnl": snap.get("realized_pnl", 0.0),
            "unrealized_pnl": snap.get("unrealized_pnl", 0.0),
            "drawdown_pct": snap.get("drawdown_pct", 0.0),
            "max_drawdown_pct": snap.get("max_drawdown_pct", 0.0),
            "leverage": snap.get("leverage", 0.0),
            "n_open_positions": len(snap.get("positions", [])),
        }

        return {
            "portfolio": portfolio_summary,
            "positions": snap.get("positions", []),
            "broker_account": self._account_snapshot,
            "alerts": alerts,
            "alert_count": len(alerts),
            "has_critical_alerts": any("CRITICAL" in a for a in alerts),
            "meta": {
                "last_update": self._last_update.isoformat() if self._last_update else None,
                "update_count": self._update_count,
                "data_available": True,
            },
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def last_update(self) -> Optional[datetime]:
        """Timestamp of the most recent :meth:`update` call."""
        return self._last_update

    @property
    def is_stale(self) -> bool:
        """
        True if no update has been received in the last 10 minutes.

        This typically indicates the monitoring loop has stopped or data
        connectivity has been lost.
        """
        if self._last_update is None:
            return True
        age = (datetime.now(tz=timezone.utc) - self._last_update).total_seconds()
        return age > 600  # 10 minutes

    def __repr__(self) -> str:
        updates = self._update_count
        last = self._last_update.isoformat() if self._last_update else "never"
        return (
            f"TradingMonitor(updates={updates}, last_update={last}, "
            f"max_drawdown={self.max_drawdown_alert:.2%})"
        )


__all__ = ["TradingMonitor"]
