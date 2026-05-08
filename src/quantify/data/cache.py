"""
Parquet-based disk cache for OHLCV market data.

Design
------
* One Parquet file per symbol, stored at ``<cache_dir>/<SYMBOL>.parquet``.
* ``put`` merges new data with whatever is already on disk (union by index,
  de-duplicated, sorted ascending) so the cache always holds the longest
  contiguous range seen so far.
* ``get`` checks whether the requested [start, end) range is fully covered;
  if yes it returns the slice from disk; if no (or file absent) it returns
  ``None`` so the caller knows it must hit the network.
* Thread-safe via a per-symbol reentrant lock — safe for concurrent use in
  multi-threaded back-test runners.

Usage
-----
>>> cache = ParquetCache()                          # defaults to data/cache/
>>> cache.put("AAPL", df)
>>> slice_ = cache.get("AAPL", start, end)          # None if not cached
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Relative to project root; used when no absolute path is supplied
_DEFAULT_CACHE_SUBDIR = "data/cache"

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]
_ALL_COLS = _OHLCV_COLS + ["vwap"]


class ParquetCache:
    """
    Disk-backed cache that persists OHLCV DataFrames as Parquet files.

    Parameters
    ----------
    cache_dir:
        Directory where ``.parquet`` files are stored.  Created on first
        write if it does not exist.  Defaults to ``data/cache/`` relative
        to the current working directory.
    compression:
        Parquet compression codec.  ``"snappy"`` gives the best
        read/write balance; ``"zstd"`` for smaller files at modest CPU cost.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        compression: str = "snappy",
    ) -> None:
        if cache_dir is None:
            self._cache_dir = Path.cwd() / _DEFAULT_CACHE_SUBDIR
        else:
            self._cache_dir = Path(cache_dir)

        self._compression = compression
        self._locks: dict[str, threading.RLock] = {}
        self._global_lock = threading.Lock()  # protects _locks dict itself

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def cache_dir(self) -> Path:
        """Resolved path to the cache directory."""
        return self._cache_dir

    def get(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> Optional[pd.DataFrame]:
        """
        Return cached OHLCV data for *symbol* over [start, end).

        Returns ``None`` when:
        * The symbol has no cached file.
        * The cached file does not fully cover [start, end).

        Parameters
        ----------
        symbol:
            Ticker symbol (case-insensitive; stored upper-case).
        start:
            Inclusive start of the requested range.
        end:
            Exclusive end of the requested range.

        Returns
        -------
        pd.DataFrame or None
        """
        symbol = symbol.upper()
        path = self._path(symbol)

        with self._lock_for(symbol):
            if not path.exists():
                return None

            try:
                df = pd.read_parquet(path)
            except Exception as exc:
                logger.warning("Failed to read cache for %s: %s", symbol, exc)
                return None

            if df.empty:
                return None

            start_utc = _ensure_utc(start)
            end_utc = _ensure_utc(end)

            # Ensure index is tz-aware for comparison
            idx = df.index
            if idx.tzinfo is None:
                idx = idx.tz_localize("UTC")
                df.index = idx

            cached_start = idx.min()
            cached_end = idx.max()

            # Coverage check: cached range must fully contain [start, end)
            # We allow a one-day buffer on end because end is exclusive and
            # daily data typically stops at the last trading day before end.
            if cached_start > start_utc or cached_end < end_utc - pd.Timedelta(days=1):
                logger.debug(
                    "Cache miss for %s: requested [%s, %s), cached [%s, %s]",
                    symbol,
                    start_utc.date(),
                    end_utc.date(),
                    cached_start.date(),
                    cached_end.date(),
                )
                return None

            # Return the requested slice
            slice_ = df.loc[start_utc:end_utc]  # type: ignore[misc]
            # Exclude the exact end timestamp (exclusive range semantics)
            slice_ = slice_[slice_.index < end_utc]

            logger.debug(
                "Cache hit for %s: %d bars [%s, %s)",
                symbol,
                len(slice_),
                start_utc.date(),
                end_utc.date(),
            )
            return slice_

    def put(self, symbol: str, df: pd.DataFrame) -> None:
        """
        Persist *df* to disk, merging with any previously cached data.

        New bars are unioned with existing cached bars.  Duplicate index
        entries are resolved by keeping the *new* value (last wins), which
        handles corrected/revised data gracefully.

        Parameters
        ----------
        symbol:
            Ticker symbol.
        df:
            Standard OHLCV DataFrame with DatetimeIndex.
        """
        if df is None or df.empty:
            return

        symbol = symbol.upper()
        path = self._path(symbol)

        with self._lock_for(symbol):
            df = _coerce(df)
            path.parent.mkdir(parents=True, exist_ok=True)

            if path.exists():
                try:
                    existing = pd.read_parquet(path)
                    existing = _coerce(existing)
                    # Merge: existing first so new data overwrites on conflict
                    merged = (
                        pd.concat([existing, df])
                        .loc[~pd.concat([existing, df]).index.duplicated(keep="last")]
                        .sort_index()
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not read existing cache for %s (%s); overwriting.",
                        symbol,
                        exc,
                    )
                    merged = df
            else:
                merged = df

            try:
                merged.to_parquet(path, compression=self._compression, index=True)
                logger.debug(
                    "Cache updated for %s: %d bars total, file=%s",
                    symbol,
                    len(merged),
                    path.name,
                )
            except Exception as exc:
                logger.error("Failed to write cache for %s: %s", symbol, exc)

    def invalidate(self, symbol: str) -> bool:
        """
        Delete the cached Parquet file for *symbol*.

        Parameters
        ----------
        symbol:
            Ticker symbol (case-insensitive).

        Returns
        -------
        bool
            True if the file existed and was deleted; False otherwise.
        """
        symbol = symbol.upper()
        path = self._path(symbol)

        with self._lock_for(symbol):
            if path.exists():
                try:
                    path.unlink()
                    logger.info("Cache invalidated for %s", symbol)
                    return True
                except OSError as exc:
                    logger.error("Failed to delete cache for %s: %s", symbol, exc)
            return False

    def invalidate_all(self) -> int:
        """
        Delete *all* cached Parquet files in ``cache_dir``.

        Returns
        -------
        int
            Number of files deleted.
        """
        count = 0
        if not self._cache_dir.exists():
            return 0
        for p in self._cache_dir.glob("*.parquet"):
            try:
                p.unlink()
                count += 1
            except OSError as exc:
                logger.error("Failed to delete cache file %s: %s", p, exc)
        logger.info("Cache cleared: %d files deleted.", count)
        return count

    def cached_symbols(self) -> list[str]:
        """Return a sorted list of ticker symbols currently in the cache."""
        if not self._cache_dir.exists():
            return []
        return sorted(p.stem.upper() for p in self._cache_dir.glob("*.parquet"))

    def info(self, symbol: str) -> dict:
        """
        Return metadata about the cached data for *symbol*.

        Returns a dict with keys: ``symbol``, ``path``, ``rows``,
        ``start``, ``end``, ``size_bytes``.  Returns an empty dict if
        the symbol is not cached.
        """
        symbol = symbol.upper()
        path = self._path(symbol)
        if not path.exists():
            return {}
        try:
            df = pd.read_parquet(path)
            return {
                "symbol": symbol,
                "path": str(path),
                "rows": len(df),
                "start": df.index.min(),
                "end": df.index.max(),
                "size_bytes": path.stat().st_size,
            }
        except Exception as exc:
            logger.warning("Could not read cache info for %s: %s", symbol, exc)
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path(self, symbol: str) -> Path:
        return self._cache_dir / f"{symbol.upper()}.parquet"

    def _lock_for(self, symbol: str) -> threading.RLock:
        with self._global_lock:
            if symbol not in self._locks:
                self._locks[symbol] = threading.RLock()
            return self._locks[symbol]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _ensure_utc(dt: datetime) -> pd.Timestamp:
    """Convert a datetime to a UTC-aware pandas Timestamp."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return pd.Timestamp(dt).tz_convert("UTC")


def _coerce(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the DataFrame has the standard OHLCV schema and a UTC-aware index.
    """
    df = df.copy()

    # Ensure UTC-aware DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.DatetimeIndex(df.index, name="timestamp")
    if df.index.tzinfo is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    df.index.name = "timestamp"

    # Add missing columns
    if "vwap" not in df.columns:
        df["vwap"] = float("nan")

    for col in ("open", "high", "low", "close", "vwap"):
        if col in df.columns:
            df[col] = df[col].astype("float64")
    if "volume" in df.columns:
        df["volume"] = df["volume"].astype("int64")

    # Drop symbol column if present (redundant in per-symbol files)
    if "symbol" in df.columns:
        df = df.drop(columns=["symbol"])

    # Keep only known columns in canonical order
    keep = [c for c in _ALL_COLS if c in df.columns]
    return df[keep].sort_index()
