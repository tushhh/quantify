"""
quantify.screener
~~~~~~~~~~~~~~~~~
Shared prediction pipeline used by the API screener endpoint, the GitHub
Actions full-screener job, the offline training script, and the walk-forward
validator.

Pipeline: fetch OHLCV → compute technical features → join → add sector RS
features → add fundamental features → (optionally) generate signals →
(optionally) filter earnings blackout.
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from quantify.data.fundamentals import add_fundamental_features, fetch_fundamentals
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

log = logging.getLogger(__name__)

# 4 calendar years of history comfortably covers the 756-trading-day
# training window plus feature warm-up (252-day rolling features).
DEFAULT_LOOKBACK_DAYS = 365 * 4


def prepare_enriched_data(
    universe: list[str],
    start_dt: datetime,
    end_dt: datetime,
    cache_dir: str = "./data/cache",
    strategy: Optional[MLReturnPredictorStrategy] = None,
    include_fundamentals: bool = True,
    include_sector_rs: bool = True,
) -> tuple[dict[str, pd.DataFrame], MLReturnPredictorStrategy]:
    """
    Fetch OHLCV data for ``universe`` and enrich it with all feature columns
    the strategy needs (technical via FeatureEngine, sector RS via
    :func:`quantify.data.sector.add_sector_rs_features`, and fundamental via
    :func:`quantify.data.fundamentals.add_fundamental_features`).

    Returns ``(enriched, strategy)``.  Raises ValueError if the data provider
    returns nothing.
    """
    # Imported lazily so this module stays importable without yfinance installed
    # (e.g. in unit-test environments).
    from quantify.data.cache import ParquetCache
    from quantify.data.features import FeatureEngine
    from quantify.data.providers.yfinance_provider import YFinanceProvider

    if strategy is None:
        strategy = MLReturnPredictorStrategy(
            universe=universe, train_enabled=False, use_sector_rs=True
        )

    provider = YFinanceProvider(cache=ParquetCache(cache_dir=cache_dir))
    log.info("screener: fetching data for %d symbols…", len(universe))
    raw_data = provider.get_multiple(universe, start=start_dt, end=end_dt)

    if not raw_data:
        raise ValueError("Market data provider returned empty results.")

    log.info("screener: computing technical features for %d symbols…", len(raw_data))
    engine = FeatureEngine()
    features = engine.compute(raw_data, required=strategy.get_required_features())

    enriched: dict[str, pd.DataFrame] = {}
    for sym, raw_df in raw_data.items():
        feat_df = features.get(sym)
        if feat_df is not None:
            enriched[sym] = raw_df.join(feat_df, how="left", rsuffix="_feat")
        else:
            enriched[sym] = raw_df

    if include_sector_rs and strategy.use_sector_rs:
        log.info("screener: adding sector relative-strength features…")
        from quantify.data.sector import add_sector_rs_features
        from quantify.data.universe import get_sector_map
        enriched = add_sector_rs_features(
            enriched, get_sector_map(), cache_dir=cache_dir
        )

    if include_fundamentals and strategy.use_fundamentals:
        log.info("screener: adding fundamental features…")
        fundamentals = fetch_fundamentals(list(enriched.keys()), cache_dir=cache_dir)
        enriched = add_fundamental_features(enriched, fundamentals)

    return enriched, strategy


def run_screener(
    universe: list[str],
    end_dt: Optional[datetime] = None,
    cache_dir: str = "./data/cache",
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    exclude_earnings_days: int = 3,
) -> dict:
    """
    Run the full prediction screener over ``universe`` and return a
    PredictionResponse-shaped plain dict (the API layer converts it to the
    Pydantic model; scripts serialise it directly).

    Parameters
    ----------
    universe:
        Ticker symbols to screen.
    end_dt:
        Reference date/time (default: now UTC).
    cache_dir:
        Root for all on-disk caches.
    lookback_days:
        Calendar days of history to fetch.
    exclude_earnings_days:
        Suppress signals for stocks with a confirmed earnings date within
        this many calendar days of *end_dt* (before or after).  Set to 0
        to disable earnings filtering.
    """
    from quantify.data.universe import get_sector_map

    if end_dt is None:
        end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=lookback_days)

    enriched, strategy = prepare_enriched_data(
        universe, start_dt, end_dt, cache_dir=cache_dir
    )

    log.info("screener: generating signals…")
    signals = strategy.generate_signals(enriched)

    # ----- Earnings blackout filter -----
    if exclude_earnings_days > 0 and signals:
        blackout = _fetch_earnings_blackout(
            universe,
            window_days=exclude_earnings_days,
            reference_date=end_dt.date() if hasattr(end_dt, "date") else date.today(),
            cache_dir=cache_dir,
        )
        if blackout:
            before = len(signals)
            signals = [s for s in signals if s.symbol not in blackout]
            log.info(
                "screener: earnings blackout removed %d signal(s) (%d symbols near earnings)",
                before - len(signals),
                len(blackout),
            )

    longs = sorted(
        [s for s in signals if s.direction == "long"],
        key=lambda x: x.strength,
        reverse=True,
    )
    shorts = sorted(
        [s for s in signals if s.direction == "short"],
        key=lambda x: x.strength,
        reverse=True,
    )

    sector_map = get_sector_map()
    items = []
    for s in longs + shorts:
        meta = s.metadata or {}
        pred_return = meta.get(
            "predicted_return_1d", meta.get("predicted_return_5d", 0.0)
        )
        items.append({
            "symbol": s.symbol,
            "strength": s.strength,
            "side": s.direction,
            "sector": sector_map.get(s.symbol, "Unknown"),
            "name": s.symbol,
            "predicted_return_pct": round(float(pred_return) * 100, 2),
            "explanations": meta.get("explanations", []),
        })

    return {
        "status": "ok",
        "mode": "previous_close",
        "date": end_dt.date().isoformat(),
        "signals": items,
        "cached": False,
        "cache_age_minutes": 0.0,
        "universe_size": len(universe),
        "model_metrics": strategy._model_metrics,
    }


def _fetch_earnings_blackout(
    tickers: list[str],
    window_days: int,
    reference_date: date,
    cache_dir: str = "./data/cache",
) -> frozenset[str]:
    """
    Return the set of tickers with a confirmed earnings date within
    ±*window_days* calendar days of *reference_date*.

    Results are cached per reference_date so repeat calls within the same
    trading day hit disk, not yfinance.  Failures for individual tickers are
    silently ignored — the goal is to avoid scheduling risk, not to be
    exhaustive, so a network blip never blocks the screener.
    """
    cache_path = os.path.join(
        cache_dir, "earnings", f"blackout_{reference_date.isoformat()}.json"
    )
    if os.path.exists(cache_path):
        try:
            with open(cache_path) as fh:
                return frozenset(json.load(fh))
        except Exception:
            pass

    window_start = reference_date - timedelta(days=window_days)
    window_end = reference_date + timedelta(days=window_days)

    def _check_ticker(sym: str) -> str | None:
        try:
            import yfinance as yf

            ticker = yf.Ticker(sym)
            earnings_dates: list[date] = []

            # Primary: earnings_dates property (DataFrame indexed by Timestamp)
            try:
                ed_df = ticker.earnings_dates
                if ed_df is not None and not ed_df.empty:
                    for ts in ed_df.index:
                        try:
                            earnings_dates.append(pd.Timestamp(ts).date())
                        except Exception:
                            pass
            except Exception:
                pass

            # Fallback: calendar dict/DataFrame
            if not earnings_dates:
                try:
                    cal = ticker.calendar
                    if isinstance(cal, dict):
                        raw = cal.get("Earnings Date", [])
                        for d in (raw if hasattr(raw, "__iter__") else [raw]):
                            try:
                                earnings_dates.append(pd.Timestamp(d).date())
                            except Exception:
                                pass
                    elif isinstance(cal, pd.DataFrame) and not cal.empty:
                        for col in ("Earnings Date",):
                            if col in cal.columns:
                                for d in cal[col].dropna():
                                    try:
                                        earnings_dates.append(pd.Timestamp(d).date())
                                    except Exception:
                                        pass
                except Exception:
                    pass

            for ed in earnings_dates:
                if window_start <= ed <= window_end:
                    return sym
        except Exception:
            pass
        return None

    blackout: set[str] = set()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_check_ticker, sym): sym for sym in tickers}
        for fut in as_completed(futures):
            result = fut.result()
            if result is not None:
                blackout.add(result)

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    try:
        with open(cache_path, "w") as fh:
            json.dump(sorted(blackout), fh)
    except Exception:
        pass

    log.info("screener: earnings blackout cache written (%d tickers)", len(blackout))
    return frozenset(blackout)


__all__ = [
    "prepare_enriched_data",
    "run_screener",
    "_fetch_earnings_blackout",
    "DEFAULT_LOOKBACK_DAYS",
]
