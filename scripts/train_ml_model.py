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

from quantify.data.universe import Universe, get_russell1000
from quantify.screener import prepare_enriched_data, DEFAULT_LOOKBACK_DAYS
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
log = logging.getLogger("train_ml_model")

# Use top 500 symbols for screener performance consistency
_SCREENER_UNIVERSE_SIZE = 500

def main():
    log.info("Starting offline ML model training")

    # 1. Define universe and timeline (4 years of history to support the
    #    756-trading-day training window plus feature warm-up)
    try:
        universe = Universe.from_wikipedia().tickers[:_SCREENER_UNIVERSE_SIZE]
    except Exception as e:
        log.warning("Failed to fetch from Wikipedia, falling back to Russell 1000: %s", e)
        universe = get_russell1000()[:_SCREENER_UNIVERSE_SIZE]
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=DEFAULT_LOOKBACK_DAYS)

    # 2. Fetch data and compute all features (technical + fundamental)
    cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")
    strat = MLReturnPredictorStrategy(universe=universe)
    log.info(f"Fetching and enriching data for {len(universe)} symbols from {start_dt.date()} to {end_dt.date()}...")
    enriched, strat = prepare_enriched_data(
        universe, start_dt, end_dt, cache_dir=cache_dir, strategy=strat
    )

    # 3. Build Training dataset
    log.info("Building cross-sectional training dataset...")
    X_all, y_all = strat._build_training_data(enriched)

    if X_all is None or len(X_all) < strat.min_train_bars:
        log.error(f"Insufficient training data. Found {len(X_all) if X_all is not None else 0} valid samples, require {strat.min_train_bars}.")
        sys.exit(1)

    # 4. Train the model
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
