"""
quantify.persistence.trade_log
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Trade, signal, and portfolio snapshot logging backed by SQLite.

The :class:`TradeLogger` wraps a :class:`~quantify.persistence.database.Database`
and provides a high-level API for recording the full audit trail of the live
trading system:

* Individual fills (trades)
* Strategy signals
* Periodic portfolio snapshots for equity-curve reconstruction
* Query helpers for P&L analysis and reporting

All timestamps are stored as ISO-8601 strings in UTC so they remain portable
across environments.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from quantify.persistence.database import Database
from quantify.strategy.signal import Signal
from quantify.execution.portfolio import Portfolio

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    """Convert a datetime to ISO-8601 string, or return None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# TradeLogger
# ---------------------------------------------------------------------------


class TradeLogger:
    """
    High-level trade and event logging backed by SQLite.

    Parameters
    ----------
    db:
        An initialised :class:`~quantify.persistence.database.Database`
        instance.  The caller is responsible for calling ``db.initialize()``
        before constructing a ``TradeLogger``.

    Examples
    --------
    ::

        db = Database()
        db.initialize()
        logger = TradeLogger(db)

        logger.log_trade(
            strategy="momentum",
            symbol="AAPL",
            side="buy",
            quantity=100,
            price=175.50,
            commission=0.0,
            order_id="ord-001",
            fill_id="fill-001",
        )
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def log_trade(
        self,
        strategy: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        order_id: Optional[str] = None,
        fill_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """
        Record a filled trade in the ``trades`` table.

        Parameters
        ----------
        strategy:
            Name of the strategy that originated the order.
        symbol:
            Ticker symbol (e.g. ``"AAPL"``).
        side:
            ``"buy"`` or ``"sell"``.
        quantity:
            Number of shares executed.
        price:
            Execution price per share.
        commission:
            Commission charged for this fill.
        order_id:
            Internal order ID from the order manager.
        fill_id:
            Broker-assigned fill identifier.
        timestamp:
            Fill timestamp.  Defaults to ``datetime.now(UTC)``.

        Returns
        -------
        int
            The auto-assigned row ID (``lastrowid``).
        """
        ts = _to_iso(timestamp) or _now_iso()
        sql = """
            INSERT INTO trades
                (strategy, symbol, side, quantity, price, commission,
                 timestamp, order_id, fill_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self._db.execute(
            sql,
            (strategy, symbol, side.lower(), quantity, price, commission, ts, order_id, fill_id),
        )
        row_id = cursor.lastrowid
        log.debug(
            "TradeLogger.log_trade: id=%d %s %s x%.2f @ %.4f",
            row_id, side.upper(), symbol, quantity, price,
        )
        return row_id

    def log_signal(self, signal: Signal) -> int:
        """
        Record a strategy signal in the ``signals_log`` table.

        Parameters
        ----------
        signal:
            The :class:`~quantify.strategy.signal.Signal` to record.

        Returns
        -------
        int
            The auto-assigned row ID.
        """
        sql = """
            INSERT INTO signals_log
                (timestamp, strategy, symbol, direction, strength, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        metadata_json = json.dumps(signal.metadata)
        ts = _to_iso(signal.timestamp) or _now_iso()
        cursor = self._db.execute(
            sql,
            (ts, signal.strategy_name, signal.symbol,
             signal.direction, signal.strength, metadata_json),
        )
        row_id = cursor.lastrowid
        log.debug(
            "TradeLogger.log_signal: id=%d %s %s %s strength=%.3f",
            row_id, signal.strategy_name, signal.symbol, signal.direction, signal.strength,
        )
        return row_id

    def log_portfolio_snapshot(self, portfolio: Portfolio) -> int:
        """
        Record a portfolio state snapshot in the ``portfolio_snapshots`` table.

        Parameters
        ----------
        portfolio:
            The :class:`~quantify.execution.portfolio.Portfolio` to snapshot.

        Returns
        -------
        int
            The auto-assigned row ID.
        """
        snap = portfolio.snapshot()
        positions_json = json.dumps(snap.get("positions", []))
        sql = """
            INSERT INTO portfolio_snapshots
                (timestamp, total_value, cash, positions_json, daily_pnl, cumulative_pnl)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor = self._db.execute(
            sql,
            (
                _now_iso(),
                snap["equity"],
                snap["cash"],
                positions_json,
                snap["daily_pnl"],
                snap["total_pnl"],
            ),
        )
        row_id = cursor.lastrowid
        log.debug(
            "TradeLogger.log_portfolio_snapshot: id=%d equity=%.2f daily_pnl=%.2f",
            row_id, snap["equity"], snap["daily_pnl"],
        )
        return row_id

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_trades(
        self,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve trade records with optional filters.

        Parameters
        ----------
        strategy:
            Filter by strategy name.
        symbol:
            Filter by ticker symbol.
        start:
            Include only trades at or after this timestamp.
        end:
            Include only trades at or before this timestamp.

        Returns
        -------
        list[dict[str, Any]]
            List of trade rows as dictionaries, ordered by timestamp ascending.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if strategy is not None:
            clauses.append("strategy = ?")
            params.append(strategy)
        if symbol is not None:
            clauses.append("symbol = ?")
            params.append(symbol)
        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(_to_iso(start))
        if end is not None:
            clauses.append("timestamp <= ?")
            params.append(_to_iso(end))

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM trades {where} ORDER BY timestamp ASC"
        return self._db.fetchall(sql, params)

    def get_daily_pnl(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.Series:
        """
        Return a daily P&L time series derived from portfolio snapshots.

        Takes the last ``daily_pnl`` value for each calendar day.

        Parameters
        ----------
        start:
            Earliest date to include.
        end:
            Latest date to include.

        Returns
        -------
        pd.Series
            Index: ``pd.DatetimeIndex`` (UTC, date-level), values: daily P&L in USD.
            Returns an empty Series if no snapshots exist.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(_to_iso(start))
        if end is not None:
            clauses.append("timestamp <= ?")
            params.append(_to_iso(end))

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT timestamp, daily_pnl FROM portfolio_snapshots {where} ORDER BY timestamp ASC"
        rows = self._db.fetchall(sql, params)

        if not rows:
            return pd.Series(dtype=float, name="daily_pnl")

        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["date"] = df["timestamp"].dt.date
        # Last snapshot value per day captures EOD P&L
        daily = df.groupby("date")["daily_pnl"].last()
        daily.index = pd.to_datetime(daily.index, utc=True)
        daily.name = "daily_pnl"
        return daily

    def get_trade_summary(self) -> dict[str, Any]:
        """
        Compute aggregate trade statistics.

        Returns
        -------
        dict[str, Any]
            A summary dictionary with the following keys:

            * ``total_trades`` — total number of completed fills
            * ``buy_trades`` — count of buy-side fills
            * ``sell_trades`` — count of sell-side fills
            * ``total_commission`` — sum of commissions paid
            * ``total_volume`` — total notional (sum of quantity × price)
            * ``strategies`` — list of distinct strategies that traded
            * ``symbols`` — list of distinct symbols traded
            * ``win_rate`` — fraction of sell trades with positive realised P&L
              (requires pairing buys and sells; approximated from snapshot data)
            * ``total_pnl`` — cumulative P&L from the latest snapshot
        """
        # Basic trade stats
        total_row = self._db.fetchone(
            "SELECT COUNT(*) AS cnt, SUM(commission) AS comm, "
            "SUM(quantity * price) AS vol FROM trades"
        ) or {}
        total_trades: int = int(total_row.get("cnt") or 0)
        total_commission: float = float(total_row.get("comm") or 0.0)
        total_volume: float = float(total_row.get("vol") or 0.0)

        side_rows = self._db.fetchall(
            "SELECT side, COUNT(*) AS cnt FROM trades GROUP BY side"
        )
        side_counts: dict[str, int] = {r["side"]: r["cnt"] for r in side_rows}

        strategy_rows = self._db.fetchall("SELECT DISTINCT strategy FROM trades")
        symbol_rows = self._db.fetchall("SELECT DISTINCT symbol FROM trades")

        # Cumulative P&L from latest snapshot
        latest_snap = self._db.fetchone(
            "SELECT cumulative_pnl FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        total_pnl = float(latest_snap["cumulative_pnl"]) if latest_snap else 0.0

        # Win rate: percentage of sell trades that close a position at a profit.
        # Compute as a simple approximation using average realized P&L sign from snapshots.
        win_rate: Optional[float] = self._estimate_win_rate()

        return {
            "total_trades": total_trades,
            "buy_trades": side_counts.get("buy", 0),
            "sell_trades": side_counts.get("sell", 0),
            "total_commission": total_commission,
            "total_volume": total_volume,
            "strategies": [r["strategy"] for r in strategy_rows],
            "symbols": [r["symbol"] for r in symbol_rows],
            "win_rate": win_rate,
            "total_pnl": total_pnl,
        }

    def _estimate_win_rate(self) -> Optional[float]:
        """
        Approximate win rate from the trades table using a simple FIFO P&L
        calculation per symbol.

        Returns None if insufficient data.
        """
        rows = self._db.fetchall(
            "SELECT symbol, side, quantity, price FROM trades ORDER BY timestamp ASC"
        )
        if not rows:
            return None

        # Build a FIFO cost-basis tracker per symbol
        from collections import deque

        wins = 0
        losses = 0

        buys: dict[str, deque[tuple[float, float]]] = {}  # symbol -> deque of (qty, price)

        for row in rows:
            sym = row["symbol"]
            side = row["side"]
            qty = float(row["quantity"])
            price = float(row["price"])

            if side == "buy":
                buys.setdefault(sym, deque()).append((qty, price))
            elif side == "sell":
                remaining_sell = qty
                avg_cost = 0.0
                total_cost_qty = 0.0
                buy_queue = buys.get(sym, deque())
                while remaining_sell > 1e-9 and buy_queue:
                    bqty, bprice = buy_queue[0]
                    used = min(bqty, remaining_sell)
                    avg_cost += bprice * used
                    total_cost_qty += used
                    remaining_sell -= used
                    if bqty <= remaining_sell + 1e-9:
                        buy_queue.popleft()
                    else:
                        buy_queue[0] = (bqty - used, bprice)
                if total_cost_qty > 1e-9:
                    avg_buy_price = avg_cost / total_cost_qty
                    pnl = (price - avg_buy_price) * (qty - remaining_sell)
                    if pnl > 0:
                        wins += 1
                    else:
                        losses += 1

        total_closed = wins + losses
        if total_closed == 0:
            return None
        return wins / total_closed

    # ------------------------------------------------------------------
    # Snapshot queries
    # ------------------------------------------------------------------

    def get_latest_snapshot(self) -> Optional[dict[str, Any]]:
        """
        Return the most recent portfolio snapshot row, or None.

        Returns
        -------
        dict[str, Any] or None
        """
        row = self._db.fetchone(
            "SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1"
        )
        if row is None:
            return None
        # Deserialize positions JSON
        try:
            row["positions"] = json.loads(row.get("positions_json", "[]"))
        except (json.JSONDecodeError, TypeError):
            row["positions"] = []
        return row

    def get_snapshots(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Return portfolio snapshots in chronological order.

        Parameters
        ----------
        start, end:
            Optional time window filter.
        limit:
            Maximum number of rows to return.

        Returns
        -------
        list[dict[str, Any]]
        """
        clauses: list[str] = []
        params: list[Any] = []
        if start is not None:
            clauses.append("timestamp >= ?")
            params.append(_to_iso(start))
        if end is not None:
            clauses.append("timestamp <= ?")
            params.append(_to_iso(end))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM portfolio_snapshots {where} ORDER BY timestamp ASC LIMIT ?"
        params.append(limit)
        rows = self._db.fetchall(sql, params)
        for row in rows:
            try:
                row["positions"] = json.loads(row.get("positions_json", "[]"))
            except (json.JSONDecodeError, TypeError):
                row["positions"] = []
        return rows

    def __repr__(self) -> str:
        return f"TradeLogger(db={self._db!r})"


__all__ = ["TradeLogger"]
