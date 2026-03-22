"""
quantify.strategy.base
~~~~~~~~~~~~~~~~~~~~~~
Abstract base class that every concrete trading strategy must implement.

The :class:`Strategy` contract is deliberately thin — it only mandates two
methods:

* :meth:`generate_signals` — produce :class:`~quantify.strategy.signal.Signal`
  objects given a window of OHLCV data keyed by symbol.
* :meth:`get_required_features` — declare which derived feature columns the
  strategy expects in its DataFrames so the data pipeline can compute them
  lazily.

Optional lifecycle hooks (:meth:`on_fill`, :meth:`on_start`, :meth:`on_stop`)
allow strategies to maintain internal state without the framework needing to
understand that state.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pandas as pd

from quantify.strategy.signal import Signal

if TYPE_CHECKING:
    from quantify.execution.order import Fill

log = logging.getLogger(__name__)


class Strategy(ABC):
    """
    Abstract base class for all Quantify trading strategies.

    Subclasses **must** implement:

    * :meth:`generate_signals`
    * :meth:`get_required_features`

    They may optionally set class/instance attributes:

    Attributes
    ----------
    name:
        Human-readable identifier, also used as ``strategy_name`` in
        emitted :class:`~quantify.strategy.signal.Signal` objects.  Must
        be unique across all strategies registered with the engine.
    universe:
        List of ticker symbols this strategy trades.  The engine uses this
        list to decide which symbols' data to pass to
        :meth:`generate_signals`.
    lookback_days:
        Minimum number of calendar days of history the strategy needs in
        order to generate valid signals.  The data pipeline will ensure at
        least this many bars are available.
    rebalance_frequency:
        One of ``"daily"``, ``"weekly"``, or ``"monthly"``.  Controls how
        often the engine calls :meth:`generate_signals`.

    Examples
    --------
    >>> class MyMomentum(Strategy):
    ...     name = "my_momentum"
    ...     universe = ["AAPL", "MSFT", "GOOG"]
    ...     lookback_days = 252
    ...     rebalance_frequency = "weekly"
    ...
    ...     def generate_signals(self, data):
    ...         signals = []
    ...         for sym, df in data.items():
    ...             ret = df["close"].pct_change(20).iloc[-1]
    ...             direction = "long" if ret > 0 else "short"
    ...             signals.append(Signal(
    ...                 strategy_name=self.name,
    ...                 symbol=sym,
    ...                 direction=direction,
    ...                 strength=min(abs(ret) * 10, 1.0),
    ...                 timestamp=df.index[-1],
    ...             ))
    ...         return signals
    ...
    ...     def get_required_features(self):
    ...         return ["returns_20d"]
    """

    # ------------------------------------------------------------------
    # Strategy-level metadata — override in subclasses
    # ------------------------------------------------------------------

    #: Unique strategy identifier.  Must be set by every subclass.
    name: str = ""

    #: Symbols this strategy trades.
    universe: list[str] = []

    #: Calendar days of lookback history required.
    lookback_days: int = 252

    #: How frequently to re-run signal generation.
    rebalance_frequency: str = "daily"  # "daily" | "weekly" | "monthly"

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        Compute trading signals from a window of bar data.

        Parameters
        ----------
        data:
            Mapping of ``{symbol: DataFrame}`` where each DataFrame has a
            :class:`~pandas.DatetimeIndex` (bar timestamps) and at minimum
            the columns ``open``, ``high``, ``low``, ``close``, ``volume``.
            Additional feature columns requested via
            :meth:`get_required_features` will also be present.

            The DataFrames are pre-sliced to the strategy's lookback window
            and contain only symbols from :attr:`universe` that passed the
            data-quality checks.

        Returns
        -------
        list[Signal]
            Zero or more signals for the current bar.  An empty list is
            valid (strategy has nothing to say this period).

        Notes
        -----
        * This method should be **pure** — do not mutate ``data`` or rely
          on external I/O.  Maintain any required state in instance
          attributes updated via lifecycle hooks.
        * Signals are processed in list order.  If two signals target the
          same symbol, the *last* one wins after deduplication in the order
          manager.
        """
        ...

    @abstractmethod
    def get_required_features(self) -> list[str]:
        """
        Declare which derived feature columns this strategy needs.

        The data pipeline calls this method at initialisation and ensures
        the requested features are computed and present in the DataFrames
        passed to :meth:`generate_signals`.

        Returns
        -------
        list[str]
            Column names from :mod:`quantify.data.features`.  An empty
            list is acceptable if the strategy only needs raw OHLCV data.

        Examples
        --------
        >>> strategy.get_required_features()
        ['sma_20', 'sma_50', 'rsi_14', 'atr_14']
        """
        ...

    # ------------------------------------------------------------------
    # Optional lifecycle hooks
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """
        Called once when the engine starts (backtest or live session).

        Use to initialise any internal state, warm up models, or pre-load
        reference data.  Default implementation does nothing.
        """

    def on_stop(self) -> None:
        """
        Called once when the engine stops (backtest complete or session ends).

        Use to flush state, save models, or write diagnostics.  Default
        implementation does nothing.
        """

    def on_fill(self, fill: "Fill") -> None:
        """
        Called each time one of this strategy's orders is (partially) filled.

        Parameters
        ----------
        fill:
            The :class:`~quantify.execution.order.Fill` object describing
            the executed trade.

        Default implementation logs the fill at DEBUG level.
        """
        log.debug(
            "%s: fill received — %s %s × %.4f @ %.4f",
            self.name,
            fill.side.value,
            fill.symbol,
            fill.quantity,
            fill.price,
        )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate that required class attributes are properly configured.

        Raises
        ------
        ValueError
            If ``name`` is empty, ``universe`` is empty, or
            ``rebalance_frequency`` is invalid.
        """
        if not self.name:
            raise ValueError(f"{type(self).__name__}.name must be set")
        if not self.universe:
            raise ValueError(f"Strategy '{self.name}': universe must not be empty")
        valid_freqs = {"daily", "weekly", "monthly"}
        if self.rebalance_frequency not in valid_freqs:
            raise ValueError(
                f"Strategy '{self.name}': rebalance_frequency must be one of "
                f"{valid_freqs}, got '{self.rebalance_frequency}'"
            )
        if self.lookback_days < 1:
            raise ValueError(
                f"Strategy '{self.name}': lookback_days must be >= 1, "
                f"got {self.lookback_days}"
            )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(name={self.name!r}, "
            f"universe={self.universe!r}, "
            f"rebalance={self.rebalance_frequency!r})"
        )


__all__ = ["Strategy"]
