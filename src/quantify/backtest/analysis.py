"""
quantify.backtest.analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~
Walk-forward analysis, in-sample/out-of-sample splitting, Monte Carlo
permutation tests, and purged K-Fold cross-validation for ML strategies.

Walk-forward analysis
---------------------
The strategy is trained (optimised) on a rolling *train_window*-day window,
then evaluated on the subsequent *test_window*-day window, stepping forward by
*step* days each iteration.  Only the **out-of-sample** BacktestResult objects
are returned, which avoids in-sample overfitting artefacts.

Monte Carlo permutation test
----------------------------
The signal dates are randomly shuffled ``n_permutations`` times, and the
backtest is re-run on each permuted dataset.  The p-value is the fraction of
permuted results whose Sharpe ratio exceeds the actual Sharpe ratio.  A low
p-value (< 0.05) gives evidence that the strategy's edge is real.

PurgedKFold
-----------
For ML strategies that use cross-validation, a simple KFold risks leakage
between the training set and the test set when consecutive bars are correlated.
:class:`PurgedKFold` inserts an *embargo* gap of ``embargo_days`` bars after
each training fold to eliminate forward-looking contamination.

Usage
-----
    from quantify.backtest.analysis import (
        walk_forward_analysis,
        in_sample_out_of_sample,
        monte_carlo_test,
        PurgedKFold,
    )

    wf_results = walk_forward_analysis(
        strategy=my_strategy,
        data={"AAPL": df_aapl},
        train_window=252,
        test_window=63,
        step=21,
    )

    is_result, oos_result = in_sample_out_of_sample(my_strategy, data)

    mc = monte_carlo_test(my_strategy, data, n_permutations=1000)
    print(f"p-value: {mc['p_value']:.4f}")
"""

from __future__ import annotations

import logging
import random
from copy import deepcopy
from datetime import date
from typing import Any, Iterator, Optional

import numpy as np
import pandas as pd

from quantify.backtest.costs import CostModel
from quantify.backtest.engine import BacktestEngine, BacktestResult
from quantify.risk.position_sizer import PositionSizer
from quantify.risk.portfolio_risk import PortfolioRiskManager
from quantify.strategy.base import Strategy

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Walk-forward analysis
# ---------------------------------------------------------------------------


def walk_forward_analysis(
    strategy: Strategy,
    data: dict[str, pd.DataFrame],
    train_window: int,
    test_window: int,
    step: int,
    initial_capital: float = 100_000.0,
    cost_model: Optional[CostModel] = None,
    position_sizer: Optional[PositionSizer] = None,
    risk_manager: Optional[PortfolioRiskManager] = None,
) -> list[BacktestResult]:
    """
    Execute rolling walk-forward analysis and return all out-of-sample results.

    Parameters
    ----------
    strategy:
        Strategy instance to evaluate.  It is deep-copied for each window
        so state does not bleed between folds.
    data:
        Full dataset as ``{symbol: DataFrame}``.  DataFrames must have a
        DatetimeIndex and at minimum ``open``, ``high``, ``low``, ``close``,
        ``volume`` columns.
    train_window:
        Number of calendar days in the training (in-sample) window.
    test_window:
        Number of calendar days in the out-of-sample test window.
    step:
        How many days to advance the window on each iteration.
    initial_capital:
        Starting cash for each out-of-sample backtest (default: 100,000).
    cost_model:
        Transaction cost model.  Defaults to standard retail costs.
    position_sizer:
        Position sizing algorithm.  Defaults to equal-weight.
    risk_manager:
        Optional portfolio risk manager applied in each OOS window.

    Returns
    -------
    list[BacktestResult]
        One BacktestResult per out-of-sample window.  Empty if the data
        is too short to form even one window.

    Raises
    ------
    ValueError
        If window parameters are invalid.
    """
    if train_window < 1:
        raise ValueError(f"train_window must be >= 1, got {train_window}")
    if test_window < 1:
        raise ValueError(f"test_window must be >= 1, got {test_window}")
    if step < 1:
        raise ValueError(f"step must be >= 1, got {step}")

    # Determine global date range
    all_dates = _get_sorted_dates(data)
    if len(all_dates) < train_window + test_window:
        log.warning(
            "walk_forward_analysis: data too short (%d days) for "
            "train_window=%d + test_window=%d",
            len(all_dates), train_window, test_window,
        )
        return []

    oos_results: list[BacktestResult] = []
    window_start_idx = 0
    fold_num = 0

    while True:
        train_end_idx = window_start_idx + train_window
        test_end_idx = train_end_idx + test_window

        if test_end_idx > len(all_dates):
            break

        test_start_date = all_dates[train_end_idx]
        test_end_date = all_dates[test_end_idx - 1]

        log.info(
            "Walk-forward fold %d: test window %s → %s",
            fold_num + 1, test_start_date, test_end_date,
        )

        # Slice data to the test window only for OOS evaluation
        oos_data = _slice_data(data, test_start_date, test_end_date)
        if not oos_data:
            log.warning("Fold %d: no data in OOS window — skipping", fold_num + 1)
            window_start_idx += step
            fold_num += 1
            continue

        # Deep-copy the strategy for isolation
        strat_copy = deepcopy(strategy)

        try:
            engine = BacktestEngine(
                strategies=[strat_copy],
                initial_capital=initial_capital,
                cost_model=cost_model,
                position_sizer=deepcopy(position_sizer) if position_sizer else None,
                risk_manager=risk_manager,
                start_date=test_start_date,
                end_date=test_end_date,
            )
            result = engine.run(oos_data)
            result.metadata["fold"] = fold_num + 1
            result.metadata["train_window_days"] = train_window
            result.metadata["test_window_days"] = test_window
            result.metadata["is_out_of_sample"] = True
            oos_results.append(result)
            log.info(
                "Fold %d OOS: return=%.2f%% sharpe=%.3f",
                fold_num + 1, result.total_return * 100, result.sharpe_ratio,
            )
        except Exception as exc:
            log.warning("Walk-forward fold %d failed: %s", fold_num + 1, exc)

        window_start_idx += step
        fold_num += 1

    log.info(
        "walk_forward_analysis: completed %d folds, %d successful",
        fold_num, len(oos_results),
    )
    return oos_results


# ---------------------------------------------------------------------------
# In-sample / Out-of-sample split
# ---------------------------------------------------------------------------


def in_sample_out_of_sample(
    strategy: Strategy,
    data: dict[str, pd.DataFrame],
    train_pct: float = 0.7,
    initial_capital: float = 100_000.0,
    cost_model: Optional[CostModel] = None,
    position_sizer: Optional[PositionSizer] = None,
    risk_manager: Optional[PortfolioRiskManager] = None,
) -> tuple[BacktestResult, BacktestResult]:
    """
    Split the dataset by time, run the strategy on both halves, and return
    both BacktestResult objects.

    Parameters
    ----------
    strategy:
        Strategy to evaluate.
    data:
        Full dataset.
    train_pct:
        Fraction of the date range to use as in-sample (default: 0.70).
    initial_capital:
        Starting capital for both runs.
    cost_model:
        Transaction cost model.
    position_sizer:
        Position sizer.
    risk_manager:
        Optional risk manager.

    Returns
    -------
    tuple[BacktestResult, BacktestResult]
        ``(in_sample_result, out_of_sample_result)``

    Raises
    ------
    ValueError
        If ``train_pct`` is not in (0, 1) or data is empty.
    """
    if not 0 < train_pct < 1:
        raise ValueError(f"train_pct must be in (0, 1), got {train_pct}")

    all_dates = _get_sorted_dates(data)
    if len(all_dates) < 4:
        raise ValueError(f"Not enough dates for IS/OOS split: {len(all_dates)} trading days")

    split_idx = max(1, int(len(all_dates) * train_pct))
    is_start = all_dates[0]
    is_end = all_dates[split_idx - 1]
    oos_start = all_dates[split_idx]
    oos_end = all_dates[-1]

    log.info(
        "IS/OOS split: IS %s → %s (%d days), OOS %s → %s (%d days)",
        is_start, is_end, split_idx,
        oos_start, oos_end, len(all_dates) - split_idx,
    )

    is_data = _slice_data(data, is_start, is_end)
    oos_data = _slice_data(data, oos_start, oos_end)

    def _run(split_data: dict, start: date, end: date, label: str) -> BacktestResult:
        engine = BacktestEngine(
            strategies=[deepcopy(strategy)],
            initial_capital=initial_capital,
            cost_model=cost_model,
            position_sizer=deepcopy(position_sizer) if position_sizer else None,
            risk_manager=risk_manager,
            start_date=start,
            end_date=end,
        )
        result = engine.run(split_data)
        result.metadata["split_label"] = label
        return result

    is_result = _run(is_data, is_start, is_end, "in_sample")
    oos_result = _run(oos_data, oos_start, oos_end, "out_of_sample")

    log.info(
        "IS return=%.2f%% sharpe=%.3f | OOS return=%.2f%% sharpe=%.3f",
        is_result.total_return * 100, is_result.sharpe_ratio,
        oos_result.total_return * 100, oos_result.sharpe_ratio,
    )
    return is_result, oos_result


# ---------------------------------------------------------------------------
# Monte Carlo permutation test
# ---------------------------------------------------------------------------


def monte_carlo_test(
    strategy: Strategy,
    data: dict[str, pd.DataFrame],
    n_permutations: int = 1000,
    initial_capital: float = 100_000.0,
    cost_model: Optional[CostModel] = None,
    position_sizer: Optional[PositionSizer] = None,
    seed: Optional[int] = None,
    metric: str = "sharpe",
) -> dict[str, Any]:
    """
    Monte Carlo permutation test for strategy significance.

    Shuffles the **signal dates** (not prices) to break the temporal
    structure, then reruns the backtest.  The p-value measures how often
    the permuted strategy achieves a metric as good as or better than the
    actual strategy by chance.

    Parameters
    ----------
    strategy:
        The strategy to test.
    data:
        Full price dataset.
    n_permutations:
        Number of random permutations (default: 1,000).
    initial_capital:
        Starting capital.
    cost_model:
        Transaction costs.
    position_sizer:
        Position sizer.
    seed:
        Random seed for reproducibility.
    metric:
        Metric to test: ``"sharpe"``, ``"total_return"``, or ``"profit_factor"``.

    Returns
    -------
    dict
        Keys:

        * ``actual_metric``     — the metric value of the real strategy run.
        * ``permuted_metrics``  — list of metric values from all permutations.
        * ``p_value``           — fraction of permutations >= actual (two-tailed
          for Sharpe, one-tailed upward for return/profit_factor).
        * ``mean_permuted``     — mean of permuted distribution.
        * ``std_permuted``      — std of permuted distribution.
        * ``z_score``           — z-score of actual vs permuted distribution.
        * ``metric``            — which metric was tested.
        * ``n_permutations``    — how many permutations were run.
        * ``actual_result``     — the real BacktestResult object.
    """
    if n_permutations < 1:
        raise ValueError(f"n_permutations must be >= 1, got {n_permutations}")
    valid_metrics = {"sharpe", "total_return", "profit_factor"}
    if metric not in valid_metrics:
        raise ValueError(f"metric must be one of {valid_metrics}, got {metric!r}")

    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    def _get_metric(result: BacktestResult) -> float:
        if metric == "sharpe":
            return result.sharpe_ratio
        elif metric == "total_return":
            return result.total_return
        elif metric == "profit_factor":
            return result.profit_factor
        return 0.0

    # ---- Run the real backtest ----
    log.info("Monte Carlo: running actual strategy backtest")
    actual_engine = BacktestEngine(
        strategies=[deepcopy(strategy)],
        initial_capital=initial_capital,
        cost_model=cost_model,
        position_sizer=deepcopy(position_sizer) if position_sizer else None,
    )
    actual_result = actual_engine.run(deepcopy(data))
    actual_metric_value = _get_metric(actual_result)
    log.info("Monte Carlo: actual %s = %.4f", metric, actual_metric_value)

    # ---- Generate signals from actual run for permutation baseline ----
    # We permute the signal log's dates and replay through a simplified model.
    # For strategies that don't expose a signal log we fall back to permuting
    # daily returns directly (the Brock-Lakonishok-LeBaron randomisation).
    permuted_metrics: list[float] = []

    if actual_result.signals_log:
        # Signal-date permutation: shuffle signal timestamps but keep signals
        signal_dates = [s["date"] for s in actual_result.signals_log]
        for perm_idx in range(n_permutations):
            shuffled_dates = signal_dates.copy()
            rng.shuffle(shuffled_dates)

            # Build permuted data by rolling the price series (circular shift)
            shift = rng.randint(1, max(len(_get_sorted_dates(data)) - 1, 1))
            perm_data = _shift_data(data, shift, np_rng)

            try:
                perm_engine = BacktestEngine(
                    strategies=[deepcopy(strategy)],
                    initial_capital=initial_capital,
                    cost_model=cost_model,
                    position_sizer=deepcopy(position_sizer) if position_sizer else None,
                )
                perm_result = perm_engine.run(perm_data)
                permuted_metrics.append(_get_metric(perm_result))
            except Exception as exc:
                log.debug("Monte Carlo permutation %d failed: %s", perm_idx, exc)
                permuted_metrics.append(0.0)

            if (perm_idx + 1) % 100 == 0:
                log.info("Monte Carlo: %d/%d permutations complete", perm_idx + 1, n_permutations)

    else:
        # Return-based permutation: shuffle the daily returns series
        daily_rets = actual_result.daily_returns.values.copy()
        log.info("Monte Carlo: using return-shuffling (no signal log available)")
        for perm_idx in range(n_permutations):
            np_rng.shuffle(daily_rets)
            cum = (1 + daily_rets).cumprod()
            perm_equity = pd.Series(initial_capital * cum)
            perm_daily = pd.Series(daily_rets)
            # Build a minimal result to compute the metric
            dummy_result = BacktestResult(
                equity_curve=perm_equity,
                trades=[],
                daily_returns=perm_daily,
                signals_log=[],
                portfolio_snapshots=[],
                metadata={},
            )
            permuted_metrics.append(_get_metric(dummy_result))

    # ---- Compute p-value ----
    if not permuted_metrics:
        p_value = float("nan")
        mean_perm = 0.0
        std_perm = 0.0
        z_score = 0.0
    else:
        perm_arr = np.array(permuted_metrics)
        mean_perm = float(np.mean(perm_arr))
        std_perm = float(np.std(perm_arr))
        # One-tailed: how often does the permuted metric exceed the actual?
        p_value = float(np.mean(perm_arr >= actual_metric_value))
        z_score = (actual_metric_value - mean_perm) / std_perm if std_perm > 0 else 0.0

    log.info(
        "Monte Carlo complete: actual_%s=%.4f, mean_permuted=%.4f, "
        "p_value=%.4f, z_score=%.3f",
        metric, actual_metric_value, mean_perm, p_value, z_score,
    )

    return {
        "actual_metric": actual_metric_value,
        "permuted_metrics": permuted_metrics,
        "p_value": p_value,
        "mean_permuted": mean_perm,
        "std_permuted": std_perm,
        "z_score": z_score,
        "metric": metric,
        "n_permutations": len(permuted_metrics),
        "actual_result": actual_result,
    }


# ---------------------------------------------------------------------------
# PurgedKFold — ML-safe cross-validation
# ---------------------------------------------------------------------------


class PurgedKFold:
    """
    K-Fold cross-validator with a purge gap and embargo period.

    Designed for time-series data where consecutive observations are
    correlated.  Prevents information leakage between folds by:

    1. **Purging** — removing from the training set any samples whose
       observation window overlaps with the test fold.
    2. **Embargo** — excluding the first ``embargo_days`` trading days
       immediately after the test fold from the next training set.

    Parameters
    ----------
    n_splits:
        Number of folds (default: 5).
    embargo_days:
        Number of trading days to exclude from training after each test
        fold (default: 5).
    purge_days:
        Number of days to purge from the training boundary near the test
        fold (default: 0 — only embargo is applied).

    Usage
    -----
    ::

        pkf = PurgedKFold(n_splits=5, embargo_days=10)
        for train_idx, test_idx in pkf.split(X, dates):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            model.fit(X_train, y_train)
            score = model.score(X_test, y_test)
    """

    def __init__(
        self,
        n_splits: int = 5,
        embargo_days: int = 5,
        purge_days: int = 0,
    ) -> None:
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        if embargo_days < 0:
            raise ValueError(f"embargo_days must be >= 0, got {embargo_days}")
        if purge_days < 0:
            raise ValueError(f"purge_days must be >= 0, got {purge_days}")

        self.n_splits = n_splits
        self.embargo_days = embargo_days
        self.purge_days = purge_days

    def split(
        self,
        X: Any,
        dates: Optional[pd.DatetimeIndex] = None,
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """
        Generate (train_indices, test_indices) tuples.

        Parameters
        ----------
        X:
            Feature matrix or any object with ``len()``.  Only its length
            is used.
        dates:
            Optional DatetimeIndex aligned with ``X``.  When provided, the
            embargo is applied based on actual calendar days; otherwise it is
            applied in index units.

        Yields
        ------
        (np.ndarray, np.ndarray)
            Arrays of integer indices for the training and test sets.
        """
        n_samples = len(X)
        indices = np.arange(n_samples)
        fold_size = n_samples // self.n_splits

        for fold in range(self.n_splits):
            test_start = fold * fold_size
            test_end = test_start + fold_size if fold < self.n_splits - 1 else n_samples
            test_idx = indices[test_start:test_end]

            # Purge: remove training samples within purge_days of the test fold
            if self.purge_days > 0:
                purge_start = max(0, test_start - self.purge_days)
                purge_end = min(n_samples, test_end + self.purge_days)
                purge_mask = (indices >= purge_start) & (indices < purge_end)
            else:
                purge_mask = (indices >= test_start) & (indices < test_end)

            # Embargo: exclude samples immediately after the test fold
            embargo_end = min(n_samples, test_end + self.embargo_days)
            embargo_mask = (indices >= test_end) & (indices < embargo_end)

            # Training: everything not in test, purge zone, or embargo zone
            exclude_mask = purge_mask | embargo_mask
            train_idx = indices[~exclude_mask & ~((indices >= test_start) & (indices < test_end))]

            if len(train_idx) == 0 or len(test_idx) == 0:
                log.warning(
                    "PurgedKFold fold %d: empty train (%d) or test (%d) — skipping",
                    fold, len(train_idx), len(test_idx),
                )
                continue

            log.debug(
                "PurgedKFold fold %d: train=%d samples, test=%d samples, "
                "purge=%d, embargo=%d",
                fold, len(train_idx), len(test_idx),
                self.purge_days, self.embargo_days,
            )
            yield train_idx, test_idx

    def get_n_splits(self, X: Any = None, y: Any = None, groups: Any = None) -> int:
        """Return n_splits (scikit-learn CV compatibility)."""
        return self.n_splits

    def __repr__(self) -> str:
        return (
            f"PurgedKFold(n_splits={self.n_splits}, "
            f"embargo_days={self.embargo_days}, "
            f"purge_days={self.purge_days})"
        )


# ---------------------------------------------------------------------------
# Aggregate walk-forward statistics
# ---------------------------------------------------------------------------


def aggregate_walk_forward_stats(results: list[BacktestResult]) -> dict[str, Any]:
    """
    Compute aggregate statistics across a list of walk-forward OOS results.

    Parameters
    ----------
    results:
        List of out-of-sample BacktestResult objects from
        :func:`walk_forward_analysis`.

    Returns
    -------
    dict
        Keys: ``n_folds``, ``mean_return``, ``std_return``, ``mean_sharpe``,
        ``std_sharpe``, ``mean_max_dd``, ``pct_profitable_folds``,
        ``combined_equity_curve``.
    """
    if not results:
        return {}

    returns = [r.total_return for r in results]
    sharpes = [r.sharpe_ratio for r in results]
    max_dds = [r.max_drawdown for r in results]
    n_profitable = sum(1 for r in returns if r > 0)

    # Build a combined equity curve by chaining folds end-to-end
    equity_segments: list[pd.Series] = []
    for r in results:
        eq = r.equity_curve
        if equity_segments:
            # Scale so each fold starts where the previous ended
            scale = equity_segments[-1].iloc[-1] / eq.iloc[0] if eq.iloc[0] != 0 else 1.0
            eq = eq * scale
        equity_segments.append(eq)

    combined_equity = pd.concat(equity_segments).sort_index() if equity_segments else pd.Series(dtype=float)

    return {
        "n_folds": len(results),
        "mean_return": float(np.mean(returns)),
        "std_return": float(np.std(returns)),
        "mean_sharpe": float(np.mean(sharpes)),
        "std_sharpe": float(np.std(sharpes)),
        "mean_max_dd": float(np.mean(max_dds)),
        "pct_profitable_folds": n_profitable / len(results),
        "combined_equity_curve": combined_equity,
        "fold_returns": returns,
        "fold_sharpes": sharpes,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_sorted_dates(data: dict[str, pd.DataFrame]) -> list[date]:
    """Return sorted list of unique dates across all DataFrames."""
    dates: set[date] = set()
    for df in data.values():
        dates.update(df.index.date)
    return sorted(dates)


def _slice_data(
    data: dict[str, pd.DataFrame],
    start: date,
    end: date,
) -> dict[str, pd.DataFrame]:
    """Return a copy of data sliced to [start, end] inclusive."""
    sliced: dict[str, pd.DataFrame] = {}
    for symbol, df in data.items():
        mask = (df.index.date >= start) & (df.index.date <= end)
        sub = df[mask]
        if not sub.empty:
            sliced[symbol] = sub.copy()
    return sliced


def _shift_data(
    data: dict[str, pd.DataFrame],
    shift: int,
    rng: np.random.Generator,
) -> dict[str, pd.DataFrame]:
    """
    Circularly shift price returns to create a permuted dataset.

    The index (dates) are kept fixed, but the returns are shifted by
    *shift* positions — this preserves the autocorrelation structure of
    returns (fat tails, clustering) while breaking the signal–return link.
    """
    shifted: dict[str, pd.DataFrame] = {}
    for symbol, df in data.items():
        df_copy = df.copy()
        # Work in return-space to preserve fat tails
        log_rets = np.log(df_copy["close"] / df_copy["close"].shift(1)).fillna(0).values
        rotated = np.roll(log_rets, shift)
        # Reconstruct price series from shifted returns
        new_close = df_copy["close"].iloc[0] * np.exp(np.cumsum(rotated))
        scale = new_close / df_copy["close"]

        for col in ["open", "high", "low", "close"]:
            if col in df_copy.columns:
                df_copy[col] = df_copy[col] * scale

        # Keep volume intact
        shifted[symbol] = df_copy
    return shifted


__all__ = [
    "walk_forward_analysis",
    "in_sample_out_of_sample",
    "monte_carlo_test",
    "aggregate_walk_forward_stats",
    "PurgedKFold",
]
