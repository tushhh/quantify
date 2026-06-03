"""
quantify.risk.stop_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop-loss and take-profit management for the Quantify trading system.

The :class:`StopManager` maintains a registry of active stops across all
open positions.  On each bar it:

1. Evaluates whether any stop has been triggered by the latest prices.
2. Updates trailing-stop levels upward as prices move in the trade's favour.
3. Returns :class:`~quantify.strategy.signal.Signal` objects with
   ``direction="close"`` for any triggered stops, ready to be routed to
   the execution layer.

Stop types
----------
* ``FIXED_PCT``   — close when price falls below ``entry × (1 - stop_pct)``
* ``ATR_BASED``   — close when price falls below ``entry - atr_multiplier × ATR(14)``
* ``TRAILING``    — trailing stop: ``max_price_since_entry - ATR``; ratchets upward
* ``TIME_BASED``  — close after ``max_holding_days`` calendar days
* ``TAKE_PROFIT`` — close when price rises above ``entry × (1 + profit_pct)``

Usage
-----
    from quantify.risk.stop_manager import StopManager, StopType

    mgr = StopManager()
    mgr.add_stop("AAPL", StopType.TRAILING, entry_price=150.0, atr=2.5)
    mgr.add_stop("AAPL", StopType.TAKE_PROFIT, entry_price=150.0)

    # On each bar:
    close_signals = mgr.check_stops(current_prices, current_time=datetime.now(tz=timezone.utc))
    mgr.update_trailing(current_prices)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import Any

from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

_STRATEGY_NAME = "stop_manager"


# ---------------------------------------------------------------------------
# Enums and dataclasses
# ---------------------------------------------------------------------------


class StopType(Enum):
    """Supported stop-loss / take-profit variants."""

    FIXED_PCT = auto()    # percentage-based hard stop
    ATR_BASED = auto()    # entry minus N × ATR
    TRAILING = auto()     # trailing ATR stop; ratchets with highest price
    TIME_BASED = auto()   # close after N days
    TAKE_PROFIT = auto()  # take-profit target above entry


@dataclass
class Stop:
    """
    Represents a single stop order tracking one position.

    Attributes
    ----------
    symbol:
        Ticker the stop applies to.
    stop_type:
        One of :class:`StopType`.
    trigger_price:
        The price at which the stop fires.  For ``TRAILING`` this is
        updated dynamically.  For ``TIME_BASED`` it is ``None``.
    entry_price:
        Price at which the position was opened.
    created_at:
        Wall-clock timestamp when the stop was registered.
    params:
        Free-form parameters (e.g. ``stop_pct``, ``max_holding_days``).
    highest_price:
        Tracks the running high since entry, used by ``TRAILING`` stops.
    active:
        ``False`` once the stop has been triggered and consumed.
    """

    symbol: str
    stop_type: StopType
    trigger_price: float | None
    entry_price: float
    created_at: datetime
    params: dict[str, Any] = field(default_factory=dict)
    highest_price: float = 0.0
    active: bool = True

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Stop.symbol must not be empty")
        if self.entry_price <= 0:
            raise ValueError(f"Stop.entry_price must be positive, got {self.entry_price}")
        if self.highest_price == 0.0:
            self.highest_price = self.entry_price

    @property
    def expiry(self) -> datetime | None:
        """Return expiry datetime for TIME_BASED stops, else None."""
        if self.stop_type is not StopType.TIME_BASED:
            return None
        days = self.params.get("max_holding_days", 20)
        return self.created_at + timedelta(days=int(days))

    def __repr__(self) -> str:
        tp = f"{self.trigger_price:.4f}" if self.trigger_price is not None else "N/A"
        return (
            f"Stop({self.symbol!r}, {self.stop_type.name}, "
            f"trigger={tp}, entry={self.entry_price:.4f})"
        )


# ---------------------------------------------------------------------------
# StopManager
# ---------------------------------------------------------------------------


class StopManager:
    """
    Manages a registry of active stops across all open positions.

    Defaults
    --------
    * Fixed stop:   ``entry × (1 - stop_pct)``  where ``stop_pct`` defaults to 0.02.
    * ATR stop:     ``entry - atr_multiplier × atr``  where multiplier defaults to 2.0.
    * Trailing:     ``highest_price - atr``  (no multiplier; starts at ``entry - atr``).
    * Time stop:    closes after ``max_holding_days`` (default 20) calendar days.
    * Take-profit:  ``entry × (1 + profit_pct)``  where ``profit_pct`` defaults to 0.04.

    Parameters
    ----------
    default_stop_pct:
        Default fixed-stop percentage (default: 0.02 = 2 %).
    default_profit_pct:
        Default take-profit percentage (default: 0.04 = 4 %).
    default_atr_multiplier:
        Default multiplier applied to ATR for ATR-based and trailing stops
        (default: 2.0).
    default_max_holding_days:
        Default days before a time-based stop fires (default: 20).
    """

    def __init__(
        self,
        default_stop_pct: float = 0.02,
        default_profit_pct: float = 0.04,
        default_atr_multiplier: float = 2.0,
        default_max_holding_days: int = 20,
    ) -> None:
        if not 0 < default_stop_pct < 1:
            raise ValueError("default_stop_pct must be in (0, 1)")
        if not 0 < default_profit_pct < 1:
            raise ValueError("default_profit_pct must be in (0, 1)")
        if default_atr_multiplier <= 0:
            raise ValueError("default_atr_multiplier must be positive")
        if default_max_holding_days < 1:
            raise ValueError("default_max_holding_days must be >= 1")

        self.default_stop_pct = default_stop_pct
        self.default_profit_pct = default_profit_pct
        self.default_atr_multiplier = default_atr_multiplier
        self.default_max_holding_days = default_max_holding_days

        # Registry: symbol → list of active stops
        self._stops: dict[str, list[Stop]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_stop(
        self,
        symbol: str,
        stop_type: StopType,
        entry_price: float,
        *,
        atr: float | None = None,
        params: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> Stop:
        """
        Create and register a new stop for *symbol*.

        Parameters
        ----------
        symbol:
            Ticker the stop applies to.
        stop_type:
            Which :class:`StopType` to register.
        entry_price:
            Fill price at which the position was opened.
        atr:
            Current ATR(14) value (required for ``ATR_BASED`` and
            ``TRAILING`` stops; raises ``ValueError`` if absent for those
            types).
        params:
            Optional overrides for defaults (e.g. ``{"stop_pct": 0.03}``).
        created_at:
            Timestamp for the stop (defaults to ``datetime.now(UTC)``).

        Returns
        -------
        Stop
            The newly created and registered stop.
        """
        p = params or {}
        ts = created_at or datetime.now(tz=timezone.utc)

        trigger = self._compute_initial_trigger(
            stop_type=stop_type,
            entry_price=entry_price,
            atr=atr,
            params=p,
        )

        stop = Stop(
            symbol=symbol,
            stop_type=stop_type,
            trigger_price=trigger,
            entry_price=entry_price,
            created_at=ts,
            params=p,
            highest_price=entry_price,
            active=True,
        )

        if symbol not in self._stops:
            self._stops[symbol] = []
        self._stops[symbol].append(stop)

        log.info(
            "StopManager.add_stop: %s [%s] entry=%.4f trigger=%s",
            symbol, stop_type.name,
            entry_price,
            f"{trigger:.4f}" if trigger is not None else "time-based",
        )
        return stop

    def _compute_initial_trigger(
        self,
        stop_type: StopType,
        entry_price: float,
        atr: float | None,
        params: dict[str, Any],
    ) -> float | None:
        """Compute the initial trigger price for a given stop type."""
        if stop_type is StopType.FIXED_PCT:
            stop_pct = float(params.get("stop_pct", self.default_stop_pct))
            return entry_price * (1.0 - stop_pct)

        if stop_type is StopType.ATR_BASED:
            if atr is None or atr <= 0:
                raise ValueError(
                    "ATR_BASED stop requires a positive atr value"
                )
            multiplier = float(params.get("atr_multiplier", self.default_atr_multiplier))
            return entry_price - multiplier * atr

        if stop_type is StopType.TRAILING:
            if atr is None or atr <= 0:
                raise ValueError(
                    "TRAILING stop requires a positive atr value"
                )
            multiplier = float(params.get("atr_multiplier", self.default_atr_multiplier))
            # Starts at entry - atr_multiplier * atr
            return entry_price - multiplier * atr

        if stop_type is StopType.TIME_BASED:
            # No trigger price — evaluated by elapsed time
            return None

        if stop_type is StopType.TAKE_PROFIT:
            profit_pct = float(params.get("profit_pct", self.default_profit_pct))
            return entry_price * (1.0 + profit_pct)

        raise ValueError(f"Unknown StopType: {stop_type}")

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def check_stops(
        self,
        current_prices: dict[str, float],
        current_time: datetime | None = None,
    ) -> list[Signal]:
        """
        Check all active stops against the provided prices.

        Parameters
        ----------
        current_prices:
            Mapping from symbol to latest market price.
        current_time:
            Current wall-clock time (defaults to ``datetime.now(UTC)``).

        Returns
        -------
        list[Signal]
            One ``direction="close"`` signal per triggered stop, suitable for
            routing directly to the execution layer.
        """
        now = current_time or datetime.now(tz=timezone.utc)
        close_signals: list[Signal] = []

        for symbol, stops in list(self._stops.items()):
            price = current_prices.get(symbol)
            if price is None:
                log.debug("check_stops: no price for %s — skipping", symbol)
                continue

            for stop in stops:
                if not stop.active:
                    continue
                triggered, reason = self._is_triggered(stop, price, now)
                if triggered:
                    stop.active = False
                    log.info(
                        "StopManager.check_stops: TRIGGERED %s [%s] "
                        "price=%.4f trigger=%s reason=%s",
                        symbol, stop.stop_type.name, price,
                        f"{stop.trigger_price:.4f}" if stop.trigger_price is not None else "N/A",
                        reason,
                    )
                    sig = Signal(
                        strategy_name=_STRATEGY_NAME,
                        symbol=symbol,
                        direction="close",
                        strength=1.0,
                        timestamp=now,
                        metadata={
                            "stop_type": stop.stop_type.name,
                            "trigger_price": stop.trigger_price,
                            "entry_price": stop.entry_price,
                            "current_price": price,
                            "reason": reason,
                        },
                    )
                    close_signals.append(sig)

        # Prune dead stops
        self._prune_inactive()

        log.debug(
            "check_stops: evaluated %d symbols, generated %d close signals",
            len(current_prices), len(close_signals),
        )
        return close_signals

    def _is_triggered(
        self,
        stop: Stop,
        price: float,
        now: datetime,
    ) -> tuple[bool, str]:
        """
        Evaluate a single stop against the current price/time.

        Returns
        -------
        (bool, str)
            Whether triggered and a human-readable reason string.
        """
        if stop.stop_type is StopType.FIXED_PCT:
            assert stop.trigger_price is not None
            if price <= stop.trigger_price:
                return True, (
                    f"price {price:.4f} <= fixed stop {stop.trigger_price:.4f}"
                )

        elif stop.stop_type is StopType.ATR_BASED:
            assert stop.trigger_price is not None
            if price <= stop.trigger_price:
                return True, (
                    f"price {price:.4f} <= ATR stop {stop.trigger_price:.4f}"
                )

        elif stop.stop_type is StopType.TRAILING:
            assert stop.trigger_price is not None
            if price <= stop.trigger_price:
                return True, (
                    f"price {price:.4f} <= trailing stop {stop.trigger_price:.4f}"
                )

        elif stop.stop_type is StopType.TIME_BASED:
            expiry = stop.expiry
            assert expiry is not None
            if now >= expiry:
                days_held = (now - stop.created_at).days
                return True, (
                    f"time stop expired: held {days_held} days "
                    f"(max {stop.params.get('max_holding_days', self.default_max_holding_days)})"
                )

        elif stop.stop_type is StopType.TAKE_PROFIT:
            assert stop.trigger_price is not None
            if price >= stop.trigger_price:
                return True, (
                    f"price {price:.4f} >= take-profit {stop.trigger_price:.4f}"
                )

        return False, ""

    # ------------------------------------------------------------------
    # Trailing-stop update
    # ------------------------------------------------------------------

    def update_trailing(self, current_prices: dict[str, float]) -> None:
        """
        Ratchet trailing stops upward as prices rise above the recorded
        high since entry.

        This should be called *after* :meth:`check_stops` on each bar so
        we do not trigger a stop and update it in the same cycle.

        Parameters
        ----------
        current_prices:
            Mapping from symbol to latest market price.
        """
        for symbol, stops in self._stops.items():
            price = current_prices.get(symbol)
            if price is None:
                continue
            for stop in stops:
                if not stop.active or stop.stop_type is not StopType.TRAILING:
                    continue
                if price > stop.highest_price:
                    old_high = stop.highest_price
                    stop.highest_price = price
                    atr = stop.params.get("atr")
                    multiplier = float(
                        stop.params.get("atr_multiplier", self.default_atr_multiplier)
                    )
                    if atr is not None and atr > 0:
                        new_trigger = price - multiplier * float(atr)
                        if new_trigger > (stop.trigger_price or 0.0):
                            old_trigger = stop.trigger_price
                            stop.trigger_price = new_trigger
                            log.debug(
                                "update_trailing: %s high %.4f→%.4f, "
                                "trigger %.4f→%.4f",
                                symbol, old_high, price,
                                old_trigger, new_trigger,
                            )

    def update_trailing_atr(self, symbol: str, new_atr: float) -> None:
        """
        Refresh the ATR value stored inside trailing stops for *symbol*.

        Call this whenever you recompute ATR(14) on a new bar so that future
        :meth:`update_trailing` calls use the latest volatility estimate.

        Parameters
        ----------
        symbol:
            Ticker whose stops should be updated.
        new_atr:
            Latest ATR(14) value.
        """
        for stop in self._stops.get(symbol, []):
            if stop.active and stop.stop_type is StopType.TRAILING:
                stop.params["atr"] = new_atr

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def remove_stops(self, symbol: str) -> int:
        """
        Remove all stops (active or inactive) for a closed position.

        Parameters
        ----------
        symbol:
            Ticker whose stops should be cleared.

        Returns
        -------
        int
            Number of stops removed.
        """
        removed = len(self._stops.get(symbol, []))
        if symbol in self._stops:
            del self._stops[symbol]
            log.info("StopManager.remove_stops: cleared %d stop(s) for %s", removed, symbol)
        else:
            log.debug("StopManager.remove_stops: no stops found for %s", symbol)
        return removed

    def _prune_inactive(self) -> None:
        """Remove inactive stops from the registry to prevent unbounded growth."""
        before = sum(len(v) for v in self._stops.values())
        self._stops = {
            sym: [s for s in stops if s.active]
            for sym, stops in self._stops.items()
            if any(s.active for s in stops)
        }
        after = sum(len(v) for v in self._stops.values())
        pruned = before - after
        if pruned:
            log.debug("StopManager._prune_inactive: removed %d inactive stop(s)", pruned)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def active_stops(self, symbol: str | None = None) -> list[Stop]:
        """
        Return all currently active stops, optionally filtered by *symbol*.

        Parameters
        ----------
        symbol:
            If provided, return only stops for this ticker.

        Returns
        -------
        list[Stop]
        """
        if symbol is not None:
            return [s for s in self._stops.get(symbol, []) if s.active]
        return [s for stops in self._stops.values() for s in stops if s.active]

    def stop_count(self) -> dict[str, int]:
        """Return {symbol: active_stop_count} for all tracked symbols."""
        return {sym: sum(1 for s in stops if s.active) for sym, stops in self._stops.items()}

    def __repr__(self) -> str:
        n_symbols = len(self._stops)
        n_stops = sum(len(v) for v in self._stops.values())
        return (
            f"StopManager(symbols={n_symbols}, active_stops={n_stops}, "
            f"default_stop_pct={self.default_stop_pct:.2%})"
        )


__all__ = [
    "StopType",
    "Stop",
    "StopManager",
]
