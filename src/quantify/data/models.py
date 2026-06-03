"""
Data models for the Quantify trading system.

Provides the core Bar dataclass, TimeFrame enum, and helpers for converting
bar data to pandas DataFrames suitable for downstream analysis.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd


class TimeFrame(enum.Enum):
    """Supported bar timeframes."""

    MINUTE = "1m"
    HOUR = "1h"
    DAILY = "1d"
    WEEKLY = "1wk"


@dataclass(frozen=True)
class Bar:
    """
    Immutable OHLCV bar for a single symbol and timestamp.

    Attributes
    ----------
    symbol:
        Ticker symbol (e.g. "AAPL").
    timestamp:
        Bar open time, timezone-aware or naive (UTC assumed when naive).
    open:
        Opening price.
    high:
        High price.
    low:
        Low price.
    close:
        Closing price.
    volume:
        Number of shares traded.
    vwap:
        Volume-weighted average price for the period.  None when not
        available (common for end-of-day data from some providers).
    """

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def typical_price(self) -> float:
        """(High + Low + Close) / 3."""
        return (self.high + self.low + self.close) / 3.0

    @property
    def dollar_volume(self) -> float:
        """Close * Volume — proxy for liquidity."""
        return self.close * self.volume

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(
                f"Bar {self.symbol} @ {self.timestamp}: high ({self.high}) < low ({self.low})"
            )
        if self.volume < 0:
            raise ValueError(
                f"Bar {self.symbol} @ {self.timestamp}: volume must be non-negative"
            )


# ---------------------------------------------------------------------------
# DataFrame helpers
# ---------------------------------------------------------------------------

_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
_ALL_COLUMNS = _OHLCV_COLUMNS + ["vwap", "symbol"]


def bars_to_dataframe(bars: list[Bar]) -> pd.DataFrame:
    """
    Convert a list of :class:`Bar` objects to an OHLCV DataFrame.

    Parameters
    ----------
    bars:
        Bars for a *single* symbol (mixing symbols is supported but the
        ``symbol`` column will be included so callers can split if needed).

    Returns
    -------
    pd.DataFrame
        Columns: open, high, low, close, volume, vwap (float, NaN when
        absent), symbol.  Index: timestamp (DatetimeIndex, ascending).
        Column dtypes: open/high/low/close/vwap → float64;
        volume → int64; symbol → object.

    Raises
    ------
    ValueError
        If *bars* is empty.

    Examples
    --------
    >>> df = bars_to_dataframe(bars)
    >>> df.columns.tolist()
    ['open', 'high', 'low', 'close', 'volume', 'vwap', 'symbol']
    """
    if not bars:
        raise ValueError("bars list must not be empty")

    rows = [
        {
            "timestamp": b.timestamp,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "vwap": b.vwap,
            "symbol": b.symbol,
        }
        for b in bars
    ]

    df = pd.DataFrame(rows)
    df = df.set_index("timestamp").sort_index()

    # Enforce dtypes
    for col in ("open", "high", "low", "close", "vwap"):
        df[col] = df[col].astype("float64")
    df["volume"] = df["volume"].astype("int64")

    return df[_ALL_COLUMNS]


def dataframe_to_bars(df: pd.DataFrame, symbol: str | None = None) -> list[Bar]:
    """
    Inverse of :func:`bars_to_dataframe`.

    Parameters
    ----------
    df:
        DataFrame with the standard OHLCV(+vwap) column layout and a
        DatetimeIndex.
    symbol:
        Override the ``symbol`` column (or supply it when the column is
        absent).
    """
    records: list[Bar] = []
    sym_col = "symbol" in df.columns

    for ts, row in df.iterrows():
        sym = symbol if symbol is not None else (row["symbol"] if sym_col else "UNKNOWN")
        vwap_val = None if pd.isna(row.get("vwap", float("nan"))) else float(row["vwap"])
        records.append(
            Bar(
                symbol=sym,
                timestamp=ts,  # type: ignore[arg-type]
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                vwap=vwap_val,
            )
        )
    return records
