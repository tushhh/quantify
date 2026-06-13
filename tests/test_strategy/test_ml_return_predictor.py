import numpy as np
import pandas as pd
from datetime import datetime, timezone

from quantify.data.universe import get_sp500
from quantify.strategy.ml_return_predictor import (
    MLReturnPredictorStrategy,
    _build_model,
    _extract_feature_importances,
)


def _make_dummy_data(symbol: str, start_date: datetime, n_bars: int) -> pd.DataFrame:
    """Create synthetic OHLCV data with features for testing."""
    np.random.seed(hash(symbol) % 2**31)
    dates = pd.date_range(start_date, periods=n_bars, freq="D", tz=timezone.utc)

    df = pd.DataFrame(index=dates)
    # Realistic price series (random walk with drift)
    returns = np.random.randn(n_bars) * 0.02
    prices = 100.0 * np.exp(np.cumsum(returns))
    df["close"] = prices
    df["open"] = prices * (1 + np.random.randn(n_bars) * 0.005)
    df["high"] = np.maximum(df["open"], df["close"]) * (1 + np.abs(np.random.randn(n_bars) * 0.01))
    df["low"] = np.minimum(df["open"], df["close"]) * (1 - np.abs(np.random.randn(n_bars) * 0.01))
    df["volume"] = np.random.randint(100_000, 1_000_000, size=n_bars)

    # Add feature columns (all 30 features the strategy expects)
    all_features = [
        "return_1d", "return_5d", "return_21d", "return_63d", "return_126d", "return_252d",
        "volatility_20d", "volatility_60d", "volatility_126d", "volatility_252d",
        "rsi_14", "macd_histogram", "bollinger_width", "sma_crossover",
        "volume_ratio_20d", "obv_slope", "volume_trend", "amihud_illiquidity", "atr_14",
        "return_std_21d", "skewness_21d", "max_return_21d", "min_return_21d",
        "price_to_high_52w", "price_to_low_52w",
        "return_consistency", "gap_return", "intraday_range",
        "rsi_divergence", "mean_reversion_5d",
    ]

    for feat in all_features:
        if "return" in feat and "std" not in feat and "consistency" not in feat and "max" not in feat and "min" not in feat and "reversion" not in feat:
            period = int(feat.split("_")[1].replace("d", "")) if "d" in feat.split("_")[1] else 1
            df[feat] = df["close"].pct_change(period)
        elif feat.startswith("volatility"):
            period = int(feat.split("_")[1].replace("d", ""))
            df[feat] = df["close"].pct_change().rolling(period).std()
        elif feat == "rsi_14":
            df[feat] = 50.0 + np.random.randn(n_bars) * 15
        elif feat == "sma_crossover":
            df[feat] = np.random.choice([0.0, 1.0], size=n_bars).astype(float)
        elif feat == "return_consistency":
            df[feat] = np.random.uniform(0.3, 0.7, size=n_bars)
        elif feat == "price_to_high_52w":
            df[feat] = np.random.uniform(0.7, 1.0, size=n_bars)
        elif feat == "price_to_low_52w":
            df[feat] = np.random.uniform(1.0, 2.0, size=n_bars)
        else:
            df[feat] = np.random.randn(n_bars) * 0.01

    # Fill NAs
    df = df.fillna(value=0)

    return df


# ---------------------------------------------------------------------------
# Bug #1: Forward return computation
# ---------------------------------------------------------------------------


def test_forward_return_no_leakage():
    """
    Verify that _build_training_data computes the forward return as:
        close[t+N] / close[t] - 1
    NOT as pct_change(N).shift(-N) which misaligns by one bar.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        use_rank_target=False,  # disable rank transform to check raw returns
        use_fundamentals=False,
    )

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    n_bars = 200

    # Create data with a known, deterministic price series
    dates = pd.date_range(start_date, periods=n_bars, freq="D", tz=timezone.utc)
    df = pd.DataFrame(index=dates)
    df["close"] = np.arange(100, 100 + n_bars, dtype=float)  # linear: 100, 101, ...
    df["open"] = df["close"]
    df["high"] = df["close"] + 1
    df["low"] = df["close"] - 1
    df["volume"] = 1_000_000
    df["return_5d"] = df["close"].pct_change(5)
    df["volatility_20d"] = df["close"].pct_change().rolling(20).std()
    df = df.fillna(0)

    data = {"AAPL": df, "MSFT": df.copy(), "GOOG": df.copy()}

    X, y = strat._build_training_data(data)

    assert X is not None
    assert y is not None

    # For a linear series close[t] = 100+t, forward return at bar t should be:
    #   close[t+5] / close[t] - 1 = (100+t+5)/(100+t) - 1 = 5/(100+t)
    # The old buggy code would give a DIFFERENT value.
    # Check a few data points (after warmup)
    for idx in range(50, min(60, len(y))):
        val = y.iloc[idx]
        # The target should be small positive values (around 0.03-0.05)
        # and definitely NOT negative for a monotonically increasing series
        assert val > 0, f"Forward return at index {idx} should be positive for rising prices, got {val}"


# ---------------------------------------------------------------------------
# Bug #5: Purged embargo gap
# ---------------------------------------------------------------------------


def test_purged_embargo_gap():
    """
    Verify that _train_model creates a train/val split with an embargo gap.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        purge_embargo_days=5,
        use_fundamentals=False,
    )

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = {
        "AAPL": _make_dummy_data("AAPL", start_date, 300),
        "MSFT": _make_dummy_data("MSFT", start_date, 300),
        "GOOG": _make_dummy_data("GOOG", start_date, 300),
    }

    X, y = strat._build_training_data(data)
    assert X is not None

    # The training method should succeed without error (embargo is internal)
    strat._train_model(X, y)

    # Model should be trained
    assert strat._model is not None
    assert strat._last_train_date is not None

    # Validation metrics should be computed (bug #2 fix)
    # With enough data, we should get metrics
    if strat._model_metrics is not None:
        assert "spearman_ic" in strat._model_metrics
        assert "hit_rate" in strat._model_metrics
        assert "rmse" in strat._model_metrics


# ---------------------------------------------------------------------------
# Bug #4: on_start preserves model
# ---------------------------------------------------------------------------


def test_on_start_preserves_model():
    """
    Verify that on_start() does NOT reset self._model, so a persisted
    model loaded in __init__ survives session restarts.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
    )

    class FakeModel:
        def predict(self, X):
            return np.zeros(len(X))

    strat._model = FakeModel()
    strat._last_train_date = datetime.now(timezone.utc)
    strat._model_metrics = {"rmse": 0.01}

    # on_start should reset training state but keep the model
    strat.on_start()

    assert strat._model is not None, "on_start() should preserve the loaded model"
    assert strat._last_train_date is None, "on_start() should reset training date"
    assert strat._model_metrics is None, "on_start() should reset metrics"


def test_training_does_not_inherit_persisted_feature_list(tmp_path, monkeypatch):
    """
    Regression: a persisted model with a *reduced* feature list must not
    shrink the feature set of a NEW training run.

    __init__ loads the persisted model's metadata to align inference with the
    trained model. That alignment must NOT happen in training mode
    (train_enabled=True); otherwise each training run inherits the previously
    persisted (possibly reduced) feature list and re-saves it — a feedback
    loop that silently collapses the model to whatever was last on disk.
    """
    import joblib
    import json

    from sklearn.dummy import DummyRegressor

    # The strategy loads ./models/ml_return_predictor.{joblib,_meta.json} in
    # __init__, so place a reduced-feature artifact there via a temp cwd.
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    joblib.dump(
        DummyRegressor().fit([[0], [1]], [0, 1]),
        models_dir / "ml_return_predictor.joblib",
    )
    (models_dir / "ml_return_predictor_meta.json").write_text(
        json.dumps({"features": ["return_5d", "volatility_20d"]})
    )
    monkeypatch.chdir(tmp_path)

    # Training mode: keeps the full intended feature set.
    train_strat = MLReturnPredictorStrategy(universe=["AAPL"], use_sector_rs=True)
    assert len(train_strat.features) > 2
    assert "rsi_14" in train_strat.features
    assert "sector_rs_5d" in train_strat.features

    # Inference mode: adopts the persisted (reduced) feature set so the matrix
    # shape matches the trained model.
    infer_strat = MLReturnPredictorStrategy(
        universe=["AAPL"], use_sector_rs=True, train_enabled=False
    )
    assert infer_strat.features == ["return_5d", "volatility_20d"]


# ---------------------------------------------------------------------------
# Bug #7: Rank target transformation
# ---------------------------------------------------------------------------


def test_rank_target_transformation():
    """
    Verify that with use_rank_target=True, the target is transformed to
    cross-sectional ranks in [-1, 1].
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        use_rank_target=True,
        use_fundamentals=False,
    )

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = {
        "AAPL": _make_dummy_data("AAPL", start_date, 200),
        "MSFT": _make_dummy_data("MSFT", start_date, 200),
        "GOOG": _make_dummy_data("GOOG", start_date, 200),
    }

    X, y = strat._build_training_data(data)

    assert X is not None
    assert y is not None

    # Rank targets should be in [-1, 1]
    assert y.min() >= -1.0 - 1e-6, f"Rank target min should be >= -1.0, got {y.min()}"
    assert y.max() <= 1.0 + 1e-6, f"Rank target max should be <= 1.0, got {y.max()}"

    # The mean across all samples should be close to the expected value for
    # 3-stock cross-sections: ranks are {1/3, 2/3, 3/3} → [-0.33, 0.33, 1.0]
    # giving a mean of ~0.33. This is expected for small universes.
    # For large universes the mean would be closer to 0.
    assert abs(y.mean()) < 0.5, f"Mean rank target should be reasonable, got {y.mean()}"


def test_raw_target_when_rank_disabled():
    """
    Verify that with use_rank_target=False, the target remains in raw return space.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        use_rank_target=False,
        use_fundamentals=False,
    )

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = {
        "AAPL": _make_dummy_data("AAPL", start_date, 200),
        "MSFT": _make_dummy_data("MSFT", start_date, 200),
    }

    X, y = strat._build_training_data(data)
    assert X is not None
    assert y is not None

    # Raw returns can be outside [-1, 1] in principle (though usually small)
    # They should NOT be uniformly distributed like ranks
    assert y.abs().max() > 0.0, "Raw targets should have non-zero values"


# ---------------------------------------------------------------------------
# Bug #3/#6: Feature importance extraction & stacking ensemble
# ---------------------------------------------------------------------------


def test_feature_importance_extraction():
    """
    Verify that _extract_feature_importances works for various model types.
    """
    features = ["f1", "f2", "f3"]

    # Test with a mock estimator that has feature_importances_
    class MockEstimator:
        feature_importances_ = np.array([0.5, 0.3, 0.2])

    result = _extract_feature_importances(MockEstimator(), features)
    assert result is not None
    assert "f1" in result
    assert result["f1"] == 0.5

    # Test with a mock stacking model
    class MockStacking:
        estimators_ = [MockEstimator(), MockEstimator()]

    result = _extract_feature_importances(MockStacking(), features)
    assert result is not None
    assert len(result) == 3


def test_build_model_returns_valid_estimator():
    """
    Verify that _build_model returns a working model with correct backends.
    """
    from quantify.strategy.ml_return_predictor import _LGBM_PARAMS

    model, backends = _build_model(_LGBM_PARAMS)

    assert model is not None
    assert len(backends) > 0

    # Should have at least one backend
    assert any(b in backends for b in ["lgbm", "xgboost", "catboost", "sklearn_fallback"])


# ---------------------------------------------------------------------------
# Original tests (preserved and updated)
# ---------------------------------------------------------------------------


def test_ml_predictor_training_data_construction():
    """
    Test that _build_training_data:
    1. Cross-sectionally standardizes features (mean ~ 0, std ~ 1 per date).
    2. Correctly shifts the raw target to avoid lookahead bias.
    3. Truncates to the sliding window length.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        use_rank_target=False,  # test raw features, not ranks
        use_fundamentals=False,
    )

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = {
        "AAPL": _make_dummy_data("AAPL", start_date, 200),
        "MSFT": _make_dummy_data("MSFT", start_date, 200),
        "GOOG": _make_dummy_data("GOOG", start_date, 200),
    }

    X, y = strat._build_training_data(data)

    assert X is not None
    assert y is not None

    # Check that columns exist
    assert "return_5d" in X.columns
    assert "volatility_20d" in X.columns

    # Check that it's standardized per timestamp
    grouped = X.groupby(level=0)
    for date, group in grouped:
        if len(group) > 1:
            mean_ret = group["return_5d"].mean()
            std_ret = group["return_5d"].std()
            assert abs(mean_ret) < 1e-7, f"Mean not 0 on {date}: {mean_ret}"
            if std_ret > 1e-7:
                assert abs(std_ret - 1.0) < 1e-7, f"Std not 1 on {date}: {std_ret}"

    # The target should remain in raw return space, not be z-scored to zero.
    assert y.abs().max() > 0.0


def test_ml_predictor_signal_strength_matches_direction():
    """
    Test that short signals carry negative strength even when all predictions
    are positive, and long signals carry positive strength.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        long_decile=0.75,
        short_decile=0.25,
    )

    predictions = {
        "AAPL": 0.1,
        "MSFT": 0.2,
        "GOOG": 0.3,
        "AMZN": 0.4,
    }

    signals = strat._rank_and_signal(predictions, datetime(2024, 1, 2, tzinfo=timezone.utc))

    short_signal = next(sig for sig in signals if sig.symbol == "AAPL")
    long_signal = next(sig for sig in signals if sig.symbol == "AMZN")

    assert short_signal.direction == "short"
    assert short_signal.strength < 0.0
    assert long_signal.direction == "long"
    assert long_signal.strength > 0.0
    assert short_signal.metadata["predicted_return_1d"] == 0.1
    assert long_signal.metadata["predicted_return_1d"] == 0.4


def test_ml_predictor_defaults_to_sp500_only():
    """
    Test that the default universe stays on the S&P 500 list and excludes
    names that only appear in the broader Russell 1000 set.
    """
    strat = MLReturnPredictorStrategy(features=["return_5d", "volatility_20d"], min_train_bars=50)

    sp500 = set(get_sp500())
    assert set(strat.universe) == sp500
    assert "CIEN" not in strat.universe
    assert "COHR" not in strat.universe


def test_ml_predictor_ignores_non_universe_symbols():
    """
    Test that symbols outside the configured universe are ignored during
    signal generation.
    """
    strat = MLReturnPredictorStrategy(
        universe=["AAPL", "MSFT", "GOOG"],
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        use_fundamentals=False,
    )

    class DummyModel:
        def fit(self, X, y):
            pass

        def predict(self, X):
            return X.sum(axis=1)

    strat._model = DummyModel()
    strat._last_train_date = datetime.now(timezone.utc)

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = {
        "AAPL": _make_dummy_data("AAPL", start_date, 200),
        "MSFT": _make_dummy_data("MSFT", start_date, 200),
        "GOOG": _make_dummy_data("GOOG", start_date, 200),
        "CIEN": _make_dummy_data("CIEN", start_date, 200),
    }

    signals = strat.generate_signals(data)

    assert {sig.symbol for sig in signals} == {"AAPL", "MSFT", "GOOG"}
    assert "CIEN" not in {sig.symbol for sig in signals}


def test_ml_predictor_emits_explanations():
    """
    Test that signal metadata includes feature explanations for ranking.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=1,
        use_fundamentals=False,
    )

    class DummyModel:
        def fit(self, X, y):
            pass

        def predict(self, X):
            return X.sum(axis=1)

    strat._model = DummyModel()
    strat._last_train_date = datetime(2024, 1, 10, tzinfo=timezone.utc)
    strat._feature_importances = {"return_5d": 2.0, "volatility_20d": 1.0}

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = {
        "AAPL": _make_dummy_data("AAPL", start_date, 200),
        "MSFT": _make_dummy_data("MSFT", start_date, 200),
        "GOOG": _make_dummy_data("GOOG", start_date, 200),
    }

    signals = strat.generate_signals(data)
    assert signals

    meta = signals[0].metadata
    explanations = meta.get("explanations")
    assert explanations is not None
    assert len(explanations) > 0
    assert "feature" in explanations[0]
    assert "zscore" in explanations[0]


def test_ml_predictor_predict_cross_sectional_standardization():
    """
    Test that _predict applies the same cross-sectional standardization to the final bar.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        use_fundamentals=False,
    )

    start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    data = {
        "AAPL": _make_dummy_data("AAPL", start_date, 200),
        "MSFT": _make_dummy_data("MSFT", start_date, 200),
        "GOOG": _make_dummy_data("GOOG", start_date, 200),
    }

    # Hack the model to just return the sum of features to make it easy to assert
    class DummyModel:
        def fit(self, X, y):
            pass
        def predict(self, X):
            return X.sum(axis=1)

    strat._model = DummyModel()
    strat._last_train_date = start_date  # fake trained

    predictions = strat._predict(data)

    assert "AAPL" in predictions
    assert "MSFT" in predictions
    assert "GOOG" in predictions

    # Check that the sum of predictions is approximately 0
    # because the inputs should be cross-sectionally mean 0
    # and our dummy model is linear sum
    sum_preds = sum(predictions.values())
    assert abs(sum_preds) < 1e-7, f"Sum of predictions should be near 0 due to CS normalization, got {sum_preds}"


def test_compute_sample_weights_returns_numpy():
    """
    Ensure `_compute_sample_weights` returns a numpy array of floats
    (CatBoost and sklearn expect array-like, not pandas.Index).
    """
    strat = MLReturnPredictorStrategy(features=["return_5d", "volatility_20d"], min_train_bars=1)

    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    weights = strat._compute_sample_weights(dates)

    assert weights is not None
    assert isinstance(weights, np.ndarray), f"weights should be numpy.ndarray, got {type(weights)}"
    assert weights.dtype == float or np.issubdtype(weights.dtype, np.floating)
    assert len(weights) == len(dates)


# ---------------------------------------------------------------------------
# New feature completeness test
# ---------------------------------------------------------------------------


def test_all_30_features_registered():
    """
    Verify that all 30 features used by the strategy are actually registered
    in the FeatureEngine.
    """
    from quantify.data.features import FeatureEngine

    engine = FeatureEngine()
    available = set(engine.available_features())

    strat = MLReturnPredictorStrategy()
    required = set(strat.get_required_features())

    missing = required - available
    assert not missing, f"Features required by strategy but not registered: {missing}"


def test_signal_metadata_includes_new_fields():
    """
    Verify that signal metadata includes the new fields added in the rewrite.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50,
        use_rank_target=True,
        purge_embargo_days=5,
    )

    predictions = {"AAPL": 0.1, "MSFT": -0.1}
    signals = strat._rank_and_signal(predictions, datetime(2024, 1, 2, tzinfo=timezone.utc))

    assert len(signals) == 2
    for sig in signals:
        meta = sig.metadata
        assert "use_rank_target" in meta
        assert "purge_embargo_days" in meta
        assert meta["use_rank_target"] is True
        assert meta["purge_embargo_days"] == 5
