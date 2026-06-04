"""
tests/test_data/test_features.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for quantify.data.features.FeatureEngine.

Covers:
- Available features are registered
- compute() returns correct shape and columns
- compute_single() convenience wrapper
- Individual feature correctness (returns, volatility, RSI range,
  MACD, Bollinger width, SMAs, volume_ratio, ATR)
- Unknown feature raises KeyError
- Empty DataFrame produces no output for that symbol
- Extra features registration on instance
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quantify.data.features import FeatureEngine, list_features


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine() -> FeatureEngine:
    return FeatureEngine()


@pytest.fixture(scope="module")
def ohlcv_300() -> pd.DataFrame:
    """300 bars of synthetic OHLCV data (enough for all features)."""
    rng = np.random.default_rng(42)
    n = 300
    close = 100.0 * np.cumprod(1 + rng.normal(0.0003, 0.012, n))
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    open_ = close * (1 + rng.uniform(-0.005, 0.005, n))
    volume = rng.integers(500_000, 5_000_000, n)
    index = pd.date_range("2021-01-04", periods=n, freq="B")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestFeatureRegistry:
    def test_list_features_nonempty(self) -> None:
        features = list_features()
        assert len(features) > 0

    def test_expected_features_registered(self) -> None:
        features = set(list_features())
        expected = {
            "return_1d", "return_5d", "return_21d", "return_63d",
            "volatility_20d", "volatility_60d",
            "rsi_14", "macd_histogram", "bollinger_width",
            "sma_50", "sma_200", "sma_crossover",
            "volume_ratio_20d", "obv_slope", "amihud_illiquidity", "atr_14",
        }
        missing = expected - features
        assert not missing, f"Expected features missing from registry: {missing}"

    def test_engine_available_features_sorted(self, engine: FeatureEngine) -> None:
        features = engine.available_features()
        assert features == sorted(features)


# ---------------------------------------------------------------------------
# compute() API tests
# ---------------------------------------------------------------------------


class TestFeatureEngineCompute:
    def test_compute_returns_all_requested_columns(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        requested = ["return_1d", "return_5d", "rsi_14", "sma_50"]
        result = engine.compute({"AAPL": ohlcv_300}, required=requested)
        assert "AAPL" in result
        df = result["AAPL"]
        for feat in requested:
            assert feat in df.columns

    def test_compute_same_index_as_input(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"AAPL": ohlcv_300}, required=["return_1d"])
        assert result["AAPL"].index.equals(ohlcv_300.index)

    def test_compute_unknown_feature_raises(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        with pytest.raises(KeyError, match="Unknown features"):
            engine.compute({"AAPL": ohlcv_300}, required=["this_does_not_exist"])

    def test_compute_empty_df_skipped(self, engine: FeatureEngine) -> None:
        result = engine.compute(
            {"EMPTY": pd.DataFrame()}, required=["return_1d"]
        )
        assert "EMPTY" not in result

    def test_compute_multi_symbol(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        data = {"AAPL": ohlcv_300, "MSFT": ohlcv_300.copy()}
        result = engine.compute(data, required=["return_1d", "sma_50"])
        assert "AAPL" in result
        assert "MSFT" in result

    def test_compute_single_wrapper(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute_single(ohlcv_300, required=["return_1d", "rsi_14"])
        assert isinstance(result, pd.DataFrame)
        assert "return_1d" in result.columns
        assert "rsi_14" in result.columns


# ---------------------------------------------------------------------------
# Individual feature correctness
# ---------------------------------------------------------------------------


class TestReturnFeatures:
    @pytest.mark.parametrize("n", [1, 5, 21, 63])
    def test_return_nd_is_pct_change(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame, n: int
    ) -> None:
        feat = f"return_{n}d"
        result = engine.compute({"X": ohlcv_300}, required=[feat])
        series = result["X"][feat]

        # First n rows should be NaN
        assert series.iloc[:n].isna().all()

        # Value should match manual pct_change
        manual = ohlcv_300["close"].pct_change(n)
        pd.testing.assert_series_equal(
            series.dropna(), manual.dropna(), check_names=False, rtol=1e-6
        )

    def test_return_1d_sign_matches_price_move(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["return_1d"])
        r = result["X"]["return_1d"]
        price_diff = ohlcv_300["close"].diff()
        # Signs must agree (ignoring NaN)
        valid = ~r.isna()
        assert (np.sign(r[valid]) == np.sign(price_diff[valid])).all()


class TestVolatilityFeatures:
    @pytest.mark.parametrize("n", [20, 60])
    def test_volatility_nd_is_positive(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame, n: int
    ) -> None:
        feat = f"volatility_{n}d"
        result = engine.compute({"X": ohlcv_300}, required=[feat])
        series = result["X"][feat].dropna()
        assert (series > 0).all(), f"{feat} has non-positive values"

    def test_volatility_20d_annualised(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        """Annualised vol should be in a reasonable range (1%–200%)."""
        result = engine.compute({"X": ohlcv_300}, required=["volatility_20d"])
        vol = result["X"]["volatility_20d"].dropna()
        assert (vol > 0.01).all()
        assert (vol < 2.0).all()


class TestRsiFeature:
    def test_rsi_range_0_to_100(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["rsi_14"])
        rsi = result["X"]["rsi_14"].dropna()
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_rsi_first_14_rows_nan(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["rsi_14"])
        rsi = result["X"]["rsi_14"]
        assert rsi.iloc[:14].isna().all()


class TestMacdFeature:
    def test_macd_histogram_varies(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["macd_histogram"])
        hist = result["X"]["macd_histogram"].dropna()
        assert not hist.empty
        # Not all the same value
        assert hist.std() > 0

    def test_macd_histogram_can_be_negative(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["macd_histogram"])
        hist = result["X"]["macd_histogram"].dropna()
        assert (hist < 0).any()


class TestBollingerWidthFeature:
    def test_bollinger_width_positive(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["bollinger_width"])
        bw = result["X"]["bollinger_width"].dropna()
        assert (bw > 0).all()


class TestSmaFeatures:
    def test_sma_50_first_49_rows_nan(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["sma_50"])
        sma = result["X"]["sma_50"]
        assert sma.iloc[:49].isna().all()
        assert not sma.iloc[49].isnan() if hasattr(sma.iloc[49], "isnan") else not np.isnan(sma.iloc[49])

    def test_sma_200_first_199_rows_nan(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["sma_200"])
        sma = result["X"]["sma_200"]
        assert sma.iloc[:199].isna().all()

    def test_sma_crossover_binary(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["sma_crossover"])
        crossover = result["X"]["sma_crossover"].dropna()
        unique_vals = set(crossover.unique())
        # Should only contain 0.0 or 1.0
        assert unique_vals <= {0.0, 1.0}


class TestVolumeRatioFeature:
    def test_volume_ratio_positive(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["volume_ratio_20d"])
        ratio = result["X"]["volume_ratio_20d"].dropna()
        assert (ratio > 0).all()


class TestAtrFeature:
    def test_atr_14_positive(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["atr_14"])
        atr = result["X"]["atr_14"].dropna()
        assert (atr > 0).all()

    def test_atr_14_less_than_price(
        self, engine: FeatureEngine, ohlcv_300: pd.DataFrame
    ) -> None:
        result = engine.compute({"X": ohlcv_300}, required=["atr_14"])
        atr = result["X"]["atr_14"].dropna()
        close = ohlcv_300["close"]
        # ATR should be less than the price (for reasonable volatility)
        common_idx = atr.index.intersection(close.index)
        assert (atr[common_idx] < close[common_idx]).all()


class TestExtraFeatureRegistration:
    def test_instance_extra_feature(self, ohlcv_300: pd.DataFrame) -> None:
        def _custom(df: pd.DataFrame) -> pd.Series:
            return df["close"].rolling(5).mean()

        engine = FeatureEngine(extra_features={"custom_sma5": _custom})
        result = engine.compute({"X": ohlcv_300}, required=["custom_sma5"])
        assert "custom_sma5" in result["X"].columns

    def test_instance_register_method(self, ohlcv_300: pd.DataFrame) -> None:
        engine = FeatureEngine()
        engine.register("my_vol", lambda df: df["close"].pct_change().rolling(10).std())
        result = engine.compute({"X": ohlcv_300}, required=["my_vol"])
        assert "my_vol" in result["X"].columns
        assert not result["X"]["my_vol"].dropna().empty
