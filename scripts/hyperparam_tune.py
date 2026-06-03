"""
Simple hyperparameter tuning for LightGBM using GridSearchCV on the assembled
training dataset from `MLReturnPredictorStrategy._build_training_data`.

Uses Spearman IC as the scoring metric (not MSE) and purged time-series CV.
"""
import json
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import make_scorer

from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.cache import ParquetCache
from quantify.data.features import FeatureEngine
from quantify.data.universe import get_sp500
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy


def spearman_scorer(y_true, y_pred):
    """Spearman rank correlation — the metric we actually care about for stock ranking."""
    try:
        return float(pd.Series(y_true).corr(pd.Series(y_pred), method='spearman'))
    except Exception:
        return 0.0


def run_tuning():
    universe = get_sp500()[:50]
    prov = YFinanceProvider(cache=ParquetCache(cache_dir='./data/cache'))
    now = datetime.now(timezone.utc)
    data = prov.get_multiple(universe, start=now - timedelta(days=365 * 3), end=now)

    engine = FeatureEngine()
    features = engine.compute(data, required=list(MLReturnPredictorStrategy().get_required_features()))
    enriched = {s: data[s].join(features.get(s, pd.DataFrame()), how='left') for s in universe}

    strat = MLReturnPredictorStrategy(universe=universe)
    X_all, y_all = strat._build_training_data(enriched)
    if X_all is None:
        print('No training data available')
        return

    X = X_all.values
    y = y_all.values

    from lightgbm import LGBMRegressor

    param_grid = {
        'n_estimators': [100, 200, 300],
        'learning_rate': [0.01, 0.05],
        'max_depth': [4, 6],
        'min_child_samples': [10, 20, 50],
    }

    tscv = TimeSeriesSplit(n_splits=5, gap=5)  # gap=5 for embargo
    scorer = make_scorer(spearman_scorer, greater_is_better=True)

    grid = GridSearchCV(
        LGBMRegressor(random_state=42, verbose=-1),
        param_grid,
        cv=tscv,
        scoring=scorer,
        n_jobs=-1,
        verbose=1,
    )
    grid.fit(X, y)

    print(f'Best params: {grid.best_params_}')
    print(f'Best Spearman IC: {grid.best_score_:.4f}')
    with open('tuning_results.json', 'w') as fh:
        json.dump({
            'best_params': grid.best_params_,
            'best_spearman_ic': float(grid.best_score_),
        }, fh, indent=2)


if __name__ == '__main__':
    run_tuning()
