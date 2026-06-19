"""
quantify.data.earnings
~~~~~~~~~~~~~~~~~~~~~~
Fetch earnings history from yfinance and derive point-in-time PEAD features.

Both features are computed with strict point-in-time safety (only past
earnings events are used for each row date), making them valid for
walk-forward backtesting.

  earnings_surprise_pct — EPS beat / miss at most recent report, as a decimal
      fraction (0.05 = 5% beat, -0.03 = 3% miss).  Decayed linearly to 0 over
      DRIFT_WINDOW_DAYS calendar days.  Encodes PEAD: stocks that beat
      consensus continue drifting up for ~60 days post-report.

  days_since_earnings   — Calendar days since the most recent report, capped
      at DAYS_SINCE_CAP.  Lets the model learn the non-linear decay in
      surprise informativeness as the market digests the news.
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

EARNINGS_FEATURES: list[str] = ["earnings_surprise_pct", "days_since_earnings"]

DRIFT_WINDOW_DAYS: int = 60   # PEAD is largely exhausted after ~60 calendar days
DAYS_SINCE_CAP: int = 252     # Cap staleness at 1 year; beyond this is noise
_CACHE_TTL_HOURS: int = 24    # Earnings come out quarterly; refresh at most daily
_MAX_WORKERS: int = 20        # Concurrent yfinance threads


def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "earnings_history.json")


def _load_cache(cache_dir: str) -> dict:
    try:
        with open(_cache_path(cache_dir)) as fh:
            c = json.load(fh)
        return c if isinstance(c, dict) else {}
    except Exception:
        return {}


def _save_cache(cache_dir: str, cache: dict) -> None:
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(_cache_path(cache_dir), "w") as fh:
            json.dump(cache, fh)
    except Exception as exc:
        log.warning("earnings: failed to persist cache: %s", exc)


def _fetch_one(symbol: str) -> Optional[list[dict]]:
    """
    Pull confirmed past earnings for one symbol from yfinance.

    Returns a sorted list of {date, surprise_pct} dicts for rows where
    Reported EPS is not NaN (past, confirmed reports only — no future dates).
    Returns None on hard failure, empty list if ticker has no earnings history.
    """
    try:
        import yfinance as yf

        df = yf.Ticker(symbol).earnings_dates
        if df is None or df.empty:
            return []

        surprise_col = next((c for c in df.columns if "surprise" in c.lower()), None)
        reported_col = next((c for c in df.columns if "reported" in c.lower()), None)
        if surprise_col is None:
            return []

        records = []
        for dt, row in df.iterrows():
            # Skip unconfirmed / future entries (no Reported EPS yet)
            if reported_col and pd.isna(row.get(reported_col)):
                continue
            try:
                if hasattr(dt, "tz_convert"):
                    dt = dt.tz_convert("UTC").tz_localize(None)
                date_str = str(pd.Timestamp(dt).date())
            except Exception:
                date_str = str(dt)[:10]
            surprise = row.get(surprise_col)
            if pd.notna(surprise):
                records.append({"date": date_str, "surprise_pct": float(surprise)})

        return sorted(records, key=lambda r: r["date"])
    except Exception as exc:
        log.debug("earnings: fetch failed for %s: %s", symbol, exc)
        return None


def fetch_earnings(
    symbols: list[str],
    cache_dir: str = "./data/cache",
    ttl_hours: int = _CACHE_TTL_HOURS,
) -> dict[str, list[dict]]:
    """
    Fetch and cache earnings history for each symbol.

    Returns ``{symbol: [{date: str, surprise_pct: float}, ...]}`` for symbols
    with confirmed past reports, sorted chronologically.  Symbols with no data
    or persistent failures are omitted.
    """
    cache = _load_cache(cache_dir)
    ttl_seconds = ttl_hours * 3600
    now_ts = time.time()
    result: dict[str, list[dict]] = {}
    to_fetch: list[str] = []
    cache_dirty = False

    for sym in symbols:
        entry = cache.get(sym)
        if entry and (now_ts - float(entry.get("fetched_at", 0))) < ttl_seconds:
            data = entry.get("data")
            if data is not None:
                result[sym] = data
        else:
            to_fetch.append(sym)

    if to_fetch:
        log.info("earnings: fetching history for %d symbols…", len(to_fetch))
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_one, sym): sym for sym in to_fetch}
            for i, fut in enumerate(as_completed(futures), 1):
                sym = futures[fut]
                if i % 50 == 0:
                    log.info("earnings: fetched %d/%d", i, len(to_fetch))
                try:
                    data = fut.result()
                except Exception as exc:
                    log.debug("earnings: fetch raised for %s: %s", sym, exc)
                    data = None

                if data is not None:
                    cache[sym] = {"fetched_at": now_ts, "data": data}
                    cache_dirty = True
                    if data:
                        result[sym] = data
                elif cache.get(sym, {}).get("data"):
                    log.debug("earnings: using stale cache for %s", sym)
                    result[sym] = cache[sym]["data"]

    if cache_dirty:
        _save_cache(cache_dir, cache)

    log.info("earnings: resolved history for %d/%d symbols", len(result), len(symbols))
    return result


def add_earnings_features(
    data: dict[str, pd.DataFrame],
    earnings: dict[str, list[dict]],
    drift_window: int = DRIFT_WINDOW_DAYS,
    days_since_cap: int = DAYS_SINCE_CAP,
) -> dict[str, pd.DataFrame]:
    """
    Append two point-in-time PEAD features to each symbol's DataFrame.

    For every row date, only earnings events on or before that date are used
    (no look-ahead).  The surprise is decayed linearly to 0 over
    *drift_window* calendar days, mirroring the empirical PEAD decay curve.

    Parameters
    ----------
    data:
        ``{symbol: OHLCV DataFrame}`` with a datetime index.
    earnings:
        Output of :func:`fetch_earnings` — confirmed past earnings only.
    drift_window:
        Calendar days over which the EPS surprise decays to 0.
    days_since_cap:
        Maximum value for ``days_since_earnings``.
    """
    out: dict[str, pd.DataFrame] = {}

    for symbol, df in data.items():
        df = df.copy()
        records = earnings.get(symbol, [])

        df["earnings_surprise_pct"] = 0.0
        df["days_since_earnings"] = float(days_since_cap)

        if not records:
            out[symbol] = df
            continue

        earn_dates = np.array(
            [np.datetime64(r["date"], "D") for r in records], dtype="datetime64[D]"
        )
        earn_surprise = np.array(
            [r["surprise_pct"] / 100.0 for r in records], dtype=float
        )

        df_dates = pd.to_datetime(df.index).normalize().values.astype("datetime64[D]")

        # For each row date, find the index of the most recent past earnings (date <=)
        past_idx = np.searchsorted(earn_dates, df_dates, side="right") - 1
        has_past = past_idx >= 0

        # Safe index into earn_dates (rows without past earnings use idx=0 then masked)
        safe_idx = np.clip(past_idx, 0, len(earn_dates) - 1)
        last_earn_day = np.where(has_past, earn_dates[safe_idx], df_dates)

        # Days since last earnings: int difference works on datetime64[D]
        days_since = (df_dates.astype("int64") - last_earn_day.astype("int64")).astype(float)
        days_since = np.where(has_past, np.clip(days_since, 0, days_since_cap), float(days_since_cap))

        in_window = has_past & (days_since <= drift_window)
        decay = np.clip(1.0 - days_since / drift_window, 0.0, 1.0)
        raw_surprise = np.where(has_past, earn_surprise[safe_idx], 0.0)

        df["earnings_surprise_pct"] = np.where(in_window, raw_surprise * decay, 0.0)
        df["days_since_earnings"] = days_since

        out[symbol] = df

    return out


__all__ = ["fetch_earnings", "add_earnings_features", "EARNINGS_FEATURES"]
