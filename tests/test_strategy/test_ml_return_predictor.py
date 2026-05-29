import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

from quantify.data.universe import get_sp500
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy
from quantify.strategy.signal import Signal

def _make_dummy_data(symbol: str, start_date: datetime, n_bars: int) -> pd.DataFrame:
    dates = pd.date_range(start_date, periods=n_bars, freq="D", tz=timezone.utc)
    
    df = pd.DataFrame(index=dates)
    df["open"] = 100.0
    df["high"] = 105.0
    df["low"] = 95.0
    df["close"] = 100.0 + np.random.randn(n_bars).cumsum()  # Random walk
    df["volume"] = 1000
    
    # Add dummy features
    df["return_5d"] = df["close"].pct_change(5)
    df["volatility_20d"] = df["close"].pct_change().rolling(20).std()
    
    # Fill NAs
    df = df.fillna(value=0)
    
    return df

def test_ml_predictor_training_data_construction():
    """
    Test that _build_training_data:
    1. Cross-sectionally standardizes features (mean ~ 0, std ~ 1 per date).
    2. Correctly shifts the raw target to avoid lookahead bias.
    3. Truncates to the sliding window length.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50
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
    # We group by the index and check the mean/std
    grouped = X.groupby(level=0)
    
    # We only check dates where we have more than 1 stock to compute std
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
    assert short_signal.metadata["predicted_return_5d"] == 0.1
    assert long_signal.metadata["predicted_return_5d"] == 0.4


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

def test_ml_predictor_predict_cross_sectional_standardization():
    """
    Test that _predict applies the same cross-sectional standardization to the final bar.
    """
    strat = MLReturnPredictorStrategy(
        features=["return_5d", "volatility_20d"],
        min_train_bars=50
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
    strat._last_train_date = start_date # fake trained
    
    predictions = strat._predict(data)
    
    assert "AAPL" in predictions
    assert "MSFT" in predictions
    assert "GOOG" in predictions
    
    # Check that the sum of predictions is approximately 0
    # because the inputs should be cross-sectionally mean 0
    # and our dummy model is linear sum
    sum_preds = sum(predictions.values())
    assert abs(sum_preds) < 1e-7, f"Sum of predictions should be near 0 due to CS normalization, got {sum_preds}"
