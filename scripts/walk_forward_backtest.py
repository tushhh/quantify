"""
Simple walk-forward backtest runner for `MLReturnPredictorStrategy`.
Runs expanding-window walk-forward retrain and evaluates IC and hit-rate.

Key improvements:
- Aligned with the fixed forward return computation
- Reports both raw-return and rank-based metrics
- Tracks cumulative IC over time
"""
from datetime import datetime, timezone, timedelta
import json
import numpy as np
import pandas as pd

from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.cache import ParquetCache
from quantify.data.features import FeatureEngine
from quantify.data.universe import get_sp500
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy, _FORWARD_RETURN_DAYS


def run_walk_forward(start_date: datetime, end_date: datetime, universe_size: int = 100, retrain_interval_days: int = 21):
    universe = get_sp500()[:universe_size]
    provider = YFinanceProvider(cache=ParquetCache(cache_dir="./data/cache"))
    data = provider.get_multiple(universe, start=start_date - timedelta(days=4000), end=end_date)

    # Prepare features once
    fe = FeatureEngine()
    strat_default = MLReturnPredictorStrategy()
    feats = fe.compute(data, required=list(strat_default.get_required_features()))
    enriched = {s: data[s].join(feats.get(s, pd.DataFrame()), how='left') for s in universe if s in data}

    # Walk-forward: re-train every `retrain_interval_days` on data up to that date
    current = start_date
    results = []
    strat = MLReturnPredictorStrategy(universe=universe)

    while current <= end_date:
        window_end = current
        train_start = current - timedelta(days=365 * 3)
        # Build train/eval slices
        slice_data = {
            s: df.loc[(df.index.date >= train_start.date()) & (df.index.date < window_end.date())]
            for s, df in enriched.items()
        }

        X_all, y_all = strat._build_training_data(slice_data)
        if X_all is None or len(X_all) < strat.min_train_bars:
            print(f"Skipping retrain at {window_end.date()}; insufficient samples ({0 if X_all is None else len(X_all)})")
            current += timedelta(days=retrain_interval_days)
            continue

        strat._train_model(X_all, y_all)

        # Evaluate one-step ahead predictions for the next period
        next_period_end = window_end + timedelta(days=retrain_interval_days)
        pred_slice = {
            s: df.loc[(df.index.date >= window_end.date()) & (df.index.date < next_period_end.date())]
            for s, df in enriched.items()
        }
        preds = strat._predict(pred_slice)

        # Compute true forward returns using the corrected formula
        true_returns = {}
        for s, df in pred_slice.items():
            if df is None or df.empty or len(df) < _FORWARD_RETURN_DAYS + 1:
                continue
            try:
                # Correct forward return: close[t+N] / close[t] - 1
                close = df['close']
                if len(close) > _FORWARD_RETURN_DAYS:
                    fwd_ret = float(close.iloc[_FORWARD_RETURN_DAYS] / close.iloc[0] - 1.0)
                    true_returns[s] = fwd_ret
            except Exception:
                continue

        paired = [(preds.get(s), true_returns.get(s)) for s in preds.keys() if s in true_returns]
        paired = [(p, t) for p, t in paired if p is not None and t is not None and not np.isnan(p) and not np.isnan(t)]

        if not paired:
            current += timedelta(days=retrain_interval_days)
            continue

        ps = np.array([p for p, _ in paired])
        ts = np.array([t for _, t in paired])

        ic = float(pd.Series(ps).corr(pd.Series(ts), method='spearman'))
        hit = float((np.sign(ps) == np.sign(ts)).mean())

        # Top-quintile return spread: mean return of top 20% predicted minus bottom 20%
        n = len(ps)
        if n >= 5:
            sorted_idx = np.argsort(ps)
            q = max(1, n // 5)
            top_return = float(np.mean(ts[sorted_idx[-q:]]))
            bottom_return = float(np.mean(ts[sorted_idx[:q]]))
            spread = top_return - bottom_return
        else:
            spread = float('nan')

        result = {
            'date': window_end.date().isoformat(),
            'ic': round(ic, 4),
            'hit_rate': round(hit, 3),
            'spread': round(spread, 6) if not np.isnan(spread) else None,
            'n': len(paired),
        }
        results.append(result)
        print(f"{window_end.date()}: IC={ic:.4f}, hit={hit:.3f}, spread={spread:.4f}, n={len(paired)}")
        current += timedelta(days=retrain_interval_days)

    # Summary statistics
    if results:
        ics = [r['ic'] for r in results]
        hits = [r['hit_rate'] for r in results]
        spreads = [r['spread'] for r in results if r['spread'] is not None]

        print('\n' + '=' * 60)
        print('Walk-forward summary:')
        print(f'  Periods:       {len(results)}')
        print(f'  Mean IC:       {np.mean(ics):.4f} ± {np.std(ics):.4f}')
        print(f'  Mean hit rate: {np.mean(hits):.3f}')
        if spreads:
            print(f'  Mean spread:   {np.mean(spreads):.4f}')
        print(f'  IC > 0:        {sum(1 for ic in ics if ic > 0)}/{len(ics)} ({sum(1 for ic in ics if ic > 0)/len(ics)*100:.0f}%)')
        print('=' * 60)

    # Save full results
    with open('walk_forward_results.json', 'w') as fh:
        json.dump(results, fh, indent=2)
    print(f'\nSaved {len(results)} results to walk_forward_results.json')


if __name__ == '__main__':
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * 2)
    run_walk_forward(start, end)
