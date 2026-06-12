#!/usr/bin/env python
"""
Standalone script to train the ML return predictor model.
Designed to be run in a CI/CD environment (like GitHub Actions) with ample RAM,
so the model artifact (.joblib) can be pushed to an orphan branch and downloaded
by the lightweight API server.
"""

import logging
import os
import sys
from datetime import datetime, timezone, timedelta

# Add src to path so we can run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.cache import ParquetCache
from quantify.data.universe import get_sp500
from quantify.data.features import FeatureEngine
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
log = logging.getLogger("train_ml_model")

# Use top 100 symbols for screener performance consistency
_SCREENER_UNIVERSE_SIZE = 500

def main():
    log.info("Starting offline ML model training")
    
    # 1. Define universe and timeline (need ~3 years of history to get ~2.5 years of features)
    universe = get_sp500()[:_SCREENER_UNIVERSE_SIZE]
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=365 * 3)
    
    # 2. Fetch raw data
    cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")
    provider = YFinanceProvider(cache=ParquetCache(cache_dir=cache_dir))
    log.info(f"Fetching market data for {len(universe)} symbols from {start_dt.date()} to {end_dt.date()}...")
    raw_data = provider.get_multiple(universe, start=start_dt, end=end_dt)
    
    if not raw_data:
        log.error("Failed to fetch market data. Aborting training.")
        sys.exit(1)
        
    # 3. Compute Features
    strat = MLReturnPredictorStrategy(universe=universe)
    log.info("Computing features...")
    engine = FeatureEngine()
    features = engine.compute(raw_data, required=strat.get_required_features())
    
    # 4. Join features with raw data
    log.info("Merging features with OHLCV data...")
    enriched = {}
    for sym, raw_df in raw_data.items():
        feat_df = features.get(sym)
        if feat_df is not None:
            enriched[sym] = raw_df.join(feat_df, how="left", rsuffix="_feat")
        else:
            enriched[sym] = raw_df

    # 5. Build Training dataset
    log.info("Building cross-sectional training dataset...")
    X_all, y_all = strat._build_training_data(enriched)
    
    if X_all is None or len(X_all) < strat.min_train_bars:
        log.error(f"Insufficient training data. Found {len(X_all) if X_all is not None else 0} valid samples, require {strat.min_train_bars}.")
        sys.exit(1)
        
    # 6. Train the model
    # _train_model will automatically save it to ./models/ml_return_predictor.joblib
    log.info("Initiating model training...")
    strat._train_model(X_all, y_all)
    
    # Verify the file was created
    if os.path.exists("./models/ml_return_predictor.joblib"):
        size_mb = os.path.getsize("./models/ml_return_predictor.joblib") / (1024*1024)
        log.info(f"Model successfully saved! File size: {size_mb:.2f} MB")
    else:
        log.error("Model file was not created!")
        sys.exit(1)

if __name__ == "__main__":
    main()
