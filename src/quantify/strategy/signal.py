"""
quantify.strategy.signal
~~~~~~~~~~~~~~~~~~~~~~~~
Core signal dataclass emitted by strategies.

A :class:`Signal` is the atomic unit of intent produced by a strategy.
It communicates to the execution layer *what* to do (direction, strength)
without encoding *how* to size or route the order — those concerns live in
the order manager and position sizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class Signal:
    """
    Immutable trading signal emitted by a :class:`~quantify.strategy.base.Strategy`.

    Parameters
    ----------
    strategy_name:
        Unique identifier of the strategy that produced this signal.
    symbol:
        Ticker symbol the signal applies to (e.g. ``"AAPL"``).
    direction:
        ``"long"``  — strategy wants to be / go long.
        ``"short"`` — strategy wants to be / go short.
        ``"close"`` — strategy wants to exit an existing position.
    strength:
        Normalised conviction score in ``[-1.0, 1.0]``.
        Positive values indicate long conviction, negative values short
        conviction.  ``0.0`` is neutral.  Position sizers may use this
        to scale notional size.
    timestamp:
        Wall-clock (or bar-close) time at which the signal was generated.
        Should be timezone-aware where possible.
    metadata:
        Arbitrary key/value pairs for strategy-specific diagnostics
        (e.g. z-score, factor exposures, model probabilities).  Not used
        by the execution layer but stored for research purposes.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> sig = Signal(
    ...     strategy_name="momentum_daily",
    ...     symbol="MSFT",
    ...     direction="long",
    ...     strength=0.75,
    ...     timestamp=datetime.now(timezone.utc),
    ...     metadata={"zscore": 2.1, "rank": 3},
    ... )
    >>> sig.direction
    'long'
    """

    strategy_name: str
    symbol: str
    direction: Literal["long", "short", "close"]
    strength: float  # -1.0 to 1.0
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not -1.0 <= self.strength <= 1.0:
            raise ValueError(
                f"Signal.strength must be in [-1.0, 1.0], got {self.strength}"
            )
        if self.direction not in ("long", "short", "close"):
            raise ValueError(
                f"Signal.direction must be 'long', 'short', or 'close', got '{self.direction}'"
            )
        if not self.strategy_name:
            raise ValueError("Signal.strategy_name must not be empty")
        if not self.symbol:
            raise ValueError("Signal.symbol must not be empty")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_entry(self) -> bool:
        """True if the signal opens a new position (long or short)."""
        return self.direction in ("long", "short")

    @property
    def is_exit(self) -> bool:
        """True if the signal requests a position closure."""
        return self.direction == "close"

    @property
    def is_long(self) -> bool:
        """True for ``"long"`` direction signals."""
        return self.direction == "long"

    @property
    def is_short(self) -> bool:
        """True for ``"short"`` direction signals."""
        return self.direction == "short"

    def __repr__(self) -> str:
        ts_str = self.timestamp.isoformat(timespec="seconds")
        return (
            f"Signal({self.strategy_name!r}, {self.symbol!r}, "
            f"{self.direction!r}, strength={self.strength:.3f}, ts={ts_str})"
        )


__all__ = ["Signal"]
