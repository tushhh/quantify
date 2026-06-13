"""
Sector relative-strength features.

For each stock, computes its N-day return relative to the corresponding GICS
sector ETF (SPDR suite).  A positive value means the stock outperformed its
sector; negative means underperformance.

These are cross-sectional features — they require data from *multiple* symbols
(the sector ETFs) and cannot be computed per-symbol inside ``FeatureEngine``.
They are added to each stock's DataFrame by :func:`add_sector_rs_features`,
which is called from ``quantify.screener.prepare_enriched_data``.

Feature names
-------------
``sector_rs_5d``  — 5-day excess return vs sector ETF.
``sector_rs_21d`` — 21-day excess return vs sector ETF.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Sequence

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GICS sector → SPDR ETF ticker
# ---------------------------------------------------------------------------

SECTOR_ETF_MAP: dict[str, str] = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}

_HORIZONS_DEFAULT: tuple[int, ...] = (5, 21)


def add_sector_rs_features(
    data: dict[str, pd.DataFrame],
    sector_map: dict[str, str],
    horizons: tuple[int, ...] = _HORIZONS_DEFAULT,
    cache_dir: str = "./data/cache",
) -> dict[str, pd.DataFrame]:
    """
    Enrich each stock's DataFrame with sector relative-strength columns.

    For each horizon ``n`` in *horizons*, a column ``sector_rs_{n}d`` is added:

        sector_rs_{n}d = stock_return_{n}d − sector_etf_return_{n}d

    Stocks whose sector has no ETF mapping (``"Unknown"`` etc.) receive NaN for
    all sector RS columns.  ETF data is fetched via :class:`YFinanceProvider`
    and cached in *cache_dir* using :class:`ParquetCache`.

    Parameters
    ----------
    data:
        Mapping from ticker → OHLCV DataFrame (must have a ``"close"`` column
        and a DatetimeIndex).
    sector_map:
        Mapping from ticker → GICS sector string.
    horizons:
        Return horizons (trading days) to compute, default ``(5, 21)``.
    cache_dir:
        Root directory for the Parquet cache.

    Returns
    -------
    dict[str, pd.DataFrame]
        Same keys as *data*; each DataFrame gains the new columns in-place on
        a copy (original DataFrames are not mutated).
    """
    if not data:
        return data

    # Determine date range from the input data.  Add a small lookback buffer
    # so the longest horizon has enough bars from the very first date.
    all_indices = [df.index for df in data.values() if not df.empty]
    if not all_indices:
        return data

    start_dt: datetime = min(idx.min() for idx in all_indices)
    end_dt: datetime = max(idx.max() for idx in all_indices)

    # Make timezone-aware for the provider
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)

    # Extra buffer so rolling returns have history from day 1
    buffer = timedelta(days=max(horizons) * 3)
    start_dt = start_dt - buffer

    # yfinance treats `end` as EXCLUSIVE ([start, end)).  end_dt here is the
    # stocks' last bar (the most recent trading day), so fetching the ETFs with
    # end=end_dt would drop that very day — leaving sector_rs NaN at every
    # stock's last bar and causing _predict to skip all symbols.  Adding 1 day
    # is sufficient: if end_dt is a trading day (e.g. Friday Jun 12), the cache
    # checks bdate_range([start, Jun 13), inclusive="left") whose last element
    # is Jun 12, matching the cached end — so cache hits are preserved.
    end_dt = end_dt + timedelta(days=1)

    # Identify which sector ETFs we actually need
    needed_etfs: set[str] = set()
    for sym in data:
        sector = sector_map.get(sym, "Unknown")
        etf = SECTOR_ETF_MAP.get(sector)
        if etf:
            needed_etfs.add(etf)

    if not needed_etfs:
        log.warning("sector_rs: no sector ETF mappings found — skipping sector RS features")
        _add_nan_columns(data, horizons)
        return data

    # Fetch ETF OHLCV via the existing provider stack (respects cache)
    etf_closes: dict[str, pd.Series] = {}
    try:
        from quantify.data.cache import ParquetCache
        from quantify.data.providers.yfinance_provider import YFinanceProvider

        provider = YFinanceProvider(cache=ParquetCache(cache_dir=cache_dir))
        etf_data = provider.get_multiple(list(needed_etfs), start=start_dt, end=end_dt)
        for etf, etf_df in etf_data.items():
            if not etf_df.empty and "close" in etf_df.columns:
                etf_closes[etf] = etf_df["close"]
    except Exception as exc:
        log.warning("sector_rs: ETF data fetch failed (%s) — filling NaN", exc)
        _add_nan_columns(data, horizons)
        return data

    if not etf_closes:
        log.warning("sector_rs: ETF data empty — filling NaN")
        _add_nan_columns(data, horizons)
        return data

    # Pre-compute rolling returns for each ETF at each horizon
    etf_returns: dict[str, dict[int, pd.Series]] = {}
    for etf, close in etf_closes.items():
        etf_returns[etf] = {n: close.pct_change(n) for n in horizons}

    # Enrich each stock's DataFrame
    result: dict[str, pd.DataFrame] = {}
    for sym, df in data.items():
        df = df.copy()
        sector = sector_map.get(sym, "Unknown")
        etf = SECTOR_ETF_MAP.get(sector)

        if etf is None or etf not in etf_returns:
            for n in horizons:
                df[f"sector_rs_{n}d"] = np.nan
        else:
            stock_close = df["close"]
            for n in horizons:
                stock_ret = stock_close.pct_change(n)
                etf_ret = etf_returns[etf][n].reindex(df.index)
                df[f"sector_rs_{n}d"] = stock_ret - etf_ret

        result[sym] = df

    log.info(
        "sector_rs: added %s columns for %d symbols (%d ETFs fetched)",
        [f"sector_rs_{n}d" for n in horizons],
        len(result),
        len(etf_closes),
    )
    return result


def _add_nan_columns(
    data: dict[str, pd.DataFrame],
    horizons: Sequence[int],
) -> None:
    """Add NaN sector RS columns in-place when ETF data is unavailable."""
    for df in data.values():
        for n in horizons:
            df[f"sector_rs_{n}d"] = np.nan
