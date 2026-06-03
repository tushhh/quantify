"""
YFinance data provider for the Quantify trading system.

Uses the ``yfinance`` library to download historical OHLCV data from Yahoo
Finance.  Results are transparently cached via :class:`~quantify.data.cache.ParquetCache`
so that repeated requests for the same symbol/date-range are served from disk
rather than hitting the network.

Usage
-----
>>> from quantify.data.providers.yfinance_provider import YFinanceProvider
>>> provider = YFinanceProvider()
>>> df = provider.get_bars("AAPL", start=datetime(2023, 1, 1), end=datetime(2024, 1, 1))
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Sequence

import pandas as pd
import yfinance as yf

from quantify.data.cache import ParquetCache
from quantify.data.models import TimeFrame
from quantify.data.providers.base import (
    DataProvider,
    DataProviderError,
    RateLimitError,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)

# yfinance interval strings mapped from TimeFrame
_TF_TO_YF: dict[TimeFrame, str] = {
    TimeFrame.MINUTE: "1m",
    TimeFrame.HOUR: "1h",
    TimeFrame.DAILY: "1d",
    TimeFrame.WEEKLY: "1wk",
}

# Standard output columns
_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


class YFinanceProvider(DataProvider):
    """
    DataProvider backed by Yahoo Finance via ``yfinance``.

    Parameters
    ----------
    cache:
        Optional :class:`~quantify.data.cache.ParquetCache` instance.
        When supplied, every successful download is persisted to disk and
        future calls that fall entirely within the cached range are served
        from cache without a network request.
    rate_limit_pause:
        Seconds to wait between individual ticker downloads when
        ``get_multiple`` falls back to sequential fetching.  Default 0.25 s
        is conservative enough for Yahoo Finance's informal limits.
    auto_adjust:
        Pass ``auto_adjust=True`` to yfinance (adjusts for splits/dividends).
        Defaults to ``True``.
    """

    def __init__(
        self,
        cache: ParquetCache | None = None,
        rate_limit_pause: float = 0.25,
        auto_adjust: bool = True,
    ) -> None:
        self._cache = cache
        self._rate_limit_pause = rate_limit_pause
        self._auto_adjust = auto_adjust

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: TimeFrame = TimeFrame.DAILY,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars for *symbol* over [start, end).

        Checks the local Parquet cache first.  Missing ranges are fetched
        from Yahoo Finance and merged back into the cache.
        """
        symbol = symbol.upper()

        # --- cache lookup ------------------------------------------------
        if self._cache is not None:
            cached = self._cache.get(symbol, start, end)
            if cached is not None and not cached.empty:
                logger.debug("Cache hit for %s [%s, %s)", symbol, start, end)
                return cached

        # --- network fetch -----------------------------------------------
        logger.debug("Fetching %s from yfinance [%s, %s)", symbol, start, end)
        df = self._download_single(symbol, start, end, timeframe)

        # --- populate cache ----------------------------------------------
        if self._cache is not None and not df.empty:
            self._cache.put(symbol, df)

        return df

    def get_multiple(
        self,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
        timeframe: TimeFrame = TimeFrame.DAILY,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch OHLCV bars for multiple *symbols* efficiently.

        Uses ``yf.download`` with ``group_by="ticker"`` for a single bulk
        HTTP request when more than one symbol is requested.  Falls back to
        sequential single-symbol downloads on parse errors.

        Symbols that return no data are omitted from the result dict.
        """
        symbols = [s.upper() for s in symbols]

        # Check which symbols are already fully cached
        uncached: list[str] = []
        results: dict[str, pd.DataFrame] = {}

        if self._cache is not None:
            for sym in symbols:
                cached = self._cache.get(sym, start, end)
                if cached is not None and not cached.empty:
                    results[sym] = cached
                else:
                    uncached.append(sym)
        else:
            uncached = list(symbols)

        if not uncached:
            logger.debug("All %d symbols served from cache.", len(symbols))
            return results

        logger.debug("Bulk-downloading %d symbols from yfinance.", len(uncached))

        if len(uncached) == 1:
            sym = uncached[0]
            df = self._download_single(sym, start, end, timeframe)
            if not df.empty:
                results[sym] = df
                if self._cache is not None:
                    self._cache.put(sym, df)
            return results

        # Bulk download
        try:
            bulk = self._bulk_download(uncached, start, end, timeframe)
        except Exception as exc:
            logger.warning(
                "Bulk download failed (%s); falling back to sequential.", exc
            )
            bulk = self._sequential_download(uncached, start, end, timeframe)

        for sym, df in bulk.items():
            if not df.empty:
                results[sym] = df
                if self._cache is not None:
                    self._cache.put(sym, df)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_single(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: TimeFrame,
    ) -> pd.DataFrame:
        """Download one symbol from yfinance and normalise to standard schema."""
        interval = _TF_TO_YF[timeframe]
        try:
            ticker = yf.Ticker(symbol)
            raw = ticker.history(
                start=_to_date_str(start),
                end=_to_date_str(end),
                interval=interval,
                auto_adjust=self._auto_adjust,
            )
        except Exception as exc:
            _handle_yf_exception(symbol, exc)
            return _empty_df()

        if raw is None or raw.empty:
            logger.info("No data returned for %s over [%s, %s)", symbol, start, end)
            return _empty_df()

        return _normalise(raw)

    def _bulk_download(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: TimeFrame,
    ) -> dict[str, pd.DataFrame]:
        """
        Use yf.download with group_by='ticker' for an efficient bulk request.
        """
        interval = _TF_TO_YF[timeframe]
        raw = yf.download(
            tickers=symbols,
            start=_to_date_str(start),
            end=_to_date_str(end),
            interval=interval,
            auto_adjust=self._auto_adjust,
            group_by="ticker",
            threads=True,
            progress=False,
        )

        if raw is None or raw.empty:
            return {}

        result: dict[str, pd.DataFrame] = {}

        if len(symbols) == 1:
            # yf.download returns a flat df for a single ticker
            df = _normalise(raw)
            if not df.empty:
                result[symbols[0]] = df
            return result

        # Multi-ticker: top-level columns are tickers
        for sym in symbols:
            try:
                ticker_df = raw[sym]
            except KeyError:
                logger.warning("Symbol %s missing from bulk download result.", sym)
                continue
            if ticker_df.empty or ticker_df.dropna(how="all").empty:
                logger.info("No data for %s in bulk result.", sym)
                continue
            df = _normalise(ticker_df)
            if not df.empty:
                result[sym] = df

        return result

    def _sequential_download(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: TimeFrame,
    ) -> dict[str, pd.DataFrame]:
        """Fall-back: download symbols one by one with a small pause."""
        result: dict[str, pd.DataFrame] = {}
        for i, sym in enumerate(symbols):
            try:
                df = self._download_single(sym, start, end, timeframe)
                if not df.empty:
                    result[sym] = df
            except (DataProviderError, Exception) as exc:
                logger.warning("Failed to download %s: %s", sym, exc)
            if i < len(symbols) - 1:
                time.sleep(self._rate_limit_pause)
        return result

    def supports_timeframe(self, timeframe: TimeFrame) -> bool:
        return timeframe in _TF_TO_YF


# ---------------------------------------------------------------------------
# Module-level utilities
# ---------------------------------------------------------------------------


def _to_date_str(dt: datetime) -> str:
    """Convert datetime to YYYY-MM-DD string expected by yfinance."""
    return dt.strftime("%Y-%m-%d")


def _normalise(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Coerce a raw yfinance DataFrame to the standard Quantify OHLCV schema.

    * Lowercase column names.
    * Keep only open/high/low/close/volume; add NaN vwap column.
    * Ensure DatetimeIndex is UTC-aware.
    * Drop rows where all OHLCV values are NaN.
    * Sort ascending by timestamp.
    """
    df = raw.copy()
    df.columns = [c.lower() for c in df.columns]

    # Map any yfinance variant names to canonical names
    rename_map = {
        "adj close": "close",
        "adj_close": "close",
    }
    df = df.rename(columns=rename_map)

    # Retain only the columns we care about
    available = [c for c in _OHLCV_COLS if c in df.columns]
    df = df[available].copy()

    # Add missing columns as NaN
    for col in _OHLCV_COLS:
        if col not in df.columns:
            df[col] = float("nan")

    df["vwap"] = float("nan")

    # Drop rows where OHLCV are entirely NaN (e.g. weekends in weekly data)
    df = df.dropna(subset=["open", "high", "low", "close"], how="all")

    if df.empty:
        return _empty_df()

    # Enforce dtypes
    for col in ("open", "high", "low", "close", "vwap"):
        df[col] = df[col].astype("float64")
    df["volume"] = df["volume"].fillna(0).astype("int64")

    # Ensure tz-aware index
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    df.index.name = "timestamp"
    return df.sort_index()[_OHLCV_COLS + ["vwap"]]


def _empty_df() -> pd.DataFrame:
    """Return an empty DataFrame with the standard OHLCV schema."""
    df = pd.DataFrame(columns=_OHLCV_COLS + ["vwap"])
    df.index = pd.DatetimeIndex([], name="timestamp", tz="UTC")
    for col in ("open", "high", "low", "close", "vwap"):
        df[col] = df[col].astype("float64")
    df["volume"] = df["volume"].astype("int64")
    return df


def _handle_yf_exception(symbol: str, exc: Exception) -> None:
    """Translate yfinance exceptions into Quantify provider exceptions."""
    msg = str(exc).lower()
    if "no data found" in msg or "no timezone found" in msg:
        raise SymbolNotFoundError(symbol) from exc
    if "429" in msg or "too many requests" in msg or "rate limit" in msg:
        raise RateLimitError(retry_after=60.0) from exc
    raise DataProviderError(f"yfinance error for {symbol}: {exc}") from exc
