"""
quantify.strategy.ml_return_predictor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Machine-Learning Return Predictor (Gu-Kelly-Xiu).

Academic basis
--------------
Gu, S., Kelly, B., & Xiu, D. (2020). "Empirical asset pricing via machine
learning." Review of Financial Studies, 33(5), 2223–2273.

This paper shows that tree-based methods (gradient-boosted trees) and neural
networks substantially outperform traditional linear factor models in
predicting stock returns.  Key findings:
  - Large feature sets capture non-linear interactions between predictors
  - Walk-forward (expanding window) training prevents look-ahead bias
  - Prediction signal is concentrated in top/bottom decile stocks

Implementation
--------------
Features (all from FeatureEngine):
  - Return-based: return_1d, return_5d, return_21d, return_63d, return_126d,
                  return_252d
  - Volatility:   volatility_20d, volatility_60d, volatility_126d, volatility_252d
  - Momentum:     rsi_14, macd_histogram
  - Bands:        bollinger_width
  - Moving avgs:  sma_crossover
  - Volume:       volume_ratio_20d, obv_slope
  - Liquidity:    amihud_illiquidity
  - ATR:          atr_14

Target:
  - 5-day forward return (computed inside generate_signals from available data)

Model:
  - LightGBM regressor (falls back to sklearn GradientBoostingRegressor)
  - Hyperparameters tuned for speed in production; use cross-validation offline
    to tune for a specific universe

Walk-forward:
  - Minimum 504 bars (2 trading years) before initial training
  - Re-train monthly (every ~21 trading days)
  - Expanding window: all history from inception is used

Prediction → Signal:
  - Predict 5-day return for each symbol
  - Rank by predicted return, go long top decile, short bottom decile
  - Strength: normalized predicted return in [-1, 1] using the max absolute
    predicted return in the cross-section as the scale factor

Feature importance is embedded in signal metadata for transparency.
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from quantify.data.universe import get_sp500
from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_TRAIN_BARS: int = 504          # minimum bars for initial model training
_RETRAIN_INTERVAL_DAYS: int = 21    # retrain every ~21 trading days
_FORWARD_RETURN_DAYS: int = 5       # prediction target horizon
_LONG_DECILE: float = 0.90          # top 10%
_SHORT_DECILE: float = 0.10         # bottom 10%
_REBALANCE_DAYS: int = 5            # weekly

# All available features from FeatureEngine
_ALL_FEATURES: list[str] = [
    "return_1d",
    "return_5d",
    "return_21d",
    "return_63d",
    "return_126d",
    "return_252d",
    "volatility_20d",
    "volatility_60d",
    "volatility_126d",
    "volatility_252d",
    "rsi_14",
    "macd_histogram",
    "bollinger_width",
    "sma_crossover",
    "volume_ratio_20d",
    "obv_slope",
    "amihud_illiquidity",
    "atr_14",
]

# LightGBM hyperparameters (production-suitable; tune offline)
_LGBM_PARAMS: dict[str, Any] = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.05,
    "n_estimators": 200,
    "max_depth": 5,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}


class MLReturnPredictorStrategy(Strategy):
    """
    Machine-learning return predictor using LightGBM.

    Trains on a growing window of feature/return pairs and predicts 5-day
    forward returns.  Signals are generated weekly for the top and bottom
    decile of predicted returns.

    Parameters
    ----------
    universe:
        List of ticker symbols.  Defaults to the top-100 S&P 500 tickers.
    features:
        List of FeatureEngine feature names to use.  Defaults to all 18
        registered features.
    min_train_bars:
        Minimum bars per symbol before the model is trained (default 504).
    retrain_interval_days:
        Trading days between model retrains (default 21).
    rebalance_days:
        Trading days between signal generation calls (default 5 = weekly).
    long_decile:
        Percentile cut-off for long signals (default 0.90).
    short_decile:
        Percentile cut-off for short signals (default 0.10).
    lgbm_params:
        Keyword arguments forwarded to LGBMRegressor (or fallback estimator).
    """

    name: str = "ml_return_predictor"
    rebalance_frequency: str = "weekly"
    lookback_days: int = 600  # 504 train + buffer

    def __init__(
        self,
        universe: Optional[list[str]] = None,
        features: Optional[list[str]] = None,
        min_train_bars: int = _MIN_TRAIN_BARS,
        retrain_interval_days: int = _RETRAIN_INTERVAL_DAYS,
        rebalance_days: int = _REBALANCE_DAYS,
        long_decile: float = _LONG_DECILE,
        short_decile: float = _SHORT_DECILE,
        lgbm_params: Optional[dict[str, Any]] = None,
    ) -> None:
        self.universe: list[str] = universe if universe is not None else get_sp500()
        self.features = features if features is not None else list(_ALL_FEATURES)
        self.min_train_bars = min_train_bars
        self.retrain_interval_days = retrain_interval_days
        self.rebalance_days = rebalance_days
        self.long_decile = long_decile
        self.short_decile = short_decile
        self.lgbm_params = lgbm_params if lgbm_params is not None else dict(_LGBM_PARAMS)

        # Model state
        self._model: Any = None
        self._feature_importances: Optional[dict[str, float]] = None
        self._model_backends: list[str] = []
        self._last_train_date: Optional[datetime] = None
        self._last_rebalance_date: Optional[datetime] = None
        self._signal_cache: list[Signal] = []

        # Accumulated training data (symbol-agnostic: stack all symbols)
        self._train_X: Optional[pd.DataFrame] = None
        self._train_y: Optional[pd.Series] = None

        log.info(
            "MLReturnPredictorStrategy initialised: %d symbols, %d features",
            len(self.universe),
            len(self.features),
        )

    def get_required_features(self) -> list[str]:
        """Return all feature names required from FeatureEngine."""
        return list(self.features)

    def on_start(self) -> None:
        """Reset model state at session start."""
        self._model = None
        self._feature_importances = None
        self._model_backends = []
        self._last_train_date = None
        self._last_rebalance_date = None
        self._signal_cache = []
        self._train_X = None
        self._train_y = None
        log.info("%s: model state reset on start", self.name)

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        Build training data, retrain if due, predict forward returns, and
        emit long/short signals for the predicted top/bottom decile.

        Parameters
        ----------
        data:
            ``{symbol: DataFrame}`` with OHLCV + feature columns.

        Returns
        -------
        list[Signal]
        """
        if not data:
            log.warning("%s: empty data dict", self.name)
            return []

        timestamp = self._latest_timestamp(data)

        # ---- Rebalance gate ----
        if not self._should_rebalance(timestamp):
            return list(self._signal_cache)

        # ---- Build cross-sectional training dataset ----
        X_all, y_all = self._build_training_data(data)

        if X_all is None or len(X_all) < self.min_train_bars:
            log.info(
                "%s: only %d training samples available (need %d); "
                "skipping signal generation",
                self.name,
                0 if X_all is None else len(X_all),
                self.min_train_bars,
            )
            self._last_rebalance_date = timestamp
            return []

        # ---- Retrain if due ----
        if self._should_retrain(timestamp):
            self._train_model(X_all, y_all)

        if self._model is None:
            log.warning("%s: model not trained, cannot generate signals", self.name)
            self._last_rebalance_date = timestamp
            return []

        # ---- Predict current-period returns ----
        predictions = self._predict(data)

        if not predictions:
            log.warning("%s: no valid predictions", self.name)
            self._last_rebalance_date = timestamp
            return []

        # ---- Rank and generate signals ----
        signals = self._rank_and_signal(predictions, timestamp)

        self._signal_cache = signals
        self._last_rebalance_date = timestamp

        log.info(
            "%s: %d signals at %s (%d long, %d short)",
            self.name,
            len(signals),
            timestamp.date(),
            sum(1 for s in signals if s.direction == "long"),
            sum(1 for s in signals if s.direction == "short"),
        )
        return signals

    # ------------------------------------------------------------------
    # Training data construction
    # ------------------------------------------------------------------

    def _build_training_data(
        self, data: dict[str, pd.DataFrame]
    ) -> tuple[Optional[pd.DataFrame], Optional[pd.Series]]:
        """
        Construct a stacked (symbol × time) feature matrix and forward-return
        target vector from the available data.

        For each symbol and each bar (up to the 2nd-to-last, since we need
        the next 5 bars for the target), assemble feature rows and match them
        to the 5-day forward return.
        """
        X_parts: list[pd.DataFrame] = []
        y_parts: list[pd.Series] = []

        for symbol, df in data.items():
            if df.empty or len(df) < _FORWARD_RETURN_DAYS + 30:
                continue

            # Check that all feature columns are present
            missing = [f for f in self.features if f not in df.columns]
            if missing:
                log.debug("%s: %s missing features: %s", self.name, symbol, missing)
                continue

            # Features matrix (all bars except last 5, since we need forward ret)
            n = len(df) - _FORWARD_RETURN_DAYS
            if n < 20:
                continue

            feat_df = df[self.features].iloc[:n].copy()

            # Forward return target: return over next 5 days
            fwd_ret = df["close"].pct_change(_FORWARD_RETURN_DAYS).shift(
                -_FORWARD_RETURN_DAYS
            ).iloc[:n]

            # Align and drop NaNs
            valid_mask = feat_df.notna().all(axis=1) & fwd_ret.notna()
            feat_df = feat_df[valid_mask]
            fwd_ret = fwd_ret[valid_mask]

            if feat_df.empty:
                continue

            X_parts.append(feat_df)
            y_parts.append(fwd_ret)

        if not X_parts:
            return None, None

        X_all = pd.concat(X_parts, axis=0).reset_index(drop=True)
        y_all = pd.concat(y_parts, axis=0).reset_index(drop=True)

        return X_all, y_all

    # ------------------------------------------------------------------
    # Model training
    # ------------------------------------------------------------------

    def _train_model(
        self, X: pd.DataFrame, y: pd.Series
    ) -> None:
        """
        Fit a LightGBM (or sklearn fallback) regressor on the full training
        dataset.
        """
        log.info(
            "%s: training model on %d samples × %d features",
            self.name, len(X), len(self.features),
        )

        model, backends = _build_model(self.lgbm_params)
        if model is None:
            log.error("%s: no ML backend available (LightGBM or sklearn)", self.name)
            return

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                model.fit(X[self.features].values, y.values)
            except Exception as exc:
                log.exception("%s: model training failed: %s", self.name, exc)
                return

        self._model = model
        self._model_backends = backends

        # Extract feature importances
        try:
            # VotingRegressor doesn't have feature_importances_, try getting it from LightGBM
            if hasattr(model, "estimators_"):
                lgbm_model = next((est for name, est in model.estimators if name == "lgbm"), None)
                if lgbm_model and hasattr(lgbm_model, "feature_importances_"):
                    importances = lgbm_model.feature_importances_
                else:
                    importances = None
            else:
                importances = getattr(model, "feature_importances_", None)

            if importances is not None:
                self._feature_importances = {
                    feat: float(imp)
                    for feat, imp in zip(self.features, importances)
                }
                top5 = sorted(
                    self._feature_importances.items(),
                    key=lambda kv: kv[1],
                    reverse=True,
                )[:5]
                log.info(
                    "%s: top-5 feature importances: %s",
                    self.name,
                    ", ".join(f"{k}={v:.3f}" for k, v in top5),
                )
            else:
                self._feature_importances = None
        except AttributeError:
            self._feature_importances = None

        # Record training date
        # Use the current time so we know when the last retrain happened
        self._last_train_date = datetime.now(timezone.utc)
        log.info("%s: model training complete", self.name)
        log.info("%s: model backends in use: %s", self.name, ", ".join(self._model_backends))

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def _predict(
        self, data: dict[str, pd.DataFrame]
    ) -> dict[str, float]:
        """
        Predict the 5-day forward return for each symbol using the current bar's
        feature vector.

        Returns a dict of {symbol: predicted_return}.
        """
        predictions: dict[str, float] = {}

        for symbol, df in data.items():
            if df.empty or len(df) < 30:
                continue

            missing = [f for f in self.features if f not in df.columns]
            if missing:
                continue

            # Use the most recent complete bar
            feat_row = df[self.features].iloc[-1]
            if feat_row.isna().any():
                log.debug("%s: %s has NaN features at latest bar", self.name, symbol)
                continue

            try:
                pred = self._model.predict(feat_row.values.reshape(1, -1))[0]
                predictions[symbol] = float(pred)
            except Exception as exc:
                log.debug(
                    "%s: prediction failed for %s: %s", self.name, symbol, exc
                )

        return predictions

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------

    def _rank_and_signal(
        self,
        predictions: dict[str, float],
        timestamp: datetime,
    ) -> list[Signal]:
        """
        Rank predicted returns and emit signals for top/bottom decile.
        """
        pred_series = pd.Series(predictions)
        pct_ranks = pred_series.rank(pct=True)

        # Normalise predictions to [-1, 1] for strength
        max_abs = pred_series.abs().max()
        if max_abs < 1e-10:
            max_abs = 1.0

        signals: list[Signal] = []

        fi_meta: Optional[dict[str, float]] = None
        if self._feature_importances:
            # Include only top-10 importances in metadata to keep it compact
            fi_meta = dict(
                sorted(
                    self._feature_importances.items(),
                    key=lambda kv: kv[1],
                    reverse=True,
                )[:10]
            )

        for symbol, pct_rank in pct_ranks.items():
            pred_ret = pred_series[symbol]
            norm_strength = float(np.clip(pred_ret / max_abs, -1.0, 1.0))

            if pct_rank >= self.long_decile:
                direction = "long"
                strength = float(np.clip(norm_strength, 0.0, 1.0))
            elif pct_rank <= self.short_decile:
                direction = "short"
                strength = float(np.clip(norm_strength, -1.0, 0.0))
            else:
                direction = "close"
                strength = 0.0

            meta: dict[str, Any] = {
                "predicted_return_5d": round(pred_ret, 6),
                "percentile_rank": round(float(pct_rank), 4),
                "last_train_date": (
                    self._last_train_date.isoformat(timespec="seconds")
                    if self._last_train_date
                    else None
                ),
                "n_predictions": len(predictions),
                "model_backends": list(self._model_backends),
            }
            if fi_meta is not None:
                meta["feature_importance_top10"] = fi_meta

            signals.append(
                Signal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction=direction,  # type: ignore[arg-type]
                    strength=strength,
                    timestamp=timestamp,
                    metadata=meta,
                )
            )

        return signals

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_rebalance(self, timestamp: datetime) -> bool:
        if self._last_rebalance_date is None:
            return True
        delta = timestamp - self._last_rebalance_date
        return delta.days >= self.rebalance_days

    def _should_retrain(self, timestamp: datetime) -> bool:
        if self._model is None or self._last_train_date is None:
            return True
        delta = timestamp - self._last_train_date
        return delta.days >= self.retrain_interval_days

    @staticmethod
    def _latest_timestamp(data: dict[str, pd.DataFrame]) -> datetime:
        latest = datetime.min.replace(tzinfo=timezone.utc)
        for df in data.values():
            if df.empty:
                continue
            ts = df.index[-1]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts > latest:
                latest = ts
        if latest == datetime.min.replace(tzinfo=timezone.utc):
            return datetime.now(timezone.utc)
        return latest

    @property
    def is_trained(self) -> bool:
        """True if the model has been trained at least once."""
        return self._model is not None


# ---------------------------------------------------------------------------
# Backend selection: LightGBM with sklearn fallback
# ---------------------------------------------------------------------------


def _build_model(params: dict[str, Any]) -> tuple[Any, list[str]]:
    """
    Return a VotingRegressor ensemble of LightGBM, XGBoost, and CatBoost,
    plus a list of backend names actually used.
    """
    from sklearn.ensemble import VotingRegressor
    
    estimators: list[tuple[str, Any]] = []
    backends: list[str] = []
    
    # 1. LightGBM
    try:
        from lightgbm import LGBMRegressor
        estimators.append(("lgbm", LGBMRegressor(**params)))
        backends.append("lgbm")
    except ImportError:
        log.error("LightGBM not found for ensemble.")

    # 2. XGBoost
    try:
        from xgboost import XGBRegressor
        xgb_params = {
            "n_estimators": params.get("n_estimators", 200),
            "learning_rate": params.get("learning_rate", 0.05),
            "max_depth": params.get("max_depth", 5),
            "n_jobs": -1,
            "random_state": 42
        }
        estimators.append(("xgboost", XGBRegressor(**xgb_params)))
        backends.append("xgboost")
    except ImportError:
        log.error("XGBoost not found for ensemble.")

    # 3. CatBoost
    try:
        from catboost import CatBoostRegressor
        cb_params = {
            "iterations": params.get("n_estimators", 200),
            "learning_rate": params.get("learning_rate", 0.05),
            "depth": params.get("max_depth", 5),
            "verbose": False,
            "random_seed": 42
        }
        estimators.append(("catboost", CatBoostRegressor(**cb_params)))
        backends.append("catboost")
    except ImportError:
        log.error("CatBoost not found for ensemble.")

    if not estimators:
        log.error("No ML backends available! Falling back to sklearn.")
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor(n_estimators=100), ["sklearn_fallback"]

    # Return the weighted ensemble
    # We give LightGBM slightly more weight as it's the gold standard for finance
    weights = []
    for name, _ in estimators:
        if name == "lgbm": weights.append(1.5)
        else: weights.append(1.0)
        
    return VotingRegressor(estimators=estimators, weights=weights), backends


__all__ = ["MLReturnPredictorStrategy"]
