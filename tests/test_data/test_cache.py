"""
tests/test_data/test_cache.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for quantify.data.cache.ParquetCache.

Covers:
- put / get roundtrip
- cache miss when file absent
- cache hit / miss for date range coverage
- merge behaviour (new data overwrites on conflict)
- invalidate single symbol
- invalidate_all
- cached_symbols listing
- info metadata
- thread-safety smoke test
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from quantify.data.cache import ParquetCache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df(
    start: str = "2022-01-01",
    periods: int = 30,
    base_price: float = 100.0,
    seed: int = 0,
) -> pd.DataFrame:
    """Create a small UTC-indexed OHLCV DataFrame."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, periods=periods, freq="B", tz="UTC")
    close = base_price * np.cumprod(1 + rng.normal(0, 0.01, periods))
    high = close * (1 + rng.uniform(0, 0.01, periods))
    low = close * (1 - rng.uniform(0, 0.01, periods))
    open_ = close * (1 + rng.uniform(-0.005, 0.005, periods))
    volume = rng.integers(1_000_000, 10_000_000, periods)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _utc(dt_str: str) -> datetime:
    return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParquetCachePutGet:
    """Basic put/get semantics."""

    def test_get_miss_on_empty_cache(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        result = cache.get("AAPL", _utc("2022-01-01"), _utc("2022-02-01"))
        assert result is None

    def test_put_creates_file(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        df = _make_df()
        cache.put("AAPL", df)
        assert (tmp_path / "AAPL.parquet").exists()

    def test_get_hit_full_range(self, tmp_path: Path) -> None:
        """Data exactly covers the requested range → cache hit."""
        cache = ParquetCache(cache_dir=tmp_path)
        df = _make_df(start="2022-01-01", periods=30)
        cache.put("AAPL", df)

        result = cache.get("AAPL", _utc("2022-01-01"), _utc("2022-01-15"))
        assert result is not None
        assert not result.empty

    def test_get_miss_range_not_covered(self, tmp_path: Path) -> None:
        """Requested start is before the cached start → cache miss."""
        cache = ParquetCache(cache_dir=tmp_path)
        df = _make_df(start="2022-02-01", periods=20)
        cache.put("MSFT", df)

        # Request starts before cached data
        result = cache.get("MSFT", _utc("2022-01-01"), _utc("2022-03-01"))
        assert result is None

    def test_get_returns_slice_within_range(self, tmp_path: Path) -> None:
        """Cache returns only data within [start, end)."""
        cache = ParquetCache(cache_dir=tmp_path)
        df = _make_df(start="2022-01-01", periods=60)
        cache.put("GOOGL", df)

        start = _utc("2022-01-10")
        end = _utc("2022-02-01")
        result = cache.get("GOOGL", start, end)
        assert result is not None
        # All returned rows must be in [start, end)
        assert (result.index >= start).all()
        assert (result.index < end).all()

    def test_put_empty_df_is_noop(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        cache.put("AAPL", pd.DataFrame())
        assert not (tmp_path / "AAPL.parquet").exists()

    def test_case_insensitive_symbol(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        df = _make_df()
        cache.put("aapl", df)
        assert (tmp_path / "AAPL.parquet").exists()
        result = cache.get("aapl", _utc("2022-01-01"), _utc("2022-01-20"))
        assert result is not None


class TestParquetCacheMerge:
    """put() merges new data with existing cached data."""

    def test_merge_extends_range(self, tmp_path: Path) -> None:
        """Putting new data with a later date range extends the cache."""
        cache = ParquetCache(cache_dir=tmp_path)

        df1 = _make_df(start="2022-01-01", periods=20)
        cache.put("AAPL", df1)

        df2 = _make_df(start="2022-02-01", periods=20)
        cache.put("AAPL", df2)

        info = cache.info("AAPL")
        # The cache should now span both ranges
        assert info["rows"] > 20

    def test_merge_new_data_overwrites_conflict(self, tmp_path: Path) -> None:
        """When index timestamps overlap, new data takes precedence."""
        cache = ParquetCache(cache_dir=tmp_path)

        df1 = _make_df(start="2022-01-03", periods=5, base_price=100.0)
        cache.put("AAPL", df1)

        # Same dates, different prices
        df2 = _make_df(start="2022-01-03", periods=5, base_price=200.0)
        cache.put("AAPL", df2)

        # Re-read from disk
        result = cache.get(
            "AAPL",
            df2.index.min().to_pydatetime(),
            df2.index.max().to_pydatetime() + timedelta(days=1),
        )
        assert result is not None
        # New (higher) prices should have won
        assert result["close"].mean() > 150.0


class TestParquetCacheInvalidate:
    """invalidate() and invalidate_all() behaviour."""

    def test_invalidate_removes_file(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        cache.put("AAPL", _make_df())
        assert (tmp_path / "AAPL.parquet").exists()

        removed = cache.invalidate("AAPL")
        assert removed is True
        assert not (tmp_path / "AAPL.parquet").exists()

    def test_invalidate_nonexistent_returns_false(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        assert cache.invalidate("ZZZZZ") is False

    def test_invalidate_all(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            cache.put(ticker, _make_df(seed=hash(ticker) % 100))

        assert len(cache.cached_symbols()) == 3
        n_deleted = cache.invalidate_all()
        assert n_deleted == 3
        assert cache.cached_symbols() == []


class TestParquetCacheInfo:
    """info() returns correct metadata."""

    def test_info_unknown_symbol(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        assert cache.info("UNKNOWN") == {}

    def test_info_known_symbol(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        df = _make_df(periods=25)
        cache.put("AMZN", df)
        info = cache.info("AMZN")
        assert info["symbol"] == "AMZN"
        assert info["rows"] == 25
        assert "start" in info
        assert "end" in info
        assert info["size_bytes"] > 0


class TestParquetCacheCachedSymbols:
    """cached_symbols() returns sorted list."""

    def test_cached_symbols_empty(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        assert cache.cached_symbols() == []

    def test_cached_symbols_populated(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        for ticker in ["TSLA", "AAPL", "MSFT"]:
            cache.put(ticker, _make_df(seed=hash(ticker) % 100))
        symbols = cache.cached_symbols()
        assert symbols == sorted(symbols)
        assert set(symbols) == {"AAPL", "MSFT", "TSLA"}


class TestParquetCacheThreadSafety:
    """Concurrent writes to the same symbol do not corrupt the cache."""

    def test_concurrent_writes(self, tmp_path: Path) -> None:
        cache = ParquetCache(cache_dir=tmp_path)
        errors: list[Exception] = []

        def writer(seed: int) -> None:
            try:
                df = _make_df(seed=seed, periods=10)
                cache.put("SHARED", df)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent write errors: {errors}"
        # The file must exist and be readable
        assert (tmp_path / "SHARED.parquet").exists()
        info = cache.info("SHARED")
        assert info["rows"] >= 10
