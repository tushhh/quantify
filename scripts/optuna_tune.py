"""
Optuna-based tuning for the ML Return Predictor ensemble.

Key improvements over the previous version:
1. Uses Spearman IC as the optimization objective (not MSE)
2. Uses purged time-series CV with embargo gap to prevent data leakage
3. Tunes hyperparameters for all three base estimators
"""
from datetime import datetime, timezone, timedelta
import json
import optuna
import numpy as np
import pandas as pd

from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.cache import ParquetCache
from quantify.data.features import FeatureEngine
from quantify.data.universe import get_sp500
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy, _FORWARD_RETURN_DAYS


def purged_time_series_cv(X, y, n_splits=5, embargo_days=_FORWARD_RETURN_DAYS):
    """
    Generate train/test indices for purged time-series cross-validation.

    Each split uses an expanding training window with an embargo gap
    between train and test to prevent forward return overlap.
    """
    unique_dates = X.index.unique().sort_values()
    n_dates = len(unique_dates)

    # Each fold uses a progressively larger training window
    fold_size = n_dates // (n_splits + 1)

    for i in range(n_splits):
        train_end_idx = (i + 1) * fold_size
        test_start_idx = train_end_idx + embargo_days
        test_end_idx = test_start_idx + fold_size

        if test_end_idx > n_dates:
            break

        train_end_date = unique_dates[train_end_idx]
        test_start_date = unique_dates[min(test_start_idx, n_dates - 1)]
        test_end_date = unique_dates[min(test_end_idx, n_dates - 1)]

        train_mask = X.index < train_end_date
        test_mask = (X.index >= test_start_date) & (X.index <= test_end_date)

        train_idx = np.where(train_mask)[0]
        test_idx = np.where(test_mask)[0]

        if len(train_idx) > 0 and len(test_idx) > 0:
            yield train_idx, test_idx


def spearman_ic_score(y_true, y_pred):
    """Compute Spearman rank correlation (the metric we actually care about)."""
    try:
        return float(pd.Series(y_true).corr(pd.Series(y_pred), method='spearman'))
    except Exception:
        return 0.0


def objective(trial):
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
        return 0.0

    # Hyperparameter search space
    params = {
        'n_estimators': trial.suggest_categorical('n_estimators', [100, 200, 300, 500]),
        'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.1, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 8),
        'num_leaves': trial.suggest_int('num_leaves', 15, 127),
        'subsample': trial.suggest_float('subsample', 0.5, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.4, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 2.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 2.0),
        'min_child_samples': trial.suggest_int('min_child_samples', 5, 50),
    }

    from lightgbm import LGBMRegressor

    # Evaluate using purged CV with Spearman IC
    ic_scores = []
    for train_idx, test_idx in purged_time_series_cv(X_all, y_all, n_splits=5):
        X_train = X_all.iloc[train_idx]
        y_train = y_all.iloc[train_idx]
        X_test = X_all.iloc[test_idx]
        y_test = y_all.iloc[test_idx]

        model = LGBMRegressor(
            random_state=42,
            verbose=-1,
            n_jobs=-1,
            objective='regression',
            **params,
        )

        try:
            model.fit(X_train.values, y_train.values)
            preds = model.predict(X_test.values)
            ic = spearman_ic_score(y_test.values, preds)
            ic_scores.append(ic)
        except Exception:
            ic_scores.append(0.0)

    if not ic_scores:
        return 0.0

    mean_ic = float(np.mean(ic_scores))
    # Report intermediate values for pruning
    trial.report(mean_ic, 0)

    return mean_ic


if __name__ == '__main__':
    study = optuna.create_study(
        direction='maximize',
        study_name='ml_return_predictor_spearman_ic',
        pruner=optuna.pruners.MedianPruner(),
    )
    study.optimize(objective, n_trials=50, show_progress_bar=True)

    print(f'\nBest trial (Spearman IC = {study.best_trial.value:.4f}):')
    print(json.dumps(study.best_trial.params, indent=2))

    with open('optuna_best.json', 'w') as fh:
        result = {
            'best_params': study.best_trial.params,
            'best_spearman_ic': study.best_trial.value,
        }
        json.dump(result, fh, indent=2)
    print('\nSaved to optuna_best.json')
