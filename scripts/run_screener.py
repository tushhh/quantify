#!/usr/bin/env python
"""
Run the full 500-stock screener and POST results to the Heroku callback URL.
Called by GitHub Actions after model training completes.
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.cache import ParquetCache
from quantify.data.universe import get_sp500, get_sector_map
from quantify.data.features import FeatureEngine
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s – %(message)s")
log = logging.getLogger("run_screener")

_SCREENER_UNIVERSE_SIZE = 500


def main():
    chat_id = os.getenv("INPUT_CHAT_ID", "")
    callback_url = os.getenv("INPUT_HEROKU_CALLBACK_URL", "")
    internal_secret = os.getenv("INTERNAL_API_SECRET", "")

    log.info("Starting full screener for %d stocks (chat_id=%s)", _SCREENER_UNIVERSE_SIZE, chat_id or "none")

    universe = get_sp500()[:_SCREENER_UNIVERSE_SIZE]
    sector_map = get_sector_map()

    now_utc = datetime.now(timezone.utc)
    end_dt = now_utc
    start_dt = end_dt - timedelta(days=365 * 3)

    cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")
    provider = YFinanceProvider(cache=ParquetCache(cache_dir=cache_dir))

    log.info("Fetching market data for %d symbols...", len(universe))
    raw_data = provider.get_multiple(universe, start=start_dt, end=end_dt)

    if not raw_data:
        log.error("No market data returned.")
        _send_callback(callback_url, chat_id, internal_secret, status="failed", error="No market data")
        sys.exit(1)

    strat = MLReturnPredictorStrategy(universe=universe, train_enabled=False)

    log.info("Computing features for %d symbols...", len(raw_data))
    engine = FeatureEngine()
    features = engine.compute(raw_data, required=strat.get_required_features())

    enriched = {}
    for sym, df in raw_data.items():
        feat_df = features.get(sym)
        enriched[sym] = df.join(feat_df, how="left", rsuffix="_feat") if feat_df is not None else df

    log.info("Generating signals...")
    signals = strat.generate_signals(enriched)

    if not signals:
        log.error("No signals generated.")
        _send_callback(callback_url, chat_id, internal_secret, status="failed", error="No signals generated")
        sys.exit(1)

    longs = sorted([s for s in signals if s.direction == "long"], key=lambda x: x.strength, reverse=True)
    shorts = sorted([s for s in signals if s.direction == "short"], key=lambda x: x.strength, reverse=True)

    items = []
    for s in longs + shorts:
        pred_return = s.metadata.get("predicted_return_1d", 0.0) if s.metadata else 0.0
        explanations = s.metadata.get("explanations", []) if s.metadata else []
        items.append({
            "symbol": s.symbol,
            "strength": s.strength,
            "side": s.direction,
            "sector": sector_map.get(s.symbol, "Unknown"),
            "name": s.symbol,
            "predicted_return_pct": round(float(pred_return) * 100, 2),
            "explanations": explanations,
        })

    session_date = now_utc.date().isoformat()
    result = {
        "status": "ok",
        "mode": "previous_close",
        "date": session_date,
        "signals": items,
        "cached": False,
        "cache_age_minutes": 0.0,
        "universe_size": len(universe),
        "model_metrics": strat._model_metrics,
    }

    log.info("Screener complete: %d longs, %d shorts", len(longs), len(shorts))
    _send_callback(callback_url, chat_id, internal_secret, status="complete", result=result)


def _send_callback(url: str, chat_id: str, secret: str, status: str, result: dict = None, error: str = None):
    if not url:
        log.info("No callback URL set — skipping notification.")
        return

    payload = {
        "chat_id": chat_id,
        "status": status,
        "result_json": json.dumps(result) if result else None,
        "error": error,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if secret:
        req.add_header("X-Internal-Secret", secret)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log.info("Callback sent to %s (HTTP %d)", url, resp.status)
    except Exception as e:
        log.error("Failed to send callback to %s: %s", url, e)


if __name__ == "__main__":
    main()
