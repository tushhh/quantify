"""
Simple walk-forward backtest runner for `MLReturnPredictorStrategy`.
Runs expanding-window walk-forward retrain and evaluates IC and hit-rate.
"""
from datetime import datetime, timezone, timedelta
import json
import numpy as np
import pandas as pd

from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.cache import ParquetCache
from quantify.data.features import FeatureEngine
from quantify.data.universe import get_sp500
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy
from quantify.backtest.engine import BacktestEngine


def run_walk_forward(start_date: datetime, end_date: datetime, universe_size: int = 100, retrain_interval_days: int = 21):
    universe = get_sp500()[:universe_size]
    provider = YFinanceProvider(cache=ParquetCache(cache_dir="./data/cache"))
    data = provider.get_multiple(universe, start=start_date - timedelta(days=4000), end=end_date)

    engine = BacktestEngine(strategies=[], initial_capital=100_000)

    # Prepare features once
    engine_data = data.copy()
    fe = FeatureEngine()
    feats = fe.compute(data, required=list(MLReturnPredictorStrategy().get_required_features()))
    enriched = {s: data[s].join(feats.get(s, pd.DataFrame()), how='left') for s in universe}

    # Walk-forward: re-train every `retrain_interval_days` on data up to that date
    current = start_date
    results = []
    strat = MLReturnPredictorStrategy(universe=universe)

    while current <= end_date:
        window_end = current
        train_start = current - timedelta(days=365 * 3)
        # Build train/eval slices
        slice_data = {s: df.loc[(df.index.date >= train_start.date()) & (df.index.date < window_end.date())] for s, df in enriched.items()}

        X_all, y_all = strat._build_training_data(slice_data)
        if X_all is None or len(X_all) < strat.min_train_bars:
            print(f"Skipping retrain at {window_end.date()}; insufficient samples")
            current += timedelta(days=retrain_interval_days)
            continue

        strat._train_model(X_all, y_all)
        # Evaluate one-step ahead predictions for the next period
        next_period_end = window_end + timedelta(days=retrain_interval_days)
        pred_slice = {s: df.loc[(df.index.date >= window_end.date()) & (df.index.date < next_period_end.date())] for s, df in enriched.items()}
        preds = strat._predict(pred_slice)

        # Compute IC and hit-rate
        true_returns = {}
        for s, df in pred_slice.items():
            if df is None or df.empty:
                continue
            try:
                true_returns[s] = float(df['close'].pct_change(5).iloc[-1])
            except Exception:
                continue
        paired = [(preds.get(s), true_returns.get(s)) for s in preds.keys() if s in true_returns]
        paired = [(p, t) for p, t in paired if p is not None and t is not None]
        if not paired:
            current += timedelta(days=retrain_interval_days)
            continue
        ps = np.array([p for p, _ in paired])
        ts = np.array([t for _, t in paired])
        ic = float(pd.Series(ps).corr(pd.Series(ts), method='spearman'))
        hit = float((np.sign(ps) == np.sign(ts)).mean())
        results.append({'date': window_end.date().isoformat(), 'ic': ic, 'hit_rate': hit, 'n': len(paired)})
        print(f"{window_end.date()}: IC={ic:.4f}, hit={hit:.3f}, n={len(paired)}")
        current += timedelta(days=retrain_interval_days)

    print('Walk-forward complete. Sample results:')
    print(json.dumps(results[-10:], indent=2))


if __name__ == '__main__':
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * 2)
    run_walk_forward(start, end)
