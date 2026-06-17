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
  - Volume:       volume_ratio_20d, obv_slope, volume_trend
  - Liquidity:    amihud_illiquidity
  - ATR:          atr_14
  - Higher-moment: return_std_21d, skewness_21d, max_return_21d, min_return_21d
  - Anchoring:    price_to_high_52w, price_to_low_52w
  - Quality:      return_consistency, gap_return, intraday_range
  - Interaction:  rsi_divergence, mean_reversion_5d

Target:
    - 5-day forward return, cross-sectionally rank-transformed to [-1, 1]
      to remove market beta noise and focus on relative stock performance.

Model:
  - Stacking ensemble of LightGBM, XGBoost, and CatBoost with a Ridge
    meta-learner (falls back to sklearn GradientBoostingRegressor).
  - Purged walk-forward validation with embargo gap to prevent data leakage.

Walk-forward:
    - Minimum 504 bars (2 trading years) before initial training
    - Re-train monthly (every ~21 trading days)
    - Rolling training window (default ~3 years) with time-decay weighting

Prediction → Signal:
    - Predict cross-sectional rank score for each symbol
    - Center predictions cross-sectionally before ranking
    - Rank by centered predicted rank, go long top decile, short bottom decile
    - Strength: normalized centered prediction in [-1, 1] scaled by ensemble agreement

Feature importance is embedded in signal metadata for transparency.
"""

from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from quantify.data.fundamentals import FUNDAMENTAL_FEATURES
from quantify.data.universe import get_sp500
from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MIN_TRAIN_BARS: int = 126          # minimum bars for initial model training
_RETRAIN_INTERVAL_DAYS: int = 21    # retrain every ~21 trading days
_FORWARD_RETURN_DAYS: int = 21      # prediction target horizon (1 month)
_LONG_DECILE: float = 0.90          # top 10%
_SHORT_DECILE: float = 0.10         # bottom 10%
_REBALANCE_DAYS: int = 5            # weekly
_TARGET_WINSOR_Q: float = 0.01      # winsorize target tails (1% / 99%)
_FEATURE_WINSOR_Q: float = 0.01     # winsorize feature tails per date
_TRAIN_WINDOW_DAYS: int = 756       # ~1 year of history for model training
_DECAY_HALFLIFE_DAYS: int = 126     # time-decay half-life for sample weights
_PURGE_EMBARGO_DAYS: int = 21       # embargo gap = forward return horizon


# Technical features sourced from FeatureEngine (per-symbol, no cross-sectional data needed)
_ALL_FEATURES: list[str] = [
    # Return-based
    "return_1d",
    "return_5d",
    "return_21d",
    "return_63d",
    "return_126d",
    "return_252d",
    # Volatility
    "volatility_20d",
    "volatility_60d",
    "volatility_126d",
    "volatility_252d",
    # Momentum
    "rsi_14",
    "macd_histogram",
    # Bands
    "bollinger_width",
    # Moving averages
    "sma_crossover",
    # Volume (core)
    "volume_ratio_20d",
    "obv_slope",
    "volume_trend",
    # Volume profile / confirmation
    "volume_price_corr_20d",
    "mfi_14",
    "vwap_ratio",
    "volume_price_divergence",
    # Liquidity
    "amihud_illiquidity",
    # ATR
    "atr_14",
    # Higher-moment features (Gu et al. 2020)
    "return_std_21d",
    "skewness_21d",
    "max_return_21d",
    "min_return_21d",
    # Anchoring features (George & Hwang 2004)
    "price_to_high_52w",
    "price_to_low_52w",
    # Return quality / consistency
    "return_consistency",
    "gap_return",
    "intraday_range",
    # Interaction / composite
    "rsi_divergence",
    "mean_reversion_5d",
]

# Cross-sectional features added by prepare_enriched_data (not FeatureEngine).
# Follows the same pattern as FUNDAMENTAL_FEATURES — included in self.features
# but NOT returned by get_required_features(), so FeatureEngine is never asked
# to compute them.
_SECTOR_FEATURES: tuple[str, ...] = (
    "sector_rs_5d",
    "sector_rs_21d",
)

# LightGBM hyperparameters — LGBM-specific; do NOT pass directly to XGBoost/CatBoost.
# max_depth=3 with num_leaves=7 is correct for LGBM's leaf-wise growth but would
# make XGB/CatBoost (level-wise) critically shallow. See _XGB_PARAMS/_CB_PARAMS below.
_LGBM_PARAMS: dict[str, Any] = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.02,
    "n_estimators": 400,
    "max_depth": 3,
    "num_leaves": 7,
    "min_child_samples": 100,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 1.0,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}

# Per-library overrides for params that are NOT safely shared from _LGBM_PARAMS.
# Shared structural params (learning_rate, n_estimators, subsample, colsample_bytree,
# reg_alpha, reg_lambda) are still forwarded from lgbm_params at build time.
_XGB_PARAMS: dict[str, Any] = {
    "max_depth": 6,        # level-wise growth — depth 6 ≈ 64 leaves (diversity vs LGBM)
    "min_child_weight": 50,  # Hessian-sum threshold; ~half of LGBM's min_child_samples
}

_CB_PARAMS: dict[str, Any] = {
    "depth": 6,             # symmetric trees — depth 6 gives meaningful complexity
    "min_data_in_leaf": 50,
    "random_strength": 1.0,  # per-split noise for implicit regularization
}

# Cross-sectional regime features — computed internally from the universe cross-section
# on each date.  NOT sourced from FeatureEngine (excluded from get_required_features).
# NOT z-scored per date: they represent absolute market state across time, not relative
# stock ranking within a day.  These let the ensemble learn regime-conditional behaviour
# (e.g. discounting momentum in high-volatility environments).
_CS_FEATURES: tuple[str, ...] = (
    "cs_mkt_return_252d",    # cross-sectional mean 252d return — market trend proxy
    "cs_mkt_vol_60d",        # cross-sectional mean 60d volatility — market stress proxy
    "cs_return_dispersion",  # cross-sectional std of 5d returns — signal quality proxy
)

# Regime gate: suppress all signals when the cross-sectional mean 252d return is below
# this threshold.  Momentum-style signals fail systematically during sustained downtrends;
# sitting out those periods directly removes the worst negative-IC periods.
_REGIME_GATE_RETURN_THRESHOLD: float = -0.10


class MLReturnPredictorStrategy(Strategy):
    """
    Machine-learning return predictor using a stacking ensemble.

    Trains on a growing window of feature/return pairs and predicts
    cross-sectional rank scores for forward returns.  Signals are generated
    weekly for the top and bottom decile of predicted rankings.

    Parameters
    ----------
    universe:
        List of ticker symbols.  Defaults to the top-100 S&P 500 tickers.
    features:
        List of FeatureEngine feature names to use.  Defaults to all 30
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
    target_winsor_q:
        Quantile for winsorizing the training target (0 disables).
    feature_winsor_q:
        Quantile for winsorizing features per date (0 disables).
    train_window_days:
        Max number of trading days to keep in the training window.
    sample_decay_half_life_days:
        Exponential time-decay half-life in days for sample weights.
    center_predictions:
        If True, subtract the cross-sectional mean prediction before ranking.
    use_rank_target:
        If True, transform the raw forward return target into a cross-sectional
        rank score in [-1, 1].  This removes market beta noise and focuses
        the model on relative stock performance.
    purge_embargo_days:
        Number of days to embargo between train and validation sets to
        prevent forward return overlap / data leakage.
    use_fundamentals:
        If True (default), append the fundamental valuation features from
        ``quantify.data.fundamentals`` (earnings_yield, book_to_market,
        fcf_yield, roe) to the technical feature set.  These columns must be
        added to the input data frames via ``add_fundamental_features``;
        they are not computed by FeatureEngine.
    """

    name: str = "ml_return_predictor"
    rebalance_frequency: str = "weekly"
    lookback_days: int = 1200  # 504 train + buffer

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
        target_winsor_q: float = _TARGET_WINSOR_Q,
        feature_winsor_q: float = _FEATURE_WINSOR_Q,
        train_window_days: int = _TRAIN_WINDOW_DAYS,
        sample_decay_half_life_days: int = _DECAY_HALFLIFE_DAYS,
        center_predictions: bool = True,
        allow_fallback: bool = True,
        use_rank_target: bool = True,
        purge_embargo_days: int = _PURGE_EMBARGO_DAYS,
        train_enabled: bool = True,
        use_fundamentals: bool = True,
        use_sector_rs: bool = False,
    ) -> None:
        self.universe: list[str] = universe if universe is not None else get_sp500()
        self.use_fundamentals = use_fundamentals
        self.use_sector_rs = use_sector_rs
        # Technical features come from FeatureEngine; sector RS and fundamental
        # features are appended onto the data frames separately.
        self.technical_features: list[str] = (
            list(features) if features is not None else list(_ALL_FEATURES)
        )
        self.sector_features: list[str] = list(_SECTOR_FEATURES) if use_sector_rs else []
        self.cs_features: list[str] = list(_CS_FEATURES)
        if use_fundamentals:
            self.features = (
                self.technical_features
                + self.sector_features
                + self.cs_features
                + list(FUNDAMENTAL_FEATURES)
            )
        else:
            self.features = self.technical_features + self.sector_features + self.cs_features
        self.min_train_bars = min_train_bars
        self.retrain_interval_days = retrain_interval_days
        self.rebalance_days = rebalance_days
        self.long_decile = long_decile
        self.short_decile = short_decile
        self.lgbm_params = lgbm_params if lgbm_params is not None else dict(_LGBM_PARAMS)
        self.target_winsor_q = target_winsor_q
        self.feature_winsor_q = feature_winsor_q
        self.train_window_days = train_window_days
        self.sample_decay_half_life_days = sample_decay_half_life_days
        self.center_predictions = center_predictions
        self.allow_fallback = allow_fallback
        self.use_rank_target = use_rank_target
        self.purge_embargo_days = purge_embargo_days
        self.train_enabled = train_enabled

        # Ensure lookback window is large enough for the training horizon
        min_lookback = max(self.min_train_bars + 30, self.train_window_days + 30)
        self.lookback_days = max(self.lookback_days, min_lookback)

        # Model state
        self._model: Any = None
        self._feature_importances: Optional[dict[str, float]] = None
        self._model_backends: list[str] = []
        self._model_metrics: Optional[dict[str, float]] = None
        self._last_train_date: Optional[datetime] = None
        self._last_rebalance_date: Optional[datetime] = None
        self._signal_cache: list[Signal] = []
        self._last_feature_values: dict[str, dict[str, float]] = {}
        self._last_feature_zscores: dict[str, dict[str, float]] = {}
        self._last_prediction_dispersion: dict[str, float] = {}

        # Persistence paths
        self._model_path = "./models/ml_return_predictor.joblib"
        self._model_meta_path = "./models/ml_return_predictor_meta.json"

        # Try to load persisted model if present
        try:
            import joblib

            self._model = joblib.load(self._model_path)
            log.info("%s: loaded persisted model from %s", self.name, self._model_path)

            # Align the feature list with the persisted model's metadata so
            # inference always matches the feature set the model was trained
            # with (prevents shape mismatch when the cached model was trained
            # with a different feature list).
            #
            # Only do this for inference (train_enabled=False).  In training
            # mode we must keep the freshly-built full feature set: otherwise
            # each training run would inherit the *previously persisted*
            # model's feature list and re-save it, a feedback loop that can
            # silently collapse the model to whatever reduced set was last
            # written to disk.
            if not self.train_enabled:
                try:
                    import json

                    with open(self._model_meta_path) as fh:
                        meta = json.load(fh)
                    persisted_features = meta.get("features")
                    if isinstance(persisted_features, list) and persisted_features:
                        self.features = list(persisted_features)
                        log.info("%s: explicitly set features to %d items from persisted model", self.name, len(self.features))
                except Exception as exc:
                    log.warning("%s: failed to load persisted features: %s", self.name, exc)
                    
                # Always trust the model itself if available
                if hasattr(self._model, "feature_names_in_"):
                    self.features = list(self._model.feature_names_in_)
                    log.info("%s: explicitly set features to %d items from model.feature_names_in_", self.name, len(self.features))
            else:
                # Training mode: keep the full intended feature set.
                # If the persisted model was trained on a different set, discard
                # it so any prediction before the first retrain uses the new
                # set rather than causing a shape mismatch.
                try:
                    import json

                    with open(self._model_meta_path) as fh:
                        meta = json.load(fh)
                    persisted_features = meta.get("features")
                    if isinstance(persisted_features, list) and persisted_features != self.features:
                        log.info(
                            "%s: persisted model feature set differs from current — "
                            "discarding loaded model; will retrain.",
                            self.name,
                        )
                        self._model = None
                except Exception:
                    pass
        except Exception:
            # No persisted model available — will train on demand
            self._model = None

        # Accumulated training data (symbol-agnostic: stack all symbols)
        self._train_X: Optional[pd.DataFrame] = None
        self._train_y: Optional[pd.Series] = None

        log.info(
            "MLReturnPredictorStrategy initialised: %d symbols, %d features",
            len(self.universe),
            len(self.features),
        )

    def get_required_features(self) -> list[str]:
        """
        Return the technical feature names required from FeatureEngine.

        Fundamental features (see ``quantify.data.fundamentals``) are NOT
        included here because they are not registered with FeatureEngine —
        they are appended onto the data frames separately.
        """
        return list(self.technical_features)

    def on_start(self) -> None:
        """
        Reset training state at session start.

        NOTE: We intentionally preserve ``self._model`` if it was loaded from
        disk so the strategy can produce predictions immediately while waiting
        for enough data to retrain.
        """
        # Keep self._model — it was loaded from persistence in __init__
        self._feature_importances = None
        self._model_backends = []
        self._model_metrics = None
        self._last_train_date = None
        self._last_rebalance_date = None
        self._signal_cache = []
        self._train_X = None
        self._train_y = None
        self._last_feature_values = {}
        self._last_feature_zscores = {}
        self._last_prediction_dispersion = {}
        log.info("%s: training state reset on start (model preserved: %s)", self.name, self._model is not None)

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

        data = self._filter_to_universe(data)
        if not data:
            log.warning("%s: no universe symbols present in input data", self.name)
            return []

        timestamp = self._latest_timestamp(data)

        # ---- Rebalance gate ----
        if not self._should_rebalance(timestamp):
            return list(self._signal_cache)

        # ---- Build the cross-sectional training dataset only when needed ----
        # Assembling this matrix is expensive (a concat across the universe
        # plus several per-date groupby transforms over ~3 years of history).
        # It is only required when we are about to retrain, or when no model
        # exists yet and we must choose between training and the lightweight
        # fallback.  On the intervening weekly rebalances — a model already
        # exists and no retrain is due — we skip the rebuild and go straight
        # to prediction.  (Retraining is monthly while rebalancing is weekly,
        # so this avoids ~3 redundant rebuilds per retrain cycle.)
        want_retrain = self.train_enabled and self._should_retrain(timestamp)
        X_all = y_all = None
        if want_retrain or self._model is None:
            X_all, y_all = self._build_training_data(data)

        # ---- No usable model AND insufficient training data → fallback ----
        if self._model is None and (X_all is None or len(X_all) < self.min_train_bars):
            n_samples = 0 if X_all is None else len(X_all)
            log.warning(
                "%s: only %d training samples available (need %d)",
                self.name,
                n_samples,
                self.min_train_bars,
            )
            # Fall back to a lightweight cross-sectional scorer if enabled
            if self.allow_fallback:
                log.info("%s: using lightweight fallback scorer", self.name)
                predictions = self._fallback_predict(data)
                if not predictions:
                    self._last_rebalance_date = timestamp
                    return []

                signals = self._rank_and_signal(predictions, timestamp)
                self._signal_cache = signals
                self._last_rebalance_date = timestamp
                return signals

            self._last_rebalance_date = timestamp
            return []

        # ---- Retrain if due (and enough data was assembled) ----
        if want_retrain:
            if X_all is not None and len(X_all) >= self.min_train_bars:
                self._train_model(X_all, y_all, timestamp)
            else:
                # Retrain was due but there isn't enough data to train on.
                # Stamp the train date anyway so _should_retrain backs off for
                # the normal interval; otherwise want_retrain stays True and
                # the expensive cross-sectional training matrix is rebuilt on
                # every weekly rebalance until enough history accrues.
                log.warning(
                    "%s: retrain due but skipped — only %d training samples (need %d)",
                    self.name,
                    0 if X_all is None else len(X_all),
                    self.min_train_bars,
                )
                self._last_train_date = timestamp
        elif not self.train_enabled and self._model is None:
            # Attempt to load model dynamically if it was just downloaded
            try:
                import joblib
                self._model = joblib.load(self._model_path)
            except Exception:
                pass

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

        Features are cross-sectionally standardized per timestamp.
        The target is transformed into cross-sectional ranks in [-1, 1] so
        the model learns *relative* stock performance, removing market beta.
        Training data is limited to a sliding window and the target is
        winsorized to reduce the impact of outliers.
        """
        data = self._filter_to_universe(data)
        X_parts: list[pd.DataFrame] = []
        # CS features are computed from the full cross-section after stacking;
        # they are never present in individual stock DataFrames.
        stock_feats = [f for f in self.features if f not in self.cs_features]

        for symbol, df in data.items():
            if df.empty or len(df) < _FORWARD_RETURN_DAYS + 30:
                continue

            missing = [f for f in stock_feats if f not in df.columns]
            if missing:
                log.debug("%s: %s missing features: %s", self.name, symbol, missing)
                continue

            # Features matrix (all bars except last N, since we need forward ret)
            n = len(df) - _FORWARD_RETURN_DAYS
            if n < 20:
                continue

            feat_df = df[stock_feats].iloc[:n].copy()

            # FIX Bug #1: Correct forward return computation.
            # We want the return from day t to day t+N:
            #   fwd_ret_t = close_{t+N} / close_t - 1
            # This avoids the pct_change().shift() double-counting bug.
            fwd_ret = (
                df["close"].shift(-_FORWARD_RETURN_DAYS) / df["close"] - 1.0
            ).iloc[:n]

            # Align and drop NaNs
            valid_mask = feat_df.notna().all(axis=1) & fwd_ret.notna()
            feat_df = feat_df[valid_mask]
            fwd_ret = fwd_ret[valid_mask]

            if feat_df.empty:
                continue

            # Tag with symbol for cross-sectional operations
            feat_df["target"] = fwd_ret.values
            feat_df["_symbol"] = symbol
            X_parts.append(feat_df)

        if not X_parts:
            return None, None

        all_data = pd.concat(X_parts, axis=0)

        # Constrain to sliding window (defaults to ~3 years)
        unique_dates = all_data.index.unique().sort_values()
        if len(unique_dates) > self.train_window_days:
            start_date = unique_dates[-self.train_window_days]
            all_data = all_data[all_data.index >= start_date]

        # Winsorize stock-level feature tails per date (CS features not computed yet)
        if 0.0 < self.feature_winsor_q < 0.5:
            q = self.feature_winsor_q
            try:
                stock_feats_to_winsorize = [
                    f for f in self.features
                    if f not in self.cs_features and f in all_data.columns
                ]
                winsorized = all_data[stock_feats_to_winsorize].groupby(level=0).transform(
                    lambda s: s.clip(lower=s.quantile(q), upper=s.quantile(1.0 - q))
                )
                all_data[stock_feats_to_winsorize] = winsorized
            except Exception:
                log.debug("%s: feature winsorization skipped", self.name)

        # Compute cross-sectional regime features from the (winsorized) stock data.
        # transform broadcasts the per-date aggregate to every row within that date.
        # These are kept in raw form — z-scoring them per date would collapse them to zero.
        if "cs_mkt_return_252d" in self.cs_features and "return_252d" in all_data.columns:
            all_data["cs_mkt_return_252d"] = (
                all_data.groupby(level=0)["return_252d"].transform("mean")
            )
        if "cs_mkt_vol_60d" in self.cs_features and "volatility_60d" in all_data.columns:
            all_data["cs_mkt_vol_60d"] = (
                all_data.groupby(level=0)["volatility_60d"].transform("mean")
            )
        if "cs_return_dispersion" in self.cs_features and "return_5d" in all_data.columns:
            all_data["cs_return_dispersion"] = (
                all_data.groupby(level=0)["return_5d"].transform("std")
            )

        # Winsorize raw target tails before rank transformation
        if 0.0 < self.target_winsor_q < 0.5:
            try:
                low = float(all_data["target"].quantile(self.target_winsor_q))
                high = float(all_data["target"].quantile(1.0 - self.target_winsor_q))
                all_data["target"] = all_data["target"].clip(lower=low, upper=high)
            except Exception:
                log.debug("%s: target winsorization skipped", self.name)

        # FIX Bug #7: Cross-sectional rank target transformation.
        # Instead of predicting raw returns (dominated by market noise),
        # we predict the cross-sectional rank of each stock's return on
        # each date.  This focuses the model on *relative* performance.
        if self.use_rank_target:
            try:
                # Rank within each date, scaled to [0, 1]
                ranked = all_data.groupby(level=0)["target"].rank(pct=True)
                # Map to [-1, 1] so the model has a symmetric target
                all_data["target"] = ranked * 2.0 - 1.0
            except Exception:
                log.debug("%s: rank target transformation skipped", self.name)

        # Cross-sectional standardization (z-score per timestamp) for stock-level features only.
        # CS features are constant within each day — applying the cross-sectional z-score
        # would collapse them to zero and destroy their time-series information.
        def zscore(x: pd.Series) -> pd.Series:
            std = x.std()
            if len(x) > 1 and std > 0:
                return (x - x.mean()) / std
            return x - x.mean()

        stock_feats = [f for f in self.features if f not in self.cs_features]
        feature_normed = all_data.groupby(level=0)[stock_feats].transform(zscore)
        valid_mask = feature_normed.notna().all(axis=1)
        feature_normed = feature_normed[valid_mask]

        if feature_normed.empty:
            return None, None

        # Append CS regime features in raw form — their time-series variation is what
        # gives the ensemble market-regime context.
        cs_feats_present = [f for f in self.cs_features if f in all_data.columns]
        if cs_feats_present:
            X_all = pd.concat(
                [feature_normed, all_data.loc[valid_mask, cs_feats_present]], axis=1
            )
        else:
            X_all = feature_normed

        y_all = all_data.loc[valid_mask, "target"]

        return X_all, y_all

    # ------------------------------------------------------------------
    # Model training
    # ------------------------------------------------------------------

    def _train_model(
        self, X: pd.DataFrame, y: pd.Series, timestamp: Optional[datetime] = None
    ) -> None:
        """
        Fit a stacking ensemble (or sklearn fallback) regressor on the full
        training dataset, using a purged time-series split for validation.

        Parameters
        ----------
        X, y:
            Training feature matrix and target vector.
        timestamp:
            The *historical* timestamp of the current step (e.g. the backtest
            bar date).  Recorded as ``_last_train_date`` so the time-based
            retrain cadence in :meth:`_should_retrain` works in backtests.  If
            omitted (e.g. one-off training from a script), the real wall-clock
            time is used instead.
        """
        log.info(
            "%s: training model on %d samples × %d features",
            self.name, len(X), len(self.features),
        )

        model, backends = _build_model(self.lgbm_params)
        if model is None:
            log.error("%s: no ML backend available (LightGBM or sklearn)", self.name)
            return

        X = X.sort_index()
        # Prefer positional alignment: the training data (X, y) are built together
        # in _build_training_data and should have the same length. Reindexing
        # against duplicate timestamp labels can fail, so align by position.
        if len(y) != len(X):
            log.error(
                "%s: training length mismatch: X=%d rows, y=%d rows — aborting training",
                self.name,
                len(X),
                len(y),
            )
            return
        y = pd.Series(y.values, index=X.index)

        # FIX Bug #5: Purged time-series split with embargo gap.
        # The embargo gap prevents forward return overlap between the last
        # training samples and the first validation samples.
        X_train = X
        y_train = y
        X_val = None
        y_val = None
        unique_dates = X.index.unique().sort_values()
        if len(unique_dates) >= 50:
            cutoff_idx = int(len(unique_dates) * 0.8)
            cutoff_date = unique_dates[max(cutoff_idx, 1)]

            # Embargo: skip `purge_embargo_days` after the cutoff to prevent
            # the last training samples' forward returns from overlapping
            # with the first validation samples' features.
            embargo_idx = min(cutoff_idx + self.purge_embargo_days, len(unique_dates) - 1)
            embargo_date = unique_dates[embargo_idx]

            train_mask = X.index < cutoff_date
            val_mask = X.index > embargo_date

            X_train = X[train_mask]
            y_train = y[train_mask]
            X_val = X[val_mask]
            y_val = y[val_mask]

            log.info(
                "%s: train/val split: train=%d (to %s), embargo=%d days, val=%d (from %s)",
                self.name,
                len(X_train),
                cutoff_date.strftime("%Y-%m-%d") if hasattr(cutoff_date, "strftime") else str(cutoff_date),
                self.purge_embargo_days,
                len(X_val) if X_val is not None else 0,
                embargo_date.strftime("%Y-%m-%d") if hasattr(embargo_date, "strftime") else str(embargo_date),
            )

        sample_weight = self._compute_sample_weights(X_train.index)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                # Fit using DataFrame/Series to preserve feature names where
                # possible. Many ML backends accept pandas objects and this
                # preserves column names for later prediction.
                if sample_weight is not None:
                    model.fit(
                        X_train[self.features],
                        y_train,
                        sample_weight=sample_weight,
                    )
                else:
                    model.fit(X_train[self.features], y_train)
            except Exception as exc:
                log.exception("%s: model training failed: %s", self.name, exc)
                return

        self._model = model
        self._model_backends = backends

        # Extract feature importances
        self._feature_importances = _extract_feature_importances(model, self.features)
        if self._feature_importances:
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

        # Record training date.  Prefer the historical (backtest) timestamp so
        # the time-based retrain cadence works when replaying past data; fall
        # back to wall-clock time for one-off/live training without a step ts.
        self._last_train_date = timestamp if timestamp is not None else datetime.now(timezone.utc)
        log.info("%s: model training complete", self.name)
        log.info("%s: model backends in use: %s", self.name, ", ".join(self._model_backends))

        # FIX Bug #2: Compute validation metrics BEFORE persisting the model,
        # so `_model_metrics` is populated when we write the metadata file.
        self._model_metrics = None
        if X_val is not None and y_val is not None and not X_val.empty:
            try:
                pred_val = model.predict(X_val[self.features])
                err = pred_val - y_val.values
                rmse = float(np.sqrt(np.mean(err ** 2)))
                mae = float(np.mean(np.abs(err)))
                hit_rate = float(np.mean(np.sign(pred_val) == np.sign(y_val.values)))
                ic = float(pd.Series(pred_val).corr(pd.Series(y_val.values), method="spearman"))
                self._model_metrics = {
                    "rmse": rmse,
                    "mae": mae,
                    "hit_rate": hit_rate,
                    "spearman_ic": ic,
                }
                log.info(
                    "%s: validation metrics rmse=%.4f mae=%.4f hit=%.2f ic=%.3f",
                    self.name,
                    rmse,
                    mae,
                    hit_rate,
                    ic,
                )
            except Exception as exc:
                log.debug("%s: validation metrics failed: %s", self.name, exc)

        # Persist model and metadata AFTER computing metrics
        try:
            import joblib
            import json
            import os

            os.makedirs(os.path.dirname(self._model_path), exist_ok=True)
            joblib.dump(self._model, self._model_path)
            meta = {
                "last_train_date": self._last_train_date.isoformat() if self._last_train_date else None,
                "model_backends": self._model_backends,
                "feature_importances": self._feature_importances,
                "model_metrics": self._model_metrics,
                "features": list(self.features),
            }
            with open(self._model_meta_path, "w") as fh:
                json.dump(meta, fh)
            log.info("%s: persisted model and metadata", self.name)
        except Exception:
            log.debug("%s: model persistence failed", self.name)

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def _predict(
        self, data: dict[str, pd.DataFrame]
    ) -> dict[str, float]:
        """
        Predict the forward return rank score for each symbol using the
        current bar's feature vector.

        Returns a dict of {symbol: predicted_rank_score}.
        """
        data = self._filter_to_universe(data)

        # Collect current feature rows for all symbols
        current_features = {}
        stock_feats = [f for f in self.features if f not in self.cs_features]
        for symbol, df in data.items():
            if df.empty or len(df) < 30:
                continue

            missing = [f for f in stock_feats if f not in df.columns]
            if missing:
                log.warning("%s: %s missing features: %s", self.name, symbol, missing)
                continue

            # Use the most recent complete bar (stock-level features only)
            feat_row = df[stock_feats].iloc[-1]
            if feat_row.isna().any():
                nan_cols = feat_row.index[feat_row.isna()].tolist()
                log.warning("%s: %s has NaN features at latest bar: %s", self.name, symbol, nan_cols)
                continue

            current_features[symbol] = feat_row

        if not current_features:
            return {}

        # Build DataFrame from stock-level features (CS features added separately below)
        feat_df = pd.DataFrame.from_dict(current_features, orient="index")
        raw_df = feat_df.copy()

        # Compute cross-sectional regime features from the current universe snapshot.
        # These are the same aggregates computed per-date during training.
        cs_vals: dict[str, float] = {}
        if len(feat_df) > 1:
            if "cs_mkt_return_252d" in self.cs_features and "return_252d" in feat_df.columns:
                cs_vals["cs_mkt_return_252d"] = float(feat_df["return_252d"].mean())
            if "cs_mkt_vol_60d" in self.cs_features and "volatility_60d" in feat_df.columns:
                cs_vals["cs_mkt_vol_60d"] = float(feat_df["volatility_60d"].mean())
            if "cs_return_dispersion" in self.cs_features and "return_5d" in feat_df.columns:
                cs_vals["cs_return_dispersion"] = float(feat_df["return_5d"].std())

        # Regime gate: sit out when the broad market is in a sustained downtrend.
        # Momentum signals fail systematically in these periods (confirmed by walk-forward
        # showing IC clusters of -0.25 to -0.40 coinciding with bear market windows).
        cs_mkt_ret = cs_vals.get("cs_mkt_return_252d")
        if cs_mkt_ret is not None and cs_mkt_ret < _REGIME_GATE_RETURN_THRESHOLD:
            log.info(
                "%s: regime gate — suppressing signals "
                "(cs_mkt_return_252d=%.3f < threshold=%.2f)",
                self.name, cs_mkt_ret, _REGIME_GATE_RETURN_THRESHOLD,
            )
            return {}

        # Z-score stock-level features cross-sectionally
        if len(feat_df) > 1:
            stds = feat_df.std()
            stds[stds == 0] = 1.0  # Avoid division by zero
            feat_df = (feat_df - feat_df.mean()) / stds
        else:
            feat_df = feat_df - feat_df.mean()

        # Append CS regime features as raw (unscaled) columns.
        # They must NOT be cross-sectionally z-scored — the constant-within-day value
        # would collapse to zero, destroying the regime signal.
        for cs_feat, cs_val in cs_vals.items():
            feat_df[cs_feat] = cs_val

        self._last_feature_values = raw_df.to_dict(orient="index")
        self._last_feature_zscores = feat_df.to_dict(orient="index")

        predictions: dict[str, float] = {}

        try:
            model_input = feat_df[self.features] if all(f in feat_df.columns for f in self.features) else feat_df
            # StackingRegressor converts DataFrames to numpy arrays internally
            # before calling each base learner, triggering a LightGBM feature-name
            # warning that is harmless (column order is guaranteed by model_input
            # construction above). Suppress it at the call site.
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="X does not have valid feature names",
                    category=UserWarning,
                )
                model_preds = self._model.predict(model_input)
            for symbol, pred in zip(feat_df.index, model_preds):
                predictions[symbol] = float(pred)
        except Exception as exc:
            log.debug("%s: prediction batch failed: %s", self.name, exc)
            for symbol in feat_df.index:
                try:
                    row = feat_df.loc[symbol].values.reshape(1, -1)
                    pred = self._model.predict(row)[0]
                    predictions[symbol] = float(pred)
                except Exception as exc2:
                    log.debug(
                        "%s: prediction failed for %s: %s", self.name, symbol, exc2
                    )

        self._last_prediction_dispersion = {}
        if hasattr(self._model, "estimators_"):
            try:
                estimator_preds: list[np.ndarray] = []
                # For StackingRegressor, estimators_ is a list of fitted base
                # estimators.  For VotingRegressor, it's similar.
                for estimator in self._model.estimators_:
                    if estimator is None:
                        continue
                    estimator_preds.append(estimator.predict(feat_df[self.features]))
                if estimator_preds:
                    stacked = np.vstack(estimator_preds)
                    dispersion = np.nanstd(stacked, axis=0)
                    self._last_prediction_dispersion = {
                        symbol: float(disp)
                        for symbol, disp in zip(feat_df.index, dispersion)
                    }
            except Exception as exc:
                log.debug("%s: prediction dispersion failed: %s", self.name, exc)

        return predictions

    def _fallback_predict(self, data: dict[str, pd.DataFrame]) -> dict[str, float]:
        """
        Lightweight fallback predictor used when there isn't enough training data.
        Uses recent short-horizon returns (5-day) and adjusts by volatility.
        Returns a dict of {symbol: score} where larger = more bullish.
        """
        data = self._filter_to_universe(data)
        scores: dict[str, float] = {}

        for symbol, df in data.items():
            try:
                if df.empty or len(df) < 5:
                    continue

                horizons = [
                    ("return_5d", 5, 0.50),
                    ("return_21d", 21, 0.30),
                    ("return_63d", 63, 0.20),
                ]
                weighted_ret = 0.0
                for feat, days, weight in horizons:
                    if feat in df.columns:
                        r = float(df[feat].iloc[-1])
                    else:
                        r = float(df["close"].pct_change(days).iloc[-1])
                    if not pd.isna(r):
                        weighted_ret += weight * r

                vol = float(df["close"].pct_change().rolling(20).std().iloc[-1])
                if vol <= 0 or pd.isna(vol):
                    vol = 1.0

                score = weighted_ret / vol
                scores[symbol] = float(score)
            except Exception:
                continue

        if not scores:
            return {}

        # Cross-sectional z-score to align with existing pipeline
        s = pd.Series(scores)
        if len(s) > 1:
            s = (s - s.mean()) / (s.std() if s.std() > 0 else 1.0)
        else:
            s = s - s.mean()

        return {k: float(v) for k, v in s.to_dict().items()}

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
        pred_for_rank = pred_series
        if self.center_predictions and len(pred_series) > 1:
            pred_for_rank = pred_series - pred_series.mean()
        pct_ranks = pred_for_rank.rank(pct=True)

        # Normalise predictions to [-1, 1] for strength
        max_abs = pred_for_rank.abs().max()
        if max_abs < 1e-10:
            max_abs = 1.0

        dispersion_scale = None
        if self._last_prediction_dispersion:
            dispersion_vals = np.array(list(self._last_prediction_dispersion.values()))
            dispersion_scale = float(np.median(dispersion_vals)) if dispersion_vals.size else None
            if dispersion_scale is not None and dispersion_scale <= 0:
                dispersion_scale = None

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
            norm_strength = float(np.clip(abs(pred_for_rank[symbol]) / max_abs, 0.0, 1.0))

            dispersion = self._last_prediction_dispersion.get(symbol)
            confidence = 1.0
            if dispersion is not None and dispersion_scale is not None:
                confidence = float(1.0 / (1.0 + (dispersion / dispersion_scale)))
                confidence = float(np.clip(confidence, 0.2, 1.0))

            explanations = self._build_explanations(symbol)

            if pct_rank >= self.long_decile:
                direction = "long"
                strength = norm_strength * confidence
            elif pct_rank <= self.short_decile:
                direction = "short"
                strength = -norm_strength * confidence
            else:
                direction = "close"
                strength = 0.0

            meta: dict[str, Any] = {
                "predicted_return_21d": round(pred_ret, 6),
                "predicted_return_21d_centered": round(float(pred_for_rank[symbol]), 6),
                "percentile_rank": round(float(pct_rank), 4),
                "last_train_date": (
                    self._last_train_date.isoformat(timespec="seconds")
                    if self._last_train_date
                    else None
                ),
                "n_predictions": len(predictions),
                "model_backends": list(self._model_backends),
                "target_winsor_q": self.target_winsor_q,
                "feature_winsor_q": self.feature_winsor_q,
                "train_window_days": self.train_window_days,
                "use_rank_target": self.use_rank_target,
                "purge_embargo_days": self.purge_embargo_days,
            }
            if dispersion is not None:
                meta["prediction_dispersion"] = round(float(dispersion), 6)
                meta["prediction_confidence"] = round(float(confidence), 4)
            if fi_meta is not None:
                meta["feature_importance_top10"] = fi_meta
            if explanations:
                meta["explanations"] = explanations
            if self._model_metrics:
                meta["model_metrics"] = dict(self._model_metrics)

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
        # Retrain cadence is purely time-based: retrain on the first call (no
        # prior train date) and thereafter once retrain_interval_days have
        # elapsed.  This intentionally does NOT short-circuit on
        # ``self._model is None`` — coupling the cadence to model existence made
        # the _last_train_date back-off ineffective (it would keep returning
        # True while no model existed, defeating the stamp set when a retrain is
        # skipped for insufficient data).  The separate "build the matrix even
        # without a model" cold-start need is handled by the build guard in
        # generate_signals, not here.
        if self._last_train_date is None:
            return True
        delta = timestamp - self._last_train_date
        return delta.days >= self.retrain_interval_days

    def _build_explanations(self, symbol: str) -> list[dict[str, Any]]:
        zscores = self._last_feature_zscores.get(symbol)
        raw_vals = self._last_feature_values.get(symbol, {})
        if not zscores:
            return []

        use_importance = bool(self._feature_importances)
        importances = self._feature_importances or {}
        items: list[tuple[float, str, float, Optional[float], Optional[float]]] = []

        for feat in self.features:
            z = zscores.get(feat)
            if z is None or pd.isna(z):
                continue
            weight = float(importances.get(feat, 0.0)) if use_importance else None
            score = abs(float(z)) * (weight if weight and weight > 0 else 1.0)
            raw = raw_vals.get(feat)
            raw_val = None if raw is None or pd.isna(raw) else float(raw)
            items.append((score, feat, float(z), raw_val, weight))

        if not items:
            return []

        items.sort(key=lambda x: x[0], reverse=True)
        top = items[:3]
        explanations: list[dict[str, Any]] = []
        for score, feat, z, raw_val, weight in top:
            explanations.append({
                "feature": feat,
                "zscore": round(z, 4),
                "value": None if raw_val is None else round(raw_val, 6),
                "weight": None if weight is None else round(weight, 4),
                "direction": "higher" if z >= 0 else "lower",
                "score": round(float(score), 4),
            })
        return explanations

    def _compute_sample_weights(self, index: pd.Index) -> Optional[np.ndarray]:
        if self.sample_decay_half_life_days <= 0:
            return None
        if not isinstance(index, pd.Index) or index.empty:
            return None
        try:
            dates = pd.to_datetime(index).normalize()
            last_date = dates.max()
            age_days = (last_date - dates).days.astype(float)
            weights = np.power(0.5, age_days / float(self.sample_decay_half_life_days))
            mean_weight = float(np.mean(weights)) if len(weights) else 1.0
            if mean_weight > 0:
                weights = weights / mean_weight
            # Ensure we return a plain numpy array (CatBoost and some sklearn
            # impls reject pandas Index objects as sample_weight).
            return np.asarray(weights, dtype=float)
        except Exception:
            return None

    def _filter_to_universe(self, data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
        universe_set = set(self.universe)
        filtered = {symbol: df for symbol, df in data.items() if symbol in universe_set}
        dropped = sorted(set(data) - universe_set)
        if dropped:
            log.debug(
                "%s: ignoring %d symbols outside universe: %s",
                self.name,
                len(dropped),
                ", ".join(dropped[:10]),
            )
        return filtered

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
# Feature importance extraction helpers
# ---------------------------------------------------------------------------


def _extract_feature_importances(
    model: Any, feature_names: list[str]
) -> Optional[dict[str, float]]:
    """
    Extract feature importances from various model types:
    - StackingRegressor: average importances across base estimators
    - VotingRegressor: average importances across estimators
    - Single estimator: use feature_importances_ directly
    """
    try:
        # StackingRegressor / VotingRegressor: aggregate from base estimators
        if hasattr(model, "estimators_") and isinstance(model.estimators_, list):
            all_importances: list[np.ndarray] = []
            for estimator in model.estimators_:
                if estimator is None:
                    continue
                imp = getattr(estimator, "feature_importances_", None)
                if imp is not None and len(imp) == len(feature_names):
                    all_importances.append(np.array(imp, dtype=float))

            if all_importances:
                # Average importances across all base estimators
                avg_imp = np.mean(all_importances, axis=0)
                return {
                    feat: float(imp)
                    for feat, imp in zip(feature_names, avg_imp)
                }

        # Single estimator fallback
        importances = getattr(model, "feature_importances_", None)
        if importances is not None and len(importances) == len(feature_names):
            return {
                feat: float(imp)
                for feat, imp in zip(feature_names, importances)
            }

        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Backend selection: Stacking ensemble with LightGBM, XGBoost, CatBoost
# ---------------------------------------------------------------------------


def _build_model(params: dict[str, Any]) -> tuple[Any, list[str]]:
    """
    Return a StackingRegressor ensemble of LightGBM, XGBoost, and CatBoost
    with a Ridge meta-learner, plus a list of backend names actually used.

    The stacking approach is superior to VotingRegressor because:
    1. The meta-learner learns optimal weights from data (not fixed/equal)
    2. It captures complementary strengths of each base learner
    3. Cross-validated base predictions prevent overfitting
    """
    from sklearn.linear_model import RidgeCV

    estimators: list[tuple[str, Any]] = []
    backends: list[str] = []

    # 1. LightGBM
    try:
        from lightgbm import LGBMRegressor
        estimators.append(("lgbm", LGBMRegressor(**params)))
        backends.append("lgbm")
    except ImportError:
        log.error("LightGBM not found for ensemble.")

    # 2. XGBoost — use _XGB_PARAMS for library-specific settings; share structural
    #    params (learning_rate, n_estimators, subsample, reg) from lgbm_params.
    try:
        from xgboost import XGBRegressor
        xgb_params = {
            "n_estimators": params.get("n_estimators", 400),
            "learning_rate": params.get("learning_rate", 0.02),
            "max_depth": _XGB_PARAMS["max_depth"],
            "min_child_weight": _XGB_PARAMS["min_child_weight"],
            "subsample": params.get("subsample", 0.8),
            "colsample_bytree": params.get("colsample_bytree", 0.8),
            "reg_alpha": params.get("reg_alpha", 1.0),
            "reg_lambda": params.get("reg_lambda", 1.0),
            "n_jobs": -1,
            "random_state": 42,
            "verbosity": 0,
        }
        estimators.append(("xgboost", XGBRegressor(**xgb_params)))
        backends.append("xgboost")
    except ImportError:
        log.error("XGBoost not found for ensemble.")

    # 3. CatBoost — same principle: own depth/leaf settings, shared structural params.
    try:
        from catboost import CatBoostRegressor
        cb_params = {
            "iterations": params.get("n_estimators", 400),
            "learning_rate": params.get("learning_rate", 0.02),
            "depth": _CB_PARAMS["depth"],
            "min_data_in_leaf": _CB_PARAMS["min_data_in_leaf"],
            "random_strength": _CB_PARAMS["random_strength"],
            "l2_leaf_reg": params.get("reg_lambda", 1.0),
            "verbose": False,
            "random_seed": 42,
        }
        estimators.append(("catboost", CatBoostRegressor(**cb_params)))
        backends.append("catboost")
    except ImportError:
        log.error("CatBoost not found for ensemble.")

    if not estimators:
        log.error("No ML backends available! Falling back to sklearn.")
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor(n_estimators=100), ["sklearn_fallback"]

    if len(estimators) == 1:
        # Only one backend available — return it directly (no stacking overhead)
        return estimators[0][1], backends

    # FIX Bug #6: Use StackingRegressor instead of VotingRegressor.
    # The Ridge meta-learner learns optimal combination weights from data
    # rather than using fixed/equal weights, and the cross-validated base
    # predictions prevent overfitting.
    try:
        from sklearn.ensemble import StackingRegressor

        stacking = StackingRegressor(
            estimators=estimators,
            final_estimator=RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0, 100.0]),
            cv=5,
            n_jobs=-1,
            passthrough=False,
        )
        return stacking, backends
    except Exception as exc:
        log.warning("StackingRegressor failed, falling back to VotingRegressor: %s", exc)
        from sklearn.ensemble import VotingRegressor
        return VotingRegressor(estimators=estimators), backends


__all__ = ["MLReturnPredictorStrategy"]
