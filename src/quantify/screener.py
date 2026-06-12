"""
quantify.screener
~~~~~~~~~~~~~~~~~
Shared prediction pipeline used by the API screener endpoint, the GitHub
Actions full-screener job, the offline training script, and the walk-forward
validator.

Pipeline: fetch OHLCV → compute technical features → join → add fundamental
features → (optionally) generate signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
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
) -> tuple[dict[str, pd.DataFrame], MLReturnPredictorStrategy]:
    """
    Fetch OHLCV data for ``universe`` and enrich it with all feature columns
    the strategy needs (technical via FeatureEngine, fundamental via
    quantify.data.fundamentals).

    Returns ``(enriched, strategy)``.  Raises ValueError if the data provider
    returns nothing.
    """
    # Imported lazily so this module stays importable without yfinance installed
    # (e.g. in unit-test environments).
    from quantify.data.cache import ParquetCache
    from quantify.data.features import FeatureEngine
    from quantify.data.providers.yfinance_provider import YFinanceProvider

    if strategy is None:
        strategy = MLReturnPredictorStrategy(universe=universe, train_enabled=False)

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
) -> dict:
    """
    Run the full prediction screener over ``universe`` and return a
    PredictionResponse-shaped plain dict (the API layer converts it to the
    Pydantic model; scripts serialise it directly).
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


__all__ = ["prepare_enriched_data", "run_screener", "DEFAULT_LOOKBACK_DAYS"]
