"""
Fundamental data features for the ML return predictor.

Fundamentals are fetched once per symbol from yfinance (.info) and cached on
disk with a TTL.  Time-varying valuation ratios are then derived by dividing
the *static* trailing fundamentals by the historical price series:

    earnings_yield_t = trailingEps / close_t
    book_to_market_t = bookValue / close_t
    fcf_yield_t      = freeCashflow / (close_t * sharesOutstanding)
    roe              = returnOnEquity  (static)

Limitation: yfinance only exposes the *latest* trailing fundamentals, so the
numerators are constant across the history window.  The time variation in the
ratios comes from price.  This is an approximation of true point-in-time data
and introduces mild look-ahead in the numerator; acceptable for a ~3-year
training window where fundamentals change slowly relative to prices.
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FUNDAMENTAL_FEATURES = ["earnings_yield", "book_to_market", "fcf_yield", "roe"]

# yfinance .info fields we extract per symbol
_INFO_FIELDS = [
    "trailingEps",
    "bookValue",
    "freeCashflow",
    "sharesOutstanding",
    "returnOnEquity",
]


def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "fundamentals.json")


def _load_cache(cache_dir: str) -> dict[str, dict]:
    path = _cache_path(cache_dir)
    try:
        with open(path) as fh:
            cache = json.load(fh)
        if isinstance(cache, dict):
            return cache
    except Exception:
        pass
    return {}


def _save_cache(cache_dir: str, cache: dict[str, dict]) -> None:
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(_cache_path(cache_dir), "w") as fh:
            json.dump(cache, fh)
    except Exception as exc:
        log.warning("fundamentals: failed to persist cache: %s", exc)


def _fetch_one(symbol: str) -> dict | None:
    """Fetch the needed .info fields for a single symbol; None on failure."""
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info
        if not info:
            return None
        return {field: info.get(field) for field in _INFO_FIELDS}
    except Exception as exc:
        log.debug("fundamentals: yfinance fetch failed for %s: %s", symbol, exc)
        return None


def fetch_fundamentals(
    symbols: list[str],
    cache_dir: str = "./data/cache",
    ttl_days: int = 7,
) -> dict[str, dict]:
    """
    Fetch trailing fundamentals for ``symbols`` from yfinance ``.info``.

    Results are cached on disk at ``{cache_dir}/fundamentals.json`` shaped
    ``{symbol: {"fetched_at": unix_ts, "data": {...}}}`` with a TTL of
    ``ttl_days``.  On fetch failure, any cached entry for the symbol is
    returned even if stale.

    Returns ``{symbol: {field: value}}`` containing only symbols with data.
    """
    cache = _load_cache(cache_dir)
    ttl_seconds = ttl_days * 86400
    now_ts = time.time()

    result: dict[str, dict] = {}
    cache_dirty = False

    # Split into cached (fresh) vs symbols that need a network fetch
    to_fetch: list[str] = []
    for symbol in symbols:
        entry = cache.get(symbol)
        if entry and (now_ts - float(entry.get("fetched_at", 0))) < ttl_seconds:
            data = entry.get("data")
            if data:
                result[symbol] = data
        else:
            to_fetch.append(symbol)

    if to_fetch:
        log.info("fundamentals: fetching %d symbols concurrently…", len(to_fetch))
        # 20 threads: fast enough to cut cold-cache time by ~20x, conservative
        # enough to avoid Yahoo Finance rate limits.
        with ThreadPoolExecutor(max_workers=20) as pool:
            futures = {pool.submit(_fetch_one, sym): sym for sym in to_fetch}
            completed = 0
            for future in as_completed(futures):
                sym = futures[future]
                completed += 1
                if completed % 50 == 0:
                    log.info("fundamentals: fetched %d/%d", completed, len(to_fetch))
                try:
                    data = future.result()
                except Exception as exc:
                    log.debug("fundamentals: fetch raised for %s: %s", sym, exc)
                    data = None

                entry = cache.get(sym)
                if data is not None:
                    cache[sym] = {"fetched_at": now_ts, "data": data}
                    cache_dirty = True
                    result[sym] = data
                elif entry and entry.get("data"):
                    log.debug("fundamentals: using stale cache for %s", sym)
                    result[sym] = entry["data"]

    if cache_dirty:
        _save_cache(cache_dir, cache)

    log.info(
        "fundamentals: resolved fundamentals for %d/%d symbols",
        len(result),
        len(symbols),
    )
    return result


def add_fundamental_features(
    data: dict[str, pd.DataFrame],
    fundamentals: dict[str, dict],
) -> dict[str, pd.DataFrame]:
    """
    Append the four fundamental feature columns to each symbol's DataFrame.

    Columns (see module docstring for derivation):
        earnings_yield, book_to_market, fcf_yield, roe

    Missing fundamental fields produce NaN columns initially.  A second pass
    fills any all-NaN column with the cross-sectional median of the latest
    values across symbols that have data, so symbols without fundamentals
    aren't dropped from training.

    Returns modified copies — input frames are not mutated.
    """
    out: dict[str, pd.DataFrame] = {}

    for symbol, df in data.items():
        df = df.copy()
        fund = fundamentals.get(symbol) or {}

        eps = fund.get("trailingEps")
        book_value = fund.get("bookValue")
        fcf = fund.get("freeCashflow")
        shares = fund.get("sharesOutstanding")
        roe = fund.get("returnOnEquity")

        close = df["close"] if "close" in df.columns else None

        if close is not None and eps is not None:
            df["earnings_yield"] = float(eps) / close
        else:
            df["earnings_yield"] = np.nan

        if close is not None and book_value is not None:
            df["book_to_market"] = float(book_value) / close
        else:
            df["book_to_market"] = np.nan

        if close is not None and fcf is not None and shares:
            df["fcf_yield"] = float(fcf) / (close * float(shares))
        else:
            df["fcf_yield"] = np.nan

        df["roe"] = float(roe) if roe is not None else np.nan

        out[symbol] = df

    # Second pass: fill all-NaN columns with the cross-sectional median of the
    # latest values across symbols that have data.
    for col in FUNDAMENTAL_FEATURES:
        latest_vals = []
        for df in out.values():
            if col in df.columns and not df.empty:
                val = df[col].iloc[-1]
                if pd.notna(val):
                    latest_vals.append(float(val))

        if not latest_vals:
            continue

        median_val = float(np.median(latest_vals))
        for symbol, df in out.items():
            if col in df.columns and df[col].isna().all():
                df[col] = median_val

    return out


__all__ = ["fetch_fundamentals", "add_fundamental_features", "FUNDAMENTAL_FEATURES"]
