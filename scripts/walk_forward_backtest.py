#!/usr/bin/env python
"""
Walk-forward validation for `MLReturnPredictorStrategy`.

Per period (every ``--interval`` calendar days):

1. Train on data strictly before ``window_end`` (lookback-limited).
2. Predict as-of the last bar BEFORE ``window_end`` — i.e. ``_predict`` on the
   training slice, which uses each symbol's most recent bar.
3. Realized outcome: for each symbol, the forward return from the last close
   in the training slice to the close ``_FORWARD_RETURN_DAYS`` trading bars
   later, looked up positionally in the full enriched frame.  This keeps the
   prediction and the realized outcome aligned on the same as-of date (the
   previous implementation predicted on the *last* bar of the evaluation
   slice while measuring returns from its *first* bar — a misalignment of
   ~retrain_interval days).
4. Metrics: Spearman IC, hit rate, top-minus-bottom quintile spread.

Outputs ``walk_forward_results.json`` (per-period results) and
``walk_forward_summary.json`` (aggregate statistics).
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quantify.data.fundamentals import FUNDAMENTAL_FEATURES
from quantify.data.universe import get_sp500
from quantify.screener import prepare_enriched_data
from quantify.strategy.ml_return_predictor import (
    MLReturnPredictorStrategy,
    _FORWARD_RETURN_DAYS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s – %(message)s")
log = logging.getLogger("walk_forward")

_RESULTS_PATH = "walk_forward_results.json"
_SUMMARY_PATH = "walk_forward_summary.json"


def _fresh_strategy(universe: list[str]) -> MLReturnPredictorStrategy:
    """Build a strategy that trains from scratch (no persisted-model state)."""
    strat = MLReturnPredictorStrategy(universe=universe, use_sector_rs=True)
    # Discard any model/feature-list loaded from disk in __init__ — walk-forward
    # must train fresh per window — and avoid clobbering the production model
    # artifacts when _train_model persists.
    strat._model = None
    strat.features = (
        list(strat.technical_features)
        + strat.sector_features
        + strat.cs_features
        + (list(FUNDAMENTAL_FEATURES) if strat.use_fundamentals else [])
    )
    strat._model_path = "./models/walk_forward_tmp.joblib"
    strat._model_meta_path = "./models/walk_forward_tmp_meta.json"
    return strat


def run_walk_forward(
    start_date: datetime,
    end_date: datetime,
    universe_size: int = 100,
    retrain_interval_days: int = 21,
) -> list[dict]:
    universe = get_sp500()[:universe_size]

    # Load enough history before start_date to cover the 756-trading-day
    # training window plus feature warm-up.
    cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")
    strat = _fresh_strategy(universe)
    enriched, strat = prepare_enriched_data(
        universe,
        start_dt=start_date - timedelta(days=365 * 4),
        end_dt=end_date,
        cache_dir=cache_dir,
        strategy=strat,
    )

    results: list[dict] = []
    current = start_date

    while current <= end_date:
        window_end = current
        train_start = window_end - timedelta(days=365 * 4)

        # 1. Train on data strictly before window_end (lookback-limited;
        #    _build_training_data further limits to train_window_days).
        train_slice = {
            s: df.loc[
                (df.index.date >= train_start.date())
                & (df.index.date < window_end.date())
            ]
            for s, df in enriched.items()
        }
        train_slice = {s: df for s, df in train_slice.items() if not df.empty}

        X_all, y_all = strat._build_training_data(train_slice)
        if X_all is None or len(X_all) < strat.min_train_bars:
            log.info(
                "Skipping %s; insufficient samples (%d)",
                window_end.date(),
                0 if X_all is None else len(X_all),
            )
            current += timedelta(days=retrain_interval_days)
            continue

        strat._train_model(X_all, y_all, timestamp=window_end)
        if strat._model is None:
            log.warning("Training failed at %s; skipping period", window_end.date())
            current += timedelta(days=retrain_interval_days)
            continue

        # 2. Predict as-of the last bar before window_end: _predict uses the
        #    most recent bar of each frame in the training slice.
        preds = strat._predict(train_slice)
        if not preds:
            current += timedelta(days=retrain_interval_days)
            continue

        # 3. Realized outcome: forward return from the last close in the train
        #    slice to the close _FORWARD_RETURN_DAYS trading bars later,
        #    looked up in the full enriched frame.
        true_returns: dict[str, float] = {}
        for s in preds:
            full_df = enriched.get(s)
            tdf = train_slice.get(s)
            if full_df is None or tdf is None or tdf.empty:
                continue
            try:
                pos = full_df.index.get_loc(tdf.index[-1])
                if not isinstance(pos, (int, np.integer)):
                    continue
                fwd_pos = pos + _FORWARD_RETURN_DAYS
                if fwd_pos >= len(full_df):
                    continue  # not enough future bars
                c0 = float(full_df["close"].iloc[pos])
                c1 = float(full_df["close"].iloc[fwd_pos])
                if c0 > 0:
                    true_returns[s] = c1 / c0 - 1.0
            except Exception:
                continue

        paired = [
            (preds[s], true_returns[s])
            for s in preds
            if s in true_returns
            and not np.isnan(preds[s])
            and not np.isnan(true_returns[s])
        ]

        if not paired:
            current += timedelta(days=retrain_interval_days)
            continue

        ps = np.array([p for p, _ in paired])
        ts = np.array([t for _, t in paired])

        # 4. Metrics
        ic = float(pd.Series(ps).corr(pd.Series(ts), method="spearman"))
        hit = float((np.sign(ps) == np.sign(ts)).mean())

        # Top-minus-bottom quintile spread
        n = len(ps)
        if n >= 5:
            sorted_idx = np.argsort(ps)
            q = max(1, n // 5)
            top_return = float(np.mean(ts[sorted_idx[-q:]]))
            bottom_return = float(np.mean(ts[sorted_idx[:q]]))
            spread = top_return - bottom_return
        else:
            spread = float("nan")

        result = {
            "date": window_end.date().isoformat(),
            "ic": round(ic, 4),
            "hit_rate": round(hit, 3),
            "spread": round(spread, 6) if not np.isnan(spread) else None,
            "n": len(paired),
        }
        results.append(result)
        log.info(
            "%s: IC=%.4f, hit=%.3f, spread=%s, n=%d",
            window_end.date(),
            ic,
            hit,
            f"{spread:.4f}" if not np.isnan(spread) else "n/a",
            len(paired),
        )
        current += timedelta(days=retrain_interval_days)

    _write_outputs(results)
    return results


def _write_outputs(results: list[dict]) -> None:
    with open(_RESULTS_PATH, "w") as fh:
        json.dump(results, fh, indent=2)
    log.info("Saved %d period results to %s", len(results), _RESULTS_PATH)

    ics = [r["ic"] for r in results if r["ic"] is not None]
    hits = [r["hit_rate"] for r in results]
    spreads = [r["spread"] for r in results if r["spread"] is not None]

    mean_ic = float(np.mean(ics)) if ics else None
    ic_std = float(np.std(ics)) if ics else None
    ic_t_stat = (
        float(mean_ic / ic_std * np.sqrt(len(ics)))
        if ics and ic_std and ic_std > 0
        else None
    )
    pct_positive = float(sum(1 for ic in ics if ic > 0) / len(ics)) if ics else None

    summary = {
        "mean_ic": round(mean_ic, 4) if mean_ic is not None else None,
        "ic_std": round(ic_std, 4) if ic_std is not None else None,
        "ic_t_stat": round(ic_t_stat, 3) if ic_t_stat is not None else None,
        "pct_positive": round(pct_positive, 3) if pct_positive is not None else None,
        "mean_hit_rate": round(float(np.mean(hits)), 3) if hits else None,
        "mean_spread": round(float(np.mean(spreads)), 6) if spreads else None,
        "n_periods": len(results),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with open(_SUMMARY_PATH, "w") as fh:
        json.dump(summary, fh, indent=2)

    print("\n" + "=" * 60)
    print("Walk-forward summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("=" * 60)
    log.info("Saved summary to %s", _SUMMARY_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward validation for the ML return predictor")
    parser.add_argument("--universe-size", type=int, default=100, help="Number of S&P 500 symbols (default 100)")
    parser.add_argument("--years", type=int, default=2, help="Evaluation span in years (default 2)")
    parser.add_argument("--interval", type=int, default=21, help="Days between retrain/evaluation periods (default 21)")
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * args.years)
    run_walk_forward(
        start,
        end,
        universe_size=args.universe_size,
        retrain_interval_days=args.interval,
    )


if __name__ == "__main__":
    main()
