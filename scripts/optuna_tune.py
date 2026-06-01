"""
Optuna-based tuning for LightGBM using the assembled training dataset.
"""
from datetime import datetime, timezone, timedelta
import optuna
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import make_scorer

from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.cache import ParquetCache
from quantify.data.features import FeatureEngine
from quantify.data.universe import get_sp500
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy


def spearman_obj(preds, train_data):
    # custom objective is not used; we use the spearman scorer in evaluation
    return 'spearman', 0.0, True


def objective(trial):
    universe = get_sp500()[:50]
    prov = YFinanceProvider(cache=ParquetCache(cache_dir='./data/cache'))
    now = datetime.now(timezone.utc)
    data = prov.get_multiple(universe, start=now - timedelta(days=365*3), end=now)

    engine = FeatureEngine()
    features = engine.compute(data, required=list(MLReturnPredictorStrategy().get_required_features()))
    enriched = {s: data[s].join(features.get(s, pd.DataFrame()), how='left') for s in universe}

    strat = MLReturnPredictorStrategy(universe=universe)
    X_all, y_all = strat._build_training_data(enriched)
    if X_all is None:
        return 0.0

    params = {
        'n_estimators': trial.suggest_categorical('n_estimators', [100, 200, 300]),
        'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.1, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 8),
        'num_leaves': trial.suggest_int('num_leaves', 15, 127),
        'subsample': trial.suggest_float('subsample', 0.5, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.4, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 1.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 1.0),
    }

    from lightgbm import LGBMRegressor
    from sklearn.model_selection import cross_val_score

    model = LGBMRegressor(random_state=42, **params)
    tscv = TimeSeriesSplit(n_splits=5)
    try:
        scores = cross_val_score(model, X_all, y_all, cv=tscv, scoring='neg_mean_squared_error', n_jobs=-1)
        return float(np.mean(scores))
    except Exception:
        return 0.0


if __name__ == '__main__':
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=20)
    print('Best trial:', study.best_trial.params)
    with open('optuna_best.json', 'w') as fh:
        import json
        json.dump(study.best_trial.params, fh)
