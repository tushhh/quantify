"""
Abstract base class for all Quantify data providers.

All providers (yfinance, Alpaca, Polygon, etc.) must implement this interface
so that the rest of the system can remain provider-agnostic.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Sequence

import pandas as pd

from quantify.data.models import TimeFrame


class DataProvider(abc.ABC):
    """
    Contract that every market-data provider must fulfil.

    All returned DataFrames share the same schema::

        Index  : DatetimeIndex  (bar open time, tz-aware UTC preferred)
        Columns: open   float64
                 high   float64
                 low    float64
                 close  float64
                 volume int64
                 vwap   float64  (NaN when not available)

    Implementors should raise :exc:`DataProviderError` for recoverable
    failures (rate-limit, symbol-not-found, etc.) so callers can handle
    them uniformly.
    """

    # ------------------------------------------------------------------
    # Core interface — must be implemented by subclasses
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: TimeFrame = TimeFrame.DAILY,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars for a single *symbol* over [start, end).

        Parameters
        ----------
        symbol:
            Ticker symbol (e.g. ``"AAPL"``).
        start:
            Inclusive start of the date range.
        end:
            Exclusive end of the date range.
        timeframe:
            Bar granularity.

        Returns
        -------
        pd.DataFrame
            Standard OHLCV DataFrame (see class docstring).  Empty
            DataFrame (same schema) if no data is available.

        Raises
        ------
        DataProviderError
            On provider-level errors (network, auth, symbol not found).
        """

    @abc.abstractmethod
    def get_multiple(
        self,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
        timeframe: TimeFrame = TimeFrame.DAILY,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch OHLCV bars for *multiple* symbols over [start, end).

        Default implementation calls :meth:`get_bars` once per symbol;
        providers should override for bulk-fetch efficiency.

        Parameters
        ----------
        symbols:
            Sequence of ticker symbols.
        start:
            Inclusive start of the date range.
        end:
            Exclusive end of the date range.
        timeframe:
            Bar granularity.

        Returns
        -------
        dict[str, pd.DataFrame]
            Mapping from symbol to its OHLCV DataFrame.  Symbols for
            which no data is available are **omitted** from the result.
        """

    # ------------------------------------------------------------------
    # Optional helpers — can be overridden for performance
    # ------------------------------------------------------------------

    def get_latest_bar(self, symbol: str) -> pd.Series | None:
        """Return the most-recent bar for *symbol*, or None."""
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_latest_bar"
        )

    def supports_timeframe(self, timeframe: TimeFrame) -> bool:
        """Return True if this provider supports *timeframe*."""
        return True  # conservative default — subclasses may restrict

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DataProviderError(Exception):
    """Raised when a data provider encounters a recoverable error."""


class RateLimitError(DataProviderError):
    """Raised when the provider signals a rate-limit (HTTP 429 etc.)."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class SymbolNotFoundError(DataProviderError):
    """Raised when the requested symbol is not recognised by the provider."""

    def __init__(self, symbol: str):
        super().__init__(f"Symbol not found: {symbol!r}")
        self.symbol = symbol


class AuthenticationError(DataProviderError):
    """Raised when API credentials are missing or invalid."""
