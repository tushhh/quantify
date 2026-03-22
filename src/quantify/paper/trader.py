"""
quantify.paper.trader
~~~~~~~~~~~~~~~~~~~~~~
Main paper-trading orchestrator for the Quantify trading system.

The :class:`PaperTrader` is the top-level entry point for running live paper
trades.  It wires together every subsystem — data, strategies, risk, execution,
persistence, and monitoring — and drives them through a structured daily
schedule.

Daily workflow
--------------
::

    09:00 ET  pre_market()             — fetch data, compute features, log status
    09:35 ET  generate_and_execute()   — signals → risk → sizing → orders
    09:30–    monitor()  (every 5 min) — check stops, update P&L
    16:00 ET
    15:55 ET  end_of_day()             — reconcile with broker, log summary

Signal aggregation
------------------
When multiple strategies emit signals for the same symbol, their strengths
are averaged.  The combined signal direction is determined by the sign of the
average strength (positive = long, negative = short, close signals always pass
through individually).

Error handling
--------------
Each phase (pre_market, generate_and_execute, monitor, end_of_day) catches
all exceptions internally.  A failure in one strategy or phase does not crash
the trading loop.

Usage
-----
::

    from quantify.paper.trader import PaperTrader
    from quantify.config import load_settings
    from quantify.execution.broker.alpaca_broker import AlpacaBroker
    from quantify.strategy.cross_sectional_momentum import CrossSectionalMomentum

    config = load_settings()
    broker = AlpacaBroker(config.alpaca)
    strategies = [CrossSectionalMomentum(universe=config.data.universe)]

    trader = PaperTrader(strategies=strategies, broker=broker, config=config)
    trader.run()   # blocks until stopped
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from quantify.config import Settings
from quantify.data.features import FeatureEngine
from quantify.data.models import TimeFrame
from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.execution.broker.base import Broker
from quantify.execution.order import Fill, Order, OrderSide, OrderType
from quantify.execution.order_manager import OrderManager
from quantify.execution.portfolio import Portfolio
from quantify.persistence.database import Database
from quantify.persistence.state import StateManager
from quantify.persistence.trade_log import TradeLogger
from quantify.risk.portfolio_risk import PortfolioRiskManager
from quantify.risk.position_sizer import EqualWeightSizer, MarketData, PositionSizer, get_sizer
from quantify.risk.stop_manager import StopManager
from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal
from quantify.strategy.volatility_regime import VolatilityRegimeStrategy
from quantify.paper.monitor import TradingMonitor
from quantify.paper.scheduler import TradingScheduler

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PaperTrader
# ---------------------------------------------------------------------------


class PaperTrader:
    """
    Top-level paper-trading orchestrator.

    Wires together all Quantify subsystems and drives them through a scheduled
    daily trading cycle.

    Parameters
    ----------
    strategies:
        List of :class:`~quantify.strategy.base.Strategy` instances to run.
        At least one strategy is required.
    broker:
        A connected :class:`~quantify.execution.broker.base.Broker` instance.
        For paper trading this is typically
        :class:`~quantify.execution.broker.alpaca_broker.AlpacaBroker`
        configured with ``paper=True``.
    config:
        Application settings loaded via
        :func:`~quantify.config.load_settings`.

    Attributes
    ----------
    portfolio:
        The live :class:`~quantify.execution.portfolio.Portfolio`.
    order_manager:
        The :class:`~quantify.execution.order_manager.OrderManager`.
    scheduler:
        The :class:`~quantify.paper.scheduler.TradingScheduler`.
    monitor:
        The :class:`~quantify.paper.monitor.TradingMonitor`.
    """

    def __init__(
        self,
        strategies: list[Strategy],
        broker: Broker,
        config: Settings,
    ) -> None:
        if not strategies:
            raise ValueError("PaperTrader requires at least one strategy")

        self._strategies = list(strategies)
        self._broker = broker
        self._config = config
        self._stop_event = threading.Event()

        # ----------------------------------------------------------------
        # Core execution layer
        # ----------------------------------------------------------------
        initial_capital = config.backtest.initial_capital
        self.portfolio = Portfolio(initial_capital=initial_capital)
        self.order_manager = OrderManager(
            broker=broker,
            max_position_pct=config.risk.max_single_position,
        )
        # Wire fills → portfolio
        self.order_manager.register_fill_listener(self._on_fill)

        # ----------------------------------------------------------------
        # Risk layer
        # ----------------------------------------------------------------
        self._risk_manager = PortfolioRiskManager(
            max_drawdown=config.risk.max_portfolio_drawdown,
            max_sector_exposure=config.risk.max_sector_exposure,
            max_gross_leverage=config.risk.max_gross_leverage,
            max_daily_loss=config.risk.daily_loss_limit,
        )
        self._stop_manager = StopManager(
            default_stop_pct=config.risk.default_stop_loss,
            default_profit_pct=config.risk.default_take_profit,
        )
        self._sizer: PositionSizer = get_sizer(
            config.risk.default_position_sizer,
            max_position_pct=config.risk.max_single_position,
        )

        # ----------------------------------------------------------------
        # Data layer
        # ----------------------------------------------------------------
        self._data_provider = YFinanceProvider()
        self._feature_engine = FeatureEngine()
        self._market_data_cache: dict[str, object] = {}  # symbol -> latest DataFrame

        # ----------------------------------------------------------------
        # Volatility regime overlay
        # ----------------------------------------------------------------
        self._vol_regime = VolatilityRegimeStrategy()

        # ----------------------------------------------------------------
        # Persistence
        # ----------------------------------------------------------------
        self._db = Database()
        self._db.initialize()
        self._trade_logger = TradeLogger(self._db)
        self._state_manager = StateManager(self._db)

        # ----------------------------------------------------------------
        # Monitoring
        # ----------------------------------------------------------------
        self.monitor = TradingMonitor(
            max_drawdown_alert=config.risk.max_portfolio_drawdown * 0.5,
            max_daily_loss_alert=config.risk.daily_loss_limit * 0.75,
        )
        self.scheduler = TradingScheduler()

        # ----------------------------------------------------------------
        # Internal counters
        # ----------------------------------------------------------------
        self._monitor_cycle: int = 0

        # ----------------------------------------------------------------
        # Build universe from all strategies
        # ----------------------------------------------------------------
        self._universe: list[str] = self._build_universe()

        log.info(
            "PaperTrader initialised: %d strategies, universe=%d symbols, "
            "initial_capital=%.2f",
            len(self._strategies),
            len(self._universe),
            initial_capital,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Start the trading scheduler and block until :meth:`stop` is called.

        Registers SIGINT/SIGTERM handlers so that Ctrl-C or a process signal
        triggers a graceful shutdown.
        """
        log.info("PaperTrader.run: starting trading scheduler")

        # Register OS signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._signal_handler)
            except (ValueError, OSError):
                # signal.signal() can fail in non-main threads; ignore
                pass

        # Restore any persisted strategy state from the previous session
        self._restore_state()

        # Wire up and start the scheduler
        self.scheduler.add_trading_jobs(
            pre_market_fn=self.pre_market,
            trading_fn=self.generate_and_execute,
            monitor_fn=self._monitor_wrapper,
            eod_fn=self.end_of_day,
        )
        self.scheduler.start()

        log.info("PaperTrader.run: scheduler running — press Ctrl-C to stop")
        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        finally:
            self._shutdown()

    def stop(self) -> None:
        """
        Signal the trading loop to stop gracefully.

        Safe to call from any thread.
        """
        log.info("PaperTrader.stop: stop requested")
        self._stop_event.set()

    def _signal_handler(self, signum: int, frame: object) -> None:
        """Handle OS shutdown signals."""
        log.info("PaperTrader: received signal %d — stopping", signum)
        self.stop()

    def _shutdown(self) -> None:
        """Internal cleanup on exit."""
        log.info("PaperTrader: shutting down")
        try:
            self.scheduler.stop(wait=False)
        except Exception as exc:
            log.warning("Scheduler stop error: %s", exc)
        try:
            self._save_state()
        except Exception as exc:
            log.warning("State save error on shutdown: %s", exc)
        try:
            self._db.close()
        except Exception as exc:
            log.warning("DB close error: %s", exc)
        log.info("PaperTrader: shutdown complete")

    # ------------------------------------------------------------------
    # Trading phases
    # ------------------------------------------------------------------

    def pre_market(self) -> None:
        """
        Pre-market phase (9:00 AM ET).

        1. Fetch the latest OHLCV data for the full universe.
        2. Compute features required by each strategy.
        3. Update the volatility regime overlay.
        4. Log the current portfolio status.
        """
        log.info("=== PaperTrader: PRE-MARKET phase started ===")
        try:
            self._fetch_and_cache_data()
        except Exception:
            log.exception("pre_market: data fetch failed")

        try:
            self._vol_regime.generate_signals(self._market_data_cache)
        except Exception:
            log.exception("pre_market: vol regime update failed")

        try:
            self._log_status()
        except Exception:
            log.exception("pre_market: status logging failed")

        log.info("=== PaperTrader: PRE-MARKET phase complete ===")

    def generate_and_execute(self) -> None:
        """
        Signal generation and order execution phase (9:35 AM ET).

        1. Collect signals from all strategies.
        2. Aggregate signals for the same symbol across strategies.
        3. Apply the volatility regime overlay.
        4. Apply portfolio-level risk adjustments.
        5. Size each signal using the configured position sizer.
        6. Submit orders via the order manager.
        7. Log all signals to the database.
        """
        log.info("=== PaperTrader: GENERATE-AND-EXECUTE phase started ===")

        if not self._market_data_cache:
            log.warning("generate_and_execute: no market data cached — fetching now")
            try:
                self._fetch_and_cache_data()
            except Exception:
                log.exception("generate_and_execute: data fetch failed — aborting")
                return

        # --- 1. Collect raw signals ---
        raw_signals: list[Signal] = []
        for strategy in self._strategies:
            try:
                data_subset = self._get_data_for_strategy(strategy)
                signals = strategy.generate_signals(data_subset)
                raw_signals.extend(signals)
                log.debug(
                    "generate_and_execute: strategy '%s' generated %d signals",
                    strategy.name, len(signals),
                )
            except Exception:
                log.exception(
                    "generate_and_execute: strategy '%s' raised an exception — skipping",
                    getattr(strategy, "name", repr(strategy)),
                )

        if not raw_signals:
            log.info("generate_and_execute: no signals generated this cycle")
            return

        # --- 2. Aggregate signals by symbol ---
        aggregated = self._aggregate_signals(raw_signals)
        log.info("generate_and_execute: aggregated %d raw → %d signals", len(raw_signals), len(aggregated))

        # --- 3. Vol regime overlay ---
        try:
            adjusted = self._vol_regime.adjust_signals(aggregated)
        except Exception:
            log.exception("generate_and_execute: vol regime adjustment failed — using raw")
            adjusted = aggregated

        # --- 4. Risk adjustments ---
        try:
            safe_signals = self._risk_manager.apply_risk_adjustments(
                adjusted, self.portfolio
            )
        except Exception:
            log.exception("generate_and_execute: risk adjustment failed — using unadjusted")
            safe_signals = adjusted

        # --- 5 & 6. Size and submit ---
        market_data = self._build_market_data()
        n_signals = max(len([s for s in safe_signals if s.direction != "close"]), 1)

        for sig in safe_signals:
            try:
                self._process_signal(sig, market_data, n_signals)
            except Exception:
                log.exception(
                    "generate_and_execute: failed to process signal %r — skipping", sig
                )

        # --- 7. Log signals ---
        try:
            for sig in raw_signals:
                self._trade_logger.log_signal(sig)
        except Exception:
            log.exception("generate_and_execute: signal logging failed")

        log.info("=== PaperTrader: GENERATE-AND-EXECUTE phase complete ===")

    def _monitor_wrapper(self) -> None:
        """Delegate to the monitor phase; called by the scheduler."""
        self._monitor_phase()

    def _monitor_phase(self) -> None:
        """
        Intraday monitoring phase (every 5 minutes).

        1. Fetch current prices.
        2. Update portfolio mark-to-market.
        3. Check stop losses / take profits.
        4. Submit close orders for triggered stops.
        5. Update the TradingMonitor.
        6. Log a portfolio snapshot every 30 minutes.
        """
        try:
            current_prices = self._fetch_current_prices()
            if current_prices:
                self.portfolio.update_market_prices(
                    current_prices, timestamp=datetime.now(tz=timezone.utc)
                )
        except Exception:
            log.exception("monitor: price update failed")

        # Check stops
        prices_for_stops = current_prices if current_prices else {}
        try:
            stop_signals = self._stop_manager.check_stops(
                prices_for_stops,
                current_time=datetime.now(tz=timezone.utc),
            )
            if stop_signals:
                log.info("monitor: %d stop(s) triggered", len(stop_signals))
                market_data = self._build_market_data()
                for sig in stop_signals:
                    try:
                        self._process_signal(sig, market_data, n_signals=1)
                    except Exception:
                        log.exception("monitor: failed to submit stop order for %s", sig.symbol)
            # Update trailing stops
            if prices_for_stops:
                self._stop_manager.update_trailing(prices_for_stops)
        except Exception:
            log.exception("monitor: stop check failed")

        # Update monitor state
        try:
            self.monitor.update(self.portfolio, self._broker)
        except Exception:
            log.exception("monitor: TradingMonitor update failed")

        # Periodic snapshot every ~30 min (every 6 cycles at 5-min interval)
        cycle = getattr(self, "_monitor_cycle", 0)
        self._monitor_cycle = cycle + 1
        if self._monitor_cycle % 6 == 0:
            try:
                self._trade_logger.log_portfolio_snapshot(self.portfolio)
            except Exception:
                log.exception("monitor: portfolio snapshot logging failed")

    def end_of_day(self) -> None:
        """
        End-of-day phase (3:55 PM ET).

        1. Reconcile local portfolio positions with broker positions.
        2. Log final portfolio snapshot.
        3. Save strategy state to the database.
        4. Log the daily performance summary.
        5. Print the status report.
        """
        log.info("=== PaperTrader: END-OF-DAY phase started ===")

        try:
            self._reconcile_positions()
        except Exception:
            log.exception("end_of_day: position reconciliation failed")

        try:
            self._trade_logger.log_portfolio_snapshot(self.portfolio)
        except Exception:
            log.exception("end_of_day: portfolio snapshot failed")

        try:
            self._save_state()
        except Exception:
            log.exception("end_of_day: state save failed")

        try:
            self._log_daily_summary()
        except Exception:
            log.exception("end_of_day: summary logging failed")

        try:
            self.monitor.update(self.portfolio, self._broker)
            self.monitor.print_status()
        except Exception:
            log.exception("end_of_day: monitor status print failed")

        log.info("=== PaperTrader: END-OF-DAY phase complete ===")

    # ------------------------------------------------------------------
    # Fill callback
    # ------------------------------------------------------------------

    def _on_fill(self, fill: Fill) -> None:
        """
        Called by the OrderManager whenever a fill is received.

        Updates the portfolio, logs the trade, and registers stop orders for
        new long positions.
        """
        try:
            self.portfolio.update_from_fill(fill)
        except Exception:
            log.exception("_on_fill: portfolio update failed for %r", fill)

        try:
            self._trade_logger.log_trade(
                strategy=fill.strategy_name,
                symbol=fill.symbol,
                side=fill.side.value,
                quantity=fill.quantity,
                price=fill.price,
                commission=fill.commission,
                order_id=fill.order_id,
                fill_id=None,
                timestamp=fill.timestamp,
            )
        except Exception:
            log.exception("_on_fill: trade logging failed for %r", fill)

        # Register a default stop for new long positions
        try:
            if fill.side == OrderSide.BUY:
                from quantify.risk.stop_manager import StopType
                self._stop_manager.add_stop(
                    symbol=fill.symbol,
                    stop_type=StopType.FIXED_PCT,
                    entry_price=fill.price,
                    params={"stop_pct": self._config.risk.default_stop_loss},
                    created_at=fill.timestamp,
                )
        except Exception:
            log.exception("_on_fill: stop registration failed for %s", fill.symbol)

    # ------------------------------------------------------------------
    # Signal aggregation
    # ------------------------------------------------------------------

    def _aggregate_signals(self, signals: list[Signal]) -> list[Signal]:
        """
        Aggregate signals for the same symbol across multiple strategies.

        Rules
        -----
        * ``close`` signals are always passed through individually.
        * For entry signals (long/short) targeting the same symbol, the
          strengths are averaged.
        * The final direction is determined by the sign of the average
          strength (positive = long, negative = short).
        * If strengths cancel out (average ≈ 0), the symbol is skipped.

        Parameters
        ----------
        signals:
            Raw signals from all strategies.

        Returns
        -------
        list[Signal]
            Aggregated signals (one entry per symbol plus any close signals).
        """
        close_signals = [s for s in signals if s.direction == "close"]
        entry_signals = [s for s in signals if s.direction != "close"]

        # Group by symbol
        by_symbol: dict[str, list[Signal]] = {}
        for sig in entry_signals:
            by_symbol.setdefault(sig.symbol, []).append(sig)

        aggregated: list[Signal] = list(close_signals)

        for symbol, sym_signals in by_symbol.items():
            if len(sym_signals) == 1:
                aggregated.append(sym_signals[0])
                continue

            # Average the signed strengths (long = positive, short = negative)
            signed_strengths = [
                s.strength if s.direction == "long" else -s.strength
                for s in sym_signals
            ]
            avg_strength = sum(signed_strengths) / len(signed_strengths)

            if abs(avg_strength) < 0.01:
                log.debug("_aggregate_signals: %s signals cancel out — skipping", symbol)
                continue

            direction = "long" if avg_strength > 0 else "short"
            abs_strength = min(abs(avg_strength), 1.0)

            strategy_names = ", ".join({s.strategy_name for s in sym_signals})
            combined_meta = {
                "aggregated_from": strategy_names,
                "n_strategies": len(sym_signals),
                "individual_strengths": signed_strengths,
            }

            aggregated.append(
                Signal(
                    strategy_name=f"aggregated[{strategy_names}]",
                    symbol=symbol,
                    direction=direction,
                    strength=abs_strength,
                    timestamp=sym_signals[0].timestamp,
                    metadata=combined_meta,
                )
            )

        return aggregated

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    def _process_signal(
        self,
        signal: Signal,
        market_data: MarketData,
        n_signals: int,
    ) -> None:
        """
        Convert a signal into a sized order and submit it.

        Parameters
        ----------
        signal:
            The signal to process.
        market_data:
            Current price data for sizing calculations.
        n_signals:
            Total number of concurrent signals (for equal-weight sizing).
        """
        if signal.direction == "close":
            # Close the position: sell the entire current holding
            pos = self.portfolio.get_position(signal.symbol)
            if pos is None or pos.is_flat:
                log.debug("_process_signal: no open position to close for %s", signal.symbol)
                return
            quantity = abs(pos.quantity)
            order_side = OrderSide.SELL if pos.quantity > 0 else OrderSide.BUY
            order = Order(
                symbol=signal.symbol,
                side=order_side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                strategy_name=signal.strategy_name,
            )
            self.order_manager.submit(order)
            # Remove stops for the closed position
            self._stop_manager.remove_stops(signal.symbol)
            return

        # Size the entry signal
        if isinstance(self._sizer, EqualWeightSizer):
            shares = self._sizer.calculate_size(
                signal, self.portfolio, market_data, n_signals=n_signals
            )
        else:
            shares = self._sizer.calculate_size(signal, self.portfolio, market_data)

        if abs(shares) < 1:
            log.debug(
                "_process_signal: sizing returned 0 shares for %s — skipping",
                signal.symbol,
            )
            return

        order_side = OrderSide.BUY if shares > 0 else OrderSide.SELL
        order = Order(
            symbol=signal.symbol,
            side=order_side,
            order_type=OrderType.MARKET,
            quantity=abs(shares),
            strategy_name=signal.strategy_name,
        )
        order_id = self.order_manager.submit(order)
        if order_id:
            log.info(
                "_process_signal: submitted %s %s x%.0f (signal strength=%.3f)",
                order_side.value, signal.symbol, abs(shares), signal.strength,
            )

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _build_universe(self) -> list[str]:
        """Collect and deduplicate all symbols across all strategies."""
        symbols: set[str] = set()
        for strategy in self._strategies:
            universe = getattr(strategy, "universe", [])
            symbols.update(universe)
        # Add sector ETFs for the vol regime overlay
        symbols.update(self._vol_regime.universe)
        result = sorted(symbols)
        log.debug("_build_universe: %d symbols", len(result))
        return result

    def _fetch_and_cache_data(self) -> None:
        """
        Fetch OHLCV data for the universe and compute features.

        Results are cached in ``self._market_data_cache`` as a dict of
        ``symbol -> pd.DataFrame`` with feature columns appended.
        """
        if not self._universe:
            log.warning("_fetch_and_cache_data: universe is empty")
            return

        import pandas as pd

        log.info("_fetch_and_cache_data: fetching data for %d symbols", len(self._universe))

        history_days = self._config.data.history_years * 365
        end_dt = datetime.now(tz=timezone.utc)
        start_dt = end_dt - timedelta(days=history_days)

        try:
            raw_data: dict[str, pd.DataFrame] = self._data_provider.get_multiple(
                self._universe,
                start=start_dt,
                end=end_dt,
                timeframe=TimeFrame.DAILY,
            )
        except Exception:
            log.exception("_fetch_and_cache_data: bulk fetch failed — falling back to sequential")
            raw_data = {}
            for symbol in self._universe:
                try:
                    df = self._data_provider.get_bars(
                        symbol,
                        start=start_dt,
                        end=end_dt,
                        timeframe=TimeFrame.DAILY,
                    )
                    if df is not None and not df.empty:
                        raw_data[symbol] = df
                except Exception:
                    log.warning("_fetch_and_cache_data: failed to fetch %s", symbol)

        if not raw_data:
            log.warning("_fetch_and_cache_data: no data retrieved for any symbol")
            return

        # Compute features required by all strategies
        required_features: set[str] = set()
        for strategy in self._strategies:
            try:
                required_features.update(strategy.get_required_features())
            except Exception:
                pass
        required_features.update(self._vol_regime.get_required_features())

        try:
            features_only = self._feature_engine.compute(
                raw_data, required=list(required_features)
            )
            # Merge features into the original OHLCV DataFrames so that price
            # columns (open, high, low, close, volume) are preserved alongside
            # the new feature columns.
            featured_data: dict = {}
            for sym, raw_df in raw_data.items():
                feat_df = features_only.get(sym)
                if feat_df is not None:
                    featured_data[sym] = raw_df.join(feat_df, how="left", rsuffix="_feat")
                else:
                    featured_data[sym] = raw_df
        except Exception:
            log.exception("_fetch_and_cache_data: feature computation failed — using raw data")
            featured_data = raw_data  # type: ignore[assignment]

        self._market_data_cache = featured_data
        log.info(
            "_fetch_and_cache_data: cached data for %d symbols with features: %s",
            len(featured_data),
            sorted(required_features),
        )

    def _get_data_for_strategy(self, strategy: Strategy) -> dict[str, object]:
        """Return the cached data subset for a strategy's universe."""
        universe = getattr(strategy, "universe", [])
        return {sym: self._market_data_cache[sym]
                for sym in universe
                if sym in self._market_data_cache}

    def _build_market_data(self) -> MarketData:
        """Build a :class:`~quantify.risk.position_sizer.MarketData` from cached data."""
        import pandas as pd

        price_series: dict[str, pd.Series] = {}
        current_prices: dict[str, float] = {}

        for symbol, df in self._market_data_cache.items():
            try:
                if hasattr(df, "columns") and "close" in df.columns:
                    price_series[symbol] = df["close"].dropna()
                    if not price_series[symbol].empty:
                        current_prices[symbol] = float(price_series[symbol].iloc[-1])
            except Exception:
                pass

        return MarketData(prices=price_series, current_prices=current_prices)

    def _fetch_current_prices(self) -> dict[str, float]:
        """Fetch the latest prices for all open positions."""
        current_prices: dict[str, float] = {}
        open_symbols = list(self.portfolio.open_positions.keys())

        if not open_symbols:
            return current_prices

        for symbol in open_symbols:
            if symbol in self._market_data_cache:
                df = self._market_data_cache[symbol]
                try:
                    if hasattr(df, "columns") and "close" in df.columns:
                        price = float(df["close"].dropna().iloc[-1])
                        current_prices[symbol] = price
                except Exception:
                    pass

        # Attempt live price fetch from broker
        try:
            live_prices = self._broker.get_latest_prices(open_symbols)
            if live_prices:
                current_prices.update(live_prices)
        except AttributeError:
            # Broker may not implement get_latest_prices
            pass
        except Exception:
            log.warning("_fetch_current_prices: broker price fetch failed, using cached")

        return current_prices

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _reconcile_positions(self) -> None:
        """
        Compare local portfolio positions against broker positions and log
        any discrepancies.

        This is informational only — no automatic corrections are made.
        Significant discrepancies should be investigated manually.
        """
        log.info("_reconcile_positions: comparing local vs broker positions")
        try:
            broker_positions: dict[str, object] = self._broker.get_positions()
        except Exception:
            log.warning("_reconcile_positions: could not fetch broker positions")
            return

        local_positions = self.portfolio.open_positions
        # broker_positions is dict[str, Position] keyed by symbol
        broker_map: dict[str, float] = {
            sym: getattr(pos, "quantity", 0.0)
            for sym, pos in broker_positions.items()
        }

        for symbol, local_pos in local_positions.items():
            broker_qty = broker_map.get(symbol, 0.0)
            local_qty = local_pos.quantity
            if abs(local_qty - broker_qty) > 0.01:
                log.warning(
                    "_reconcile_positions: MISMATCH %s local=%.2f broker=%.2f",
                    symbol, local_qty, broker_qty,
                )
            else:
                log.debug("_reconcile_positions: OK %s qty=%.2f", symbol, local_qty)

        for symbol, broker_qty in broker_map.items():
            if symbol not in local_positions and abs(float(broker_qty)) > 0.01:
                log.warning(
                    "_reconcile_positions: broker has position %s qty=%.2f not in local portfolio",
                    symbol, broker_qty,
                )

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _save_state(self) -> None:
        """Persist each strategy's internal state."""
        for strategy in self._strategies:
            try:
                state = getattr(strategy, "get_state", lambda: {})()
                if state:
                    self._state_manager.save_state(strategy.name, state)
                    log.debug("_save_state: saved state for '%s'", strategy.name)
            except Exception:
                log.exception("_save_state: failed for strategy '%s'", getattr(strategy, "name", "?"))

    def _restore_state(self) -> None:
        """Restore each strategy's internal state from the previous session."""
        for strategy in self._strategies:
            try:
                state = self._state_manager.load_state(strategy.name)
                if state:
                    restore_fn = getattr(strategy, "set_state", None)
                    if callable(restore_fn):
                        restore_fn(state)
                        log.info("_restore_state: restored state for '%s'", strategy.name)
                    else:
                        log.debug(
                            "_restore_state: strategy '%s' has no set_state method",
                            strategy.name,
                        )
            except Exception:
                log.exception("_restore_state: failed for strategy '%s'", getattr(strategy, "name", "?"))

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------

    def _log_status(self) -> None:
        """Log a brief portfolio status line at INFO level."""
        snap = self.portfolio.snapshot()
        log.info(
            "Portfolio status: equity=%.2f cash=%.2f daily_pnl=%+.2f "
            "total_pnl=%+.2f drawdown=%.2f%% positions=%d",
            snap["equity"],
            snap["cash"],
            snap["daily_pnl"],
            snap["total_pnl"],
            snap["drawdown_pct"],
            len(snap["positions"]),
        )

    def _log_daily_summary(self) -> None:
        """Log the daily performance summary to INFO and persist to DB."""
        snap = self.portfolio.snapshot()
        regime_summary = self._vol_regime.regime_summary()
        summary = self._trade_logger.get_trade_summary()

        log.info(
            "DAILY SUMMARY | equity=%.2f | daily_pnl=%+.2f | "
            "total_pnl=%+.2f (%.2f%%) | drawdown=%.2f%% | "
            "trades=%d | win_rate=%s | regime=%s",
            snap["equity"],
            snap["daily_pnl"],
            snap["total_pnl"],
            snap["total_return_pct"],
            snap["drawdown_pct"],
            summary.get("total_trades", 0),
            f"{summary.get('win_rate', 0.0):.1%}" if summary.get("win_rate") is not None else "N/A",
            regime_summary.get("regime", "unknown"),
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the trading loop is active."""
        return not self._stop_event.is_set()

    @property
    def strategies(self) -> list[Strategy]:
        """The list of registered strategies (read-only view)."""
        return list(self._strategies)

    def __repr__(self) -> str:
        return (
            f"PaperTrader(strategies={len(self._strategies)}, "
            f"universe={len(self._universe)}, "
            f"running={self.is_running})"
        )


__all__ = ["PaperTrader"]
