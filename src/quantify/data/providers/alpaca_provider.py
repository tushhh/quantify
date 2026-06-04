"""
Alpaca data provider for the Quantify trading system.

Uses the official ``alpaca-py`` SDK (``alpaca.data.historical``) to fetch
historical OHLCV bar data from Alpaca Markets.

API credentials are resolved in the following priority order:
1. Constructor arguments ``api_key`` / ``secret_key``.
2. Environment variables ``ALPACA_API_KEY`` / ``ALPACA_SECRET_KEY``.
3. A local config file at ``~/.quantify/alpaca.json``
   (keys: ``"api_key"`` / ``"secret_key"``).

Data Tiers
----------
Free ("IEX") feed only covers IEX-listed trades.  A paid subscription
gives access to the consolidated ("SIP") feed.  Set ``feed="sip"`` when
initialising with a paid account.

Usage
-----
>>> provider = AlpacaProvider(feed="iex")
>>> df = provider.get_bars("AAPL", start=datetime(2023, 1, 1), end=datetime(2024, 1, 1))
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd

from quantify.data.cache import ParquetCache
from quantify.data.models import TimeFrame
from quantify.data.providers.base import (
    AuthenticationError,
    DataProvider,
    DataProviderError,
    RateLimitError,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional alpaca-py import — deferred so the rest of the system works even
# when alpaca-py is not installed.
# ---------------------------------------------------------------------------
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame as AlpacaTimeFrame
    from alpaca.data.timeframe import TimeFrameUnit

    _ALPACA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ALPACA_AVAILABLE = False
    StockHistoricalDataClient = None  # type: ignore[assignment,misc]
    StockBarsRequest = None  # type: ignore[assignment,misc]
    AlpacaTimeFrame = None  # type: ignore[assignment]
    TimeFrameUnit = None  # type: ignore[assignment]

# Map Quantify TimeFrame → alpaca-py TimeFrame
def _make_alpaca_tf_map():
    if not _ALPACA_AVAILABLE:
        return {}
    return {
        TimeFrame.MINUTE: AlpacaTimeFrame(1, TimeFrameUnit.Minute),
        TimeFrame.HOUR: AlpacaTimeFrame(1, TimeFrameUnit.Hour),
        TimeFrame.DAILY: AlpacaTimeFrame(1, TimeFrameUnit.Day),
        TimeFrame.WEEKLY: AlpacaTimeFrame(1, TimeFrameUnit.Week),
    }


_OHLCV_COLS = ["open", "high", "low", "close", "volume"]
_CONFIG_PATH = Path.home() / ".quantify" / "alpaca.json"


class AlpacaProvider(DataProvider):
    """
    DataProvider backed by Alpaca Markets via ``alpaca-py``.

    Parameters
    ----------
    api_key:
        Alpaca API key ID.  Falls back to ``ALPACA_API_KEY`` env var.
    secret_key:
        Alpaca secret key.  Falls back to ``ALPACA_SECRET_KEY`` env var.
    feed:
        Data feed — ``"iex"`` (free) or ``"sip"`` (paid subscription).
    cache:
        Optional :class:`~quantify.data.cache.ParquetCache` instance.
    paper:
        When True, uses paper-trading credentials (same keys, different
        endpoint behaviour).  Only relevant for live trading; has no effect
        on historical data.

    Raises
    ------
    AuthenticationError
        If no API credentials can be found.
    ImportError
        If ``alpaca-py`` is not installed.
    """

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        feed: str = "iex",
        cache: ParquetCache | None = None,
        paper: bool = False,
    ) -> None:
        if not _ALPACA_AVAILABLE:
            raise ImportError(
                "alpaca-py is required for AlpacaProvider.  "
                "Install it with: pip install alpaca-py"
            )

        self._api_key, self._secret_key = _resolve_credentials(api_key, secret_key)
        self._feed = feed.lower()
        self._cache = cache
        self._paper = paper
        self._tf_map = _make_alpaca_tf_map()

        self._client = StockHistoricalDataClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
        )
        logger.debug(
            "AlpacaProvider initialised (feed=%s, paper=%s)", self._feed, self._paper
        )

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
        """Fetch OHLCV bars for a single *symbol* from Alpaca."""
        symbol = symbol.upper()

        if self._cache is not None:
            cached = self._cache.get(symbol, start, end)
            if cached is not None and not cached.empty:
                logger.debug("Cache hit for %s [%s, %s)", symbol, start, end)
                return cached

        df = self._fetch_bars([symbol], start, end, timeframe).get(symbol, _empty_df())

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
        """Fetch OHLCV bars for multiple *symbols* in a single Alpaca request."""
        symbols = [s.upper() for s in symbols]

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
            return results

        fetched = self._fetch_bars(uncached, start, end, timeframe)

        for sym, df in fetched.items():
            if not df.empty:
                results[sym] = df
                if self._cache is not None:
                    self._cache.put(sym, df)

        return results

    def supports_timeframe(self, timeframe: TimeFrame) -> bool:
        return timeframe in self._tf_map

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_bars(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        timeframe: TimeFrame,
    ) -> dict[str, pd.DataFrame]:
        """
        Issue a StockBarsRequest to the Alpaca API and parse the response.
        """
        alpaca_tf = self._tf_map.get(timeframe)
        if alpaca_tf is None:
            raise DataProviderError(
                f"AlpacaProvider does not support timeframe {timeframe!r}"
            )

        # Alpaca expects tz-aware datetimes; coerce if needed
        start_utc = _ensure_utc(start)
        end_utc = _ensure_utc(end)

        request = StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=alpaca_tf,
            start=start_utc,
            end=end_utc,
            feed=self._feed,
            adjustment="split",  # adjust for splits; pass "all" for div+split
        )

        try:
            response = self._client.get_stock_bars(request)
        except Exception as exc:
            _handle_alpaca_exception(symbols, exc)
            return {}

        return _parse_response(response, symbols)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_response(response, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """
    Convert an Alpaca BarSet response object to a dict of standard DataFrames.

    alpaca-py returns either a ``BarSet`` (multi-symbol) or a plain dict.
    We handle both.
    """
    result: dict[str, pd.DataFrame] = {}

    # response.data is a dict[str, list[Bar]] in alpaca-py >= 0.8
    data: dict = {}
    if hasattr(response, "data"):
        data = response.data
    elif isinstance(response, dict):
        data = response
    else:
        try:
            data = dict(response)
        except Exception:
            logger.warning("Could not parse Alpaca response: %r", type(response))
            return result

    for sym in symbols:
        bars = data.get(sym, [])
        if not bars:
            logger.info("No bars returned for %s", sym)
            continue

        rows = []
        for bar in bars:
            rows.append(
                {
                    "timestamp": getattr(bar, "timestamp", None),
                    "open": getattr(bar, "open", float("nan")),
                    "high": getattr(bar, "high", float("nan")),
                    "low": getattr(bar, "low", float("nan")),
                    "close": getattr(bar, "close", float("nan")),
                    "volume": int(getattr(bar, "volume", 0)),
                    "vwap": getattr(bar, "vwap", float("nan")),
                }
            )

        if not rows:
            continue

        df = pd.DataFrame(rows).set_index("timestamp")
        df.index = pd.DatetimeIndex(df.index, name="timestamp")

        if df.index.tzinfo is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        for col in ("open", "high", "low", "close", "vwap"):
            df[col] = df[col].astype("float64")
        df["volume"] = df["volume"].astype("int64")

        df = df.sort_index()
        result[sym] = df[_OHLCV_COLS + ["vwap"]]

    return result


# ---------------------------------------------------------------------------
# Credential resolution
# ---------------------------------------------------------------------------


def _resolve_credentials(
    api_key: str | None, secret_key: str | None
) -> tuple[str, str]:
    """
    Resolve Alpaca API credentials from constructor args → env → config file.
    """
    key = api_key or os.environ.get("ALPACA_API_KEY")
    secret = secret_key or os.environ.get("ALPACA_SECRET_KEY")

    if not key or not secret:
        if _CONFIG_PATH.exists():
            try:
                cfg = json.loads(_CONFIG_PATH.read_text())
                key = key or cfg.get("api_key")
                secret = secret or cfg.get("secret_key")
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not read Alpaca config at %s: %s", _CONFIG_PATH, exc)

    if not key or not secret:
        raise AuthenticationError(
            "Alpaca API credentials not found.  Supply them via constructor "
            "arguments, ALPACA_API_KEY / ALPACA_SECRET_KEY environment "
            f"variables, or {_CONFIG_PATH}."
        )

    return str(key), str(secret)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _empty_df() -> pd.DataFrame:
    df = pd.DataFrame(columns=_OHLCV_COLS + ["vwap"])
    df.index = pd.DatetimeIndex([], name="timestamp", tz="UTC")
    for col in ("open", "high", "low", "close", "vwap"):
        df[col] = df[col].astype("float64")
    df["volume"] = df["volume"].astype("int64")
    return df


def _handle_alpaca_exception(symbols: list[str], exc: Exception) -> None:
    """Translate alpaca-py exceptions to Quantify provider exceptions."""
    msg = str(exc).lower()
    if "forbidden" in msg or "unauthorized" in msg or "403" in msg or "401" in msg:
        raise AuthenticationError(f"Alpaca authentication failed: {exc}") from exc
    if "429" in msg or "too many requests" in msg or "rate limit" in msg:
        raise RateLimitError(retry_after=60.0) from exc
    if "not found" in msg or "404" in msg:
        raise SymbolNotFoundError(symbols[0] if len(symbols) == 1 else str(symbols)) from exc
    raise DataProviderError(f"Alpaca API error for {symbols}: {exc}") from exc
