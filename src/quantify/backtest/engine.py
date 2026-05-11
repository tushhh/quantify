"""
quantify.backtest.engine
~~~~~~~~~~~~~~~~~~~~~~~~
Hybrid event-driven backtesting engine for the Quantify trading system.

Architecture
------------
The engine walks day-by-day through a date range, orchestrating:

1. Feature pre-computation  — FeatureEngine computes all required derived
   columns once before the main loop starts.
2. Stop evaluation          — StopManager checks per-bar whether any stop
   is triggered and emits close signals.
3. Signal generation        — each Strategy's generate_signals() is called
   at its configured rebalance frequency.
4. Risk filtering           — PortfolioRiskManager.apply_risk_adjustments()
   filters signals against portfolio-level limits.
5. Position sizing          — PositionSizer.calculate_size() converts each
   signal into a share count.
6. Order creation           — Orders are submitted to the SimulatedBroker.
7. Bar processing           — SimulatedBroker.process_bar() fills pending
   orders and marks positions to market.
8. Portfolio update         — Portfolio tracks equity, P&L, and positions.
9. Snapshot recording       — Equity, trades, and signals are logged for
   the BacktestResult.

No-look-ahead guarantee
-----------------------
Signals are generated using data up to (but not including) the current bar.
The current bar's OHLCV is only used for order filling inside process_bar().

Usage
-----
    engine = BacktestEngine(
        strategies=[my_strategy],
        initial_capital=100_000,
    )
    result = engine.run(data={"AAPL": df_aapl, "MSFT": df_msft})
    print(result.equity_curve.tail())
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from quantify.backtest.costs import CostModel
from quantify.data.features import FeatureEngine
from quantify.execution.broker.simulated import BarData, SimulatedBroker
from quantify.execution.order import Order, OrderSide, OrderStatus, OrderType
from quantify.execution.portfolio import Portfolio
from quantify.risk.portfolio_risk import PortfolioRiskManager
from quantify.risk.position_sizer import EqualWeightSizer, MarketData, PositionSizer
from quantify.risk.stop_manager import StopManager, StopType
from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BacktestResult
# ---------------------------------------------------------------------------


@dataclass
class BacktestResult:
    """
    Container for all outputs produced by a completed backtest run.

    Attributes
    ----------
    equity_curve:
        Daily equity values indexed by date.
    trades:
        List of completed round-trip trade records.  Each record is a dict
        with keys: symbol, strategy_name, entry_date, exit_date, entry_price,
        exit_price, quantity, pnl, return_pct, holding_days.
    daily_returns:
        Daily portfolio returns (pct change of equity curve).
    signals_log:
        Every signal generated during the backtest (list of dicts).
    portfolio_snapshots:
        End-of-day portfolio snapshots (list of dicts from Portfolio.snapshot()).
    metadata:
        Run-level metadata: start, end, initial_capital, strategy names, etc.
    fills:
        All Fill objects accumulated during the run.
    """

    equity_curve: pd.Series
    trades: list[dict]
    daily_returns: pd.Series
    signals_log: list[dict]
    portfolio_snapshots: list[dict]
    metadata: dict[str, Any]
    fills: list = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience analytics computed on demand
    # ------------------------------------------------------------------

    @property
    def total_return(self) -> float:
        """Total return as a decimal (e.g. 0.15 = 15%)."""
        if len(self.equity_curve) < 2:
            return 0.0
        return (self.equity_curve.iloc[-1] / self.equity_curve.iloc[0]) - 1.0

    @property
    def annualized_return(self) -> float:
        """Annualised return assuming 252 trading days per year."""
        n_days = max(len(self.equity_curve) - 1, 1)
        total_ret = self.total_return
        if total_ret <= -1.0:
            return -1.0
        years = n_days / 252.0
        return (1.0 + total_ret) ** (1.0 / years) - 1.0

    @property
    def sharpe_ratio(self) -> float:
        """Annualised Sharpe ratio (risk-free rate = 0)."""
        if len(self.daily_returns) < 2:
            return 0.0
        rets = self.daily_returns.dropna()
        if rets.std() == 0:
            return 0.0
        return float((rets.mean() / rets.std()) * math.sqrt(252))

    @property
    def max_drawdown(self) -> float:
        """Maximum peak-to-trough drawdown as a fraction (0.0 – 1.0)."""
        if len(self.equity_curve) < 2:
            return 0.0
        cum_max = self.equity_curve.cummax()
        drawdowns = (self.equity_curve - cum_max) / cum_max
        return float(drawdowns.min()) * -1.0  # return as positive

    @property
    def win_rate(self) -> float:
        """Fraction of completed trades that are profitable."""
        if not self.trades:
            return 0.0
        winning = sum(1 for t in self.trades if t.get("pnl", 0) > 0)
        return winning / len(self.trades)

    @property
    def profit_factor(self) -> float:
        """Gross profit / gross loss."""
        gross_profit = sum(t["pnl"] for t in self.trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t["pnl"] for t in self.trades if t.get("pnl", 0) < 0))
        return gross_profit / gross_loss if gross_loss > 0 else float("inf")

    def __repr__(self) -> str:
        start = self.metadata.get("start", "?")
        end = self.metadata.get("end", "?")
        return (
            f"BacktestResult(start={start}, end={end}, "
            f"total_return={self.total_return:.2%}, "
            f"sharpe={self.sharpe_ratio:.3f}, "
            f"max_dd={self.max_drawdown:.2%}, "
            f"trades={len(self.trades)})"
        )


# ---------------------------------------------------------------------------
# PortfolioAdapter — bridges Portfolio to the PositionSizer's expected API
# ---------------------------------------------------------------------------


class _PortfolioAdapter:
    """Thin adapter exposing 'nav' so PositionSizer protocols are satisfied."""

    def __init__(self, portfolio: Portfolio) -> None:
        self._portfolio = portfolio

    @property
    def nav(self) -> float:
        return self._portfolio.equity

    @property
    def cash(self) -> float:
        return self._portfolio.cash

    @property
    def positions(self) -> dict:
        return self._portfolio.positions


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------


class BacktestEngine:
    """
    Hybrid event-driven / vectorised backtesting engine.

    Parameters
    ----------
    strategies:
        One or more :class:`~quantify.strategy.base.Strategy` instances.
        They run simultaneously and share a single portfolio.
    initial_capital:
        Starting cash balance in USD (default: 100,000).
    cost_model:
        :class:`~quantify.backtest.costs.CostModel` instance.  Defaults
        to the standard retail model ($0.005/share, 5 bps spread, 10 bps
        market impact).
    position_sizer:
        :class:`~quantify.risk.position_sizer.PositionSizer` instance.
        Defaults to :class:`~quantify.risk.position_sizer.EqualWeightSizer`
        with ``max_position_pct=0.10``.
    risk_manager:
        Optional :class:`~quantify.risk.portfolio_risk.PortfolioRiskManager`.
        When provided, signals are filtered through risk checks before sizing.
    stop_manager:
        Optional :class:`~quantify.risk.stop_manager.StopManager`.  When
        provided, stops are evaluated and updated on each bar.
    start_date:
        Inclusive start date for the backtest.  If ``None``, uses the
        earliest date available across all data.
    end_date:
        Inclusive end date for the backtest.  If ``None``, uses the latest
        date available across all data.
    benchmark_symbol:
        Symbol used for benchmark comparison in reports (default: ``"SPY"``).
        Must be present in the data dict passed to :meth:`run`.
    """

    def __init__(
        self,
        strategies: list[Strategy],
        initial_capital: float = 100_000.0,
        cost_model: Optional[CostModel] = None,
        position_sizer: Optional[PositionSizer] = None,
        risk_manager: Optional[PortfolioRiskManager] = None,
        stop_manager: Optional[StopManager] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        benchmark_symbol: str = "SPY",
    ) -> None:
        if not strategies:
            raise ValueError("BacktestEngine requires at least one strategy")
        if initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {initial_capital}")

        self.strategies = strategies
        self.initial_capital = initial_capital
        self.cost_model = cost_model or CostModel()
        self.position_sizer = position_sizer or EqualWeightSizer(max_position_pct=0.10)
        self.risk_manager = risk_manager
        self.stop_manager = stop_manager
        self.start_date = start_date
        self.end_date = end_date
        self.benchmark_symbol = benchmark_symbol

        # Validate all strategies
        for strat in self.strategies:
            strat.validate()

        log.info(
            "BacktestEngine initialised: %d strategies, capital=%.2f",
            len(strategies), initial_capital,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, data: dict[str, pd.DataFrame]) -> BacktestResult:
        """
        Execute the backtest over the provided data.

        Parameters
        ----------
        data:
            Mapping of ``{symbol: DataFrame}`` where each DataFrame has a
            DatetimeIndex and at minimum the columns ``open``, ``high``,
            ``low``, ``close``, ``volume``.

        Returns
        -------
        BacktestResult
            Full result object with equity curve, trades, returns, and metadata.
        """
        if not data:
            raise ValueError("data must contain at least one symbol")

        log.info("BacktestEngine.run: preparing data for %d symbols", len(data))
        data = self._clean_data(data)

        # Compute features for all strategies
        data = self._precompute_features(data)

        # Determine backtest date range
        trading_dates = self._get_trading_dates(data)
        if len(trading_dates) == 0:
            raise ValueError("No trading dates found in data after filtering")

        log.info(
            "BacktestEngine.run: %d trading days from %s to %s",
            len(trading_dates), trading_dates[0], trading_dates[-1],
        )

        # Initialise portfolio, broker, accumulators
        portfolio = Portfolio(initial_capital=self.initial_capital)
        # Pass the cost_model to the simulated broker (it implements the same interface)
        broker = SimulatedBroker(
            initial_capital=self.initial_capital,
            cost_model=self.cost_model,  # type: ignore[arg-type]
        )
        broker.register_fill_callback(portfolio.update_from_fill)

        # Call lifecycle hooks
        for strat in self.strategies:
            strat.on_start()

        # Per-strategy fill callbacks
        for strat in self.strategies:
            broker.register_fill_callback(
                lambda fill, s=strat: s.on_fill(fill) if fill.strategy_name == s.name else None
            )

        # Accumulators
        equity_by_date: dict[date, float] = {}
        signals_log: list[dict] = []
        portfolio_snapshots: list[dict] = []
        open_trades: dict[str, dict] = {}  # symbol -> open trade record
        closed_trades: list[dict] = []
        all_fills: list = []

        # Track which orders came from which strategy for P&L attribution
        pending_order_strategy: dict[str, str] = {}

        for current_date in trading_dates:
            current_ts = datetime.combine(current_date, datetime.min.time()).replace(
                tzinfo=timezone.utc
            )

            # ---- 1. Collect current close prices for all symbols ----
            current_prices: dict[str, float] = {}
            for symbol, df in data.items():
                try:
                    price = self._get_close_price(df, current_date)
                    if price is not None and price > 0:
                        current_prices[symbol] = price
                except Exception as exc:
                    log.debug("Could not get price for %s on %s: %s", symbol, current_date, exc)

            if not current_prices:
                log.debug("No prices available on %s, skipping", current_date)
                continue

            # ---- 2. Check stops (before new signals, using current prices) ----
            stop_signals: list[Signal] = []
            if self.stop_manager is not None:
                try:
                    stop_signals = self.stop_manager.check_stops(
                        current_prices, current_time=current_ts
                    )
                    if stop_signals:
                        log.debug(
                            "%s: %d stop signal(s) triggered",
                            current_date, len(stop_signals),
                        )
                except Exception as exc:
                    log.warning("stop_manager.check_stops failed on %s: %s", current_date, exc)

            # ---- 3. Process bar for all symbols (fills pending orders) ----
            bar_fills: list = []
            for symbol, df in data.items():
                try:
                    bar = self._make_bar_data(df, current_date, symbol, current_ts)
                    if bar is not None:
                        fills = broker.process_bar(bar)
                        bar_fills.extend(fills)
                        all_fills.extend(fills)
                except Exception as exc:
                    log.warning(
                        "process_bar failed for %s on %s: %s", symbol, current_date, exc
                    )

            # Record fills for trade tracking
            for fill in bar_fills:
                self._update_open_trades(
                    fill, open_trades, closed_trades, current_date
                )

            # Update trailing stops
            if self.stop_manager is not None:
                try:
                    self.stop_manager.update_trailing(current_prices)
                except Exception as exc:
                    log.debug("update_trailing failed on %s: %s", current_date, exc)

            # ---- 4. Generate strategy signals ----
            strategy_signals: list[Signal] = []
            for strat in self.strategies:
                if not self._should_rebalance(strat, current_date, trading_dates):
                    continue
                try:
                    window_data = self._slice_lookback(data, current_date, strat.lookback_days)
                    if not window_data:
                        log.debug(
                            "%s: insufficient data window on %s, skipping signals",
                            strat.name, current_date,
                        )
                        continue
                    signals = strat.generate_signals(window_data)
                    # Stamp timestamp if not already set
                    stamped: list[Signal] = []
                    for sig in signals:
                        stamped.append(sig)
                    strategy_signals.extend(stamped)
                    log.debug(
                        "%s on %s: generated %d signal(s)",
                        strat.name, current_date, len(signals),
                    )
                except Exception as exc:
                    log.warning(
                        "Strategy %s failed on %s: %s", strat.name, current_date, exc
                    )

            # Apply volatility regime adjustment if available
            regime_strategy = None
            for strat in self.strategies:
                if strat.__class__.__name__ == "VolatilityRegimeStrategy":
                    regime_strategy = strat
                    break
            
            if regime_strategy is not None and strategy_signals:
                try:
                    strategy_signals = regime_strategy.adjust_signals(strategy_signals)
                    log.debug(
                        "VolatilityRegimeStrategy adjusted %d signal(s) on %s",
                        len(strategy_signals), current_date,
                    )
                except Exception as exc:
                    log.warning(
                        "VolatilityRegimeStrategy.adjust_signals failed on %s: %s",
                        current_date, exc,
                    )

            # Combine stop signals with strategy signals
            all_signals = stop_signals + strategy_signals

            # Log signals
            for sig in all_signals:
                signals_log.append({
                    "date": current_date,
                    "strategy": sig.strategy_name,
                    "symbol": sig.symbol,
                    "direction": sig.direction,
                    "strength": sig.strength,
                    "metadata": sig.metadata,
                })

            # ---- 5. Risk filtering ----
            if self.risk_manager is not None and all_signals:
                try:
                    portfolio_adapter = _PortfolioAdapter(portfolio)
                    # Build returns data for correlation check
                    returns_data = self._build_returns_df(data, current_date, window=60)
                    all_signals = self.risk_manager.apply_risk_adjustments(
                        all_signals,
                        portfolio_adapter,
                        returns_data=returns_data if not returns_data.empty else None,
                    )
                except Exception as exc:
                    log.warning(
                        "risk_manager.apply_risk_adjustments failed on %s: %s",
                        current_date, exc,
                    )

            # ---- 6. Size and submit orders ----
            if all_signals:
                entry_signals = [s for s in all_signals if s.direction in ("long", "short")]
                n_entry = len(entry_signals)

                market_data = MarketData(
                    prices={
                        sym: df["close"][df.index.date <= current_date]
                        for sym, df in data.items()
                        if len(df[df.index.date <= current_date]) > 0
                    },
                    current_prices=current_prices,
                )
                portfolio_adapter = _PortfolioAdapter(portfolio)

                for sig in all_signals:
                    try:
                        self._process_signal(
                            sig,
                            portfolio,
                            broker,
                            portfolio_adapter,
                            market_data,
                            current_ts,
                            n_entry,
                        )
                    except Exception as exc:
                        log.warning(
                            "Failed to process signal %s on %s: %s", sig, current_date, exc
                        )

            # ---- 7. Update portfolio market prices (end-of-day MTM) ----
            try:
                portfolio.update_market_prices(current_prices, timestamp=current_ts)
            except Exception as exc:
                log.warning("update_market_prices failed on %s: %s", current_date, exc)

            # ---- 8. Record equity snapshot ----
            equity_by_date[current_date] = portfolio.equity
            portfolio_snapshots.append({
                "date": current_date,
                **portfolio.snapshot(),
            })

        # ---- Lifecycle cleanup ----
        for strat in self.strategies:
            strat.on_stop()

        # Close any remaining open trades at last known price
        last_prices = {}
        for symbol, df in data.items():
            if len(df) > 0:
                last_prices[symbol] = float(df["close"].iloc[-1])
        for symbol, trade in list(open_trades.items()):
            price = last_prices.get(symbol, trade.get("entry_price", 0.0))
            trade["exit_date"] = trading_dates[-1] if trading_dates else None
            trade["exit_price"] = price
            qty = trade.get("quantity", 0.0)
            entry_p = trade.get("entry_price", price)
            side = trade.get("side", "long")
            if side == "long":
                trade["pnl"] = qty * (price - entry_p)
            else:
                trade["pnl"] = qty * (entry_p - price)
            trade["return_pct"] = trade["pnl"] / (qty * entry_p) if qty * entry_p != 0 else 0.0
            if trade.get("entry_date") and trade.get("exit_date"):
                trade["holding_days"] = (trade["exit_date"] - trade["entry_date"]).days
            closed_trades.append(trade)

        # Build results
        equity_series = pd.Series(equity_by_date, name="equity")
        equity_series.index = pd.DatetimeIndex(equity_series.index)
        equity_series = equity_series.sort_index()

        daily_returns = equity_series.pct_change().dropna()
        daily_returns.name = "returns"

        result = BacktestResult(
            equity_curve=equity_series,
            trades=closed_trades,
            daily_returns=daily_returns,
            signals_log=signals_log,
            portfolio_snapshots=portfolio_snapshots,
            fills=all_fills,
            metadata={
                "start": trading_dates[0] if trading_dates else None,
                "end": trading_dates[-1] if trading_dates else None,
                "initial_capital": self.initial_capital,
                "final_equity": equity_series.iloc[-1] if len(equity_series) > 0 else self.initial_capital,
                "strategies": [s.name for s in self.strategies],
                "symbols": list(data.keys()),
                "n_trading_days": len(trading_dates),
                "cost_model": repr(self.cost_model),
            },
        )

        log.info(
            "BacktestEngine.run completed: total_return=%.2f%% sharpe=%.3f max_dd=%.2f%%",
            result.total_return * 100,
            result.sharpe_ratio,
            result.max_drawdown * 100,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clean_data(self, data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """
        Normalise column names, parse datetimes, sort, and drop bad rows.
        Filters to [start_date, end_date] if provided.
        """
        cleaned: dict[str, pd.DataFrame] = {}
        required_cols = {"open", "high", "low", "close", "volume"}

        for symbol, df in data.items():
            df = df.copy()
            df.columns = [c.lower().strip() for c in df.columns]

            missing = required_cols - set(df.columns)
            if missing:
                log.warning("Symbol %s missing columns %s — skipping", symbol, missing)
                continue

            # Ensure DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                try:
                    df.index = pd.to_datetime(df.index)
                except Exception as exc:
                    log.warning("Symbol %s: cannot parse index as datetime: %s", symbol, exc)
                    continue

            # Sort ascending
            df = df.sort_index()

            # Drop rows with NaN in key price columns
            df = df.dropna(subset=["open", "high", "low", "close"])

            # Drop zero-price rows
            df = df[(df["close"] > 0) & (df["open"] > 0)]

            # Apply date range filter
            if self.start_date is not None:
                df = df[df.index.date >= self.start_date]
            if self.end_date is not None:
                df = df[df.index.date <= self.end_date]

            if df.empty:
                log.warning("Symbol %s has no data after filtering — skipping", symbol)
                continue

            cleaned[symbol] = df
            log.debug("Symbol %s: %d bars after cleaning", symbol, len(df))

        return cleaned

    def _precompute_features(self, data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        """Compute all features required by registered strategies."""
        required: set[str] = set()
        for strat in self.strategies:
            try:
                required.update(strat.get_required_features())
            except Exception as exc:
                log.warning("get_required_features failed for %s: %s", strat.name, exc)

        if not required:
            log.debug("No features required by any strategy")
            return data

        log.info("Pre-computing features: %s", sorted(required))
        engine = FeatureEngine()
        enriched: dict[str, pd.DataFrame] = {}
        for symbol, df in data.items():
            try:
                result = engine.compute({symbol: df}, required=list(required))
                # Merge computed features into the original OHLCV DataFrame
                # so that price columns (open, high, low, close, volume) are
                # preserved alongside the new feature columns.
                features_df = result[symbol]
                merged = df.join(features_df, how="left", rsuffix="_feat")
                enriched[symbol] = merged
            except Exception as exc:
                log.warning("Feature computation failed for %s: %s — using raw data", symbol, exc)
                enriched[symbol] = df

        return enriched

    def _get_trading_dates(self, data: dict[str, pd.DataFrame]) -> list[date]:
        """Return sorted list of unique trading dates across all symbols."""
        all_dates: set[date] = set()
        for df in data.values():
            all_dates.update(df.index.date)

        sorted_dates = sorted(all_dates)

        # Apply engine-level date range filter
        if self.start_date:
            sorted_dates = [d for d in sorted_dates if d >= self.start_date]
        if self.end_date:
            sorted_dates = [d for d in sorted_dates if d <= self.end_date]

        return sorted_dates

    def _get_close_price(self, df: pd.DataFrame, target_date: date) -> Optional[float]:
        """Return the close price on or before target_date."""
        mask = df.index.date <= target_date
        sub = df[mask]
        if sub.empty:
            return None
        return float(sub["close"].iloc[-1])

    def _make_bar_data(
        self,
        df: pd.DataFrame,
        target_date: date,
        symbol: str,
        timestamp: datetime,
    ) -> Optional[BarData]:
        """Create a BarData object for the given date if data exists."""
        mask = df.index.date == target_date
        sub = df[mask]
        if sub.empty:
            return None
        row = sub.iloc[0]
        try:
            return BarData(
                symbol=symbol,
                timestamp=timestamp,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
            )
        except Exception as exc:
            log.debug("Cannot create BarData for %s on %s: %s", symbol, target_date, exc)
            return None

    def _slice_lookback(
        self,
        data: dict[str, pd.DataFrame],
        current_date: date,
        lookback_days: int,
    ) -> dict[str, pd.DataFrame]:
        """
        Return a window of data up to (but NOT including) current_date to
        prevent look-ahead bias.
        """
        result: dict[str, pd.DataFrame] = {}
        for symbol, df in data.items():
            # Exclude current date — signals are generated from previous bars
            hist = df[df.index.date < current_date]
            if hist.empty or len(hist) < 2:
                continue
            # Trim to lookback window
            if len(hist) > lookback_days:
                hist = hist.iloc[-lookback_days:]
            result[symbol] = hist
        return result

    def _should_rebalance(
        self,
        strategy: Strategy,
        current_date: date,
        all_dates: list[date],
    ) -> bool:
        """Return True if this strategy should generate signals today."""
        freq = strategy.rebalance_frequency
        if freq == "daily":
            return True
        if freq == "weekly":
            # Monday (weekday == 0) or first trading day of the week
            if current_date.weekday() == 0:
                return True
            # If Monday is not a trading day, use the first available day
            idx = all_dates.index(current_date)
            if idx == 0:
                return True
            prev = all_dates[idx - 1]
            return prev.isocalendar()[1] != current_date.isocalendar()[1]
        if freq == "monthly":
            # First trading day of the month
            idx = all_dates.index(current_date)
            if idx == 0:
                return True
            prev = all_dates[idx - 1]
            return prev.month != current_date.month or prev.year != current_date.year
        return True

    def _process_signal(
        self,
        sig: Signal,
        portfolio: Portfolio,
        broker: SimulatedBroker,
        portfolio_adapter: _PortfolioAdapter,
        market_data: MarketData,
        timestamp: datetime,
        n_entry_signals: int,
    ) -> None:
        """Convert a signal to an order and submit it to the broker."""
        symbol = sig.symbol
        current_price = market_data.current_price(symbol)
        if current_price is None or current_price <= 0:
            log.debug("No current price for %s — cannot process signal", symbol)
            return

        current_position = portfolio.get_position_quantity(symbol)

        # ---- Close signal: exit full position ----
        if sig.direction == "close":
            if abs(current_position) < 1e-9:
                log.debug("Close signal for %s but no open position", symbol)
                return
            side = OrderSide.SELL if current_position > 0 else OrderSide.BUY
            qty = abs(current_position)
            order = Order(
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET,
                quantity=qty,
                strategy_name=sig.strategy_name,
            )
            try:
                broker.submit_order(order)
                # Remove stops for closed position
                if self.stop_manager is not None:
                    self.stop_manager.remove_stops(symbol)
                log.debug("Close order submitted: %s qty=%.0f", symbol, qty)
            except Exception as exc:
                log.warning("Failed to submit close order for %s: %s", symbol, exc)
            return

        # ---- Entry/direction signal ----
        desired_side = OrderSide.BUY if sig.direction == "long" else OrderSide.SELL

        # Compute target position size via the sizer
        try:
            # Update n_signals in EqualWeightSizer if applicable
            if hasattr(self.position_sizer, "n_signals"):
                self.position_sizer.n_signals = max(n_entry_signals, 1)
            if hasattr(self.position_sizer, "n_positions"):
                self.position_sizer.n_positions = max(n_entry_signals, 1)

            target_shares = self.position_sizer.calculate_size(
                sig, portfolio_adapter, market_data
            )
        except Exception as exc:
            log.warning("position_sizer failed for %s: %s", symbol, exc)
            return

        if target_shares == 0:
            log.debug("Sizer returned 0 for %s — no order placed", symbol)
            return

        # If already in a position in the same direction, skip (no pyramiding by default)
        if current_position > 0 and target_shares > 0:
            log.debug(
                "Already long %s (qty=%.0f) — skipping additional entry", symbol, current_position
            )
            return
        if current_position < 0 and target_shares < 0:
            log.debug(
                "Already short %s (qty=%.0f) — skipping additional entry", symbol, current_position
            )
            return

        # If reversing direction, close the existing position first
        if current_position != 0:
            close_side = OrderSide.SELL if current_position > 0 else OrderSide.BUY
            close_order = Order(
                symbol=symbol,
                side=close_side,
                order_type=OrderType.MARKET,
                quantity=abs(current_position),
                strategy_name=sig.strategy_name,
            )
            try:
                broker.submit_order(close_order)
                if self.stop_manager is not None:
                    self.stop_manager.remove_stops(symbol)
            except Exception as exc:
                log.warning("Failed to submit reversal close for %s: %s", symbol, exc)

        # Submit the new entry order
        qty = abs(target_shares)
        if qty < 1:
            log.debug("Calculated qty=%.2f < 1 for %s — no order placed", qty, symbol)
            return

        order = Order(
            symbol=symbol,
            side=desired_side,
            order_type=OrderType.MARKET,
            quantity=math.floor(qty),
            strategy_name=sig.strategy_name,
        )
        try:
            broker.submit_order(order)
            log.debug(
                "Entry order submitted: %s %s qty=%.0f @ ~%.4f",
                desired_side.value, symbol, qty, current_price,
            )
        except Exception as exc:
            log.warning("Failed to submit entry order for %s: %s", symbol, exc)

    def _update_open_trades(
        self,
        fill,
        open_trades: dict[str, dict],
        closed_trades: list[dict],
        current_date: date,
    ) -> None:
        """Track open/closed round-trip trades from fills."""
        symbol = fill.symbol
        qty = fill.quantity
        price = fill.price

        if fill.side == OrderSide.BUY:
            if symbol not in open_trades:
                # Opening a long position
                open_trades[symbol] = {
                    "symbol": symbol,
                    "strategy_name": fill.strategy_name,
                    "side": "long",
                    "entry_date": current_date,
                    "entry_price": price,
                    "quantity": qty,
                    "exit_date": None,
                    "exit_price": None,
                    "pnl": None,
                    "return_pct": None,
                    "holding_days": None,
                    "commission": fill.commission,
                }
            else:
                # Closing a short position
                trade = open_trades.pop(symbol)
                trade["exit_date"] = current_date
                trade["exit_price"] = price
                trade["pnl"] = trade["quantity"] * (trade["entry_price"] - price) - fill.commission - trade.get("commission", 0)
                ep = trade["entry_price"]
                trade["return_pct"] = trade["pnl"] / (trade["quantity"] * ep) if ep > 0 else 0.0
                trade["holding_days"] = (current_date - trade["entry_date"]).days if trade["entry_date"] else 0
                closed_trades.append(trade)

        else:  # SELL
            if symbol not in open_trades:
                # Opening a short position
                open_trades[symbol] = {
                    "symbol": symbol,
                    "strategy_name": fill.strategy_name,
                    "side": "short",
                    "entry_date": current_date,
                    "entry_price": price,
                    "quantity": qty,
                    "exit_date": None,
                    "exit_price": None,
                    "pnl": None,
                    "return_pct": None,
                    "holding_days": None,
                    "commission": fill.commission,
                }
            else:
                # Closing a long position
                trade = open_trades.pop(symbol)
                trade["exit_date"] = current_date
                trade["exit_price"] = price
                trade["pnl"] = trade["quantity"] * (price - trade["entry_price"]) - fill.commission - trade.get("commission", 0)
                ep = trade["entry_price"]
                trade["return_pct"] = trade["pnl"] / (trade["quantity"] * ep) if ep > 0 else 0.0
                trade["holding_days"] = (current_date - trade["entry_date"]).days if trade["entry_date"] else 0
                closed_trades.append(trade)

    def _build_returns_df(
        self,
        data: dict[str, pd.DataFrame],
        current_date: date,
        window: int = 60,
    ) -> pd.DataFrame:
        """Build a returns DataFrame for the risk manager's correlation check."""
        close_frames: dict[str, pd.Series] = {}
        for symbol, df in data.items():
            hist = df[df.index.date < current_date]["close"]
            if len(hist) > 1:
                close_frames[symbol] = hist.iloc[-window:] if len(hist) > window else hist

        if not close_frames:
            return pd.DataFrame()

        prices_df = pd.DataFrame(close_frames)
        return prices_df.pct_change().dropna(how="all")


__all__ = ["BacktestEngine", "BacktestResult"]
