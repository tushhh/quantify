from __future__ import annotations

import json

import pytest

from quantify.backtest.costs import CostModel
from quantify.backtest.engine import BacktestEngine
from quantify.backtest.manifest import build_backtest_manifest
from quantify.risk.position_sizer import EqualWeightSizer
from quantify.strategy.base import Strategy


class _StubStrategy(Strategy):
    name = "stub"
    lookback_days = 20

    def __init__(self, threshold: float = 0.5, model_path: str | None = None):
        self.universe = ["AAPL"]
        self.threshold = threshold
        if model_path:
            self._model_path = model_path

    def generate_signals(self, data):
        return []

    def get_required_features(self):
        return []


@pytest.fixture
def data(sample_ohlcv_data):
    return {"AAPL": sample_ohlcv_data.copy(), "SPY": sample_ohlcv_data.copy()}


def _run_id(data, **engine_kwargs) -> str:
    engine_kwargs.setdefault("strategies", [_StubStrategy()])
    return build_backtest_manifest(BacktestEngine(**engine_kwargs), data)["run_id"]


def test_same_inputs_give_same_run_id(data) -> None:
    first = build_backtest_manifest(BacktestEngine(strategies=[_StubStrategy()]), data)
    copied = {symbol: df.copy() for symbol, df in data.items()}
    second = build_backtest_manifest(BacktestEngine(strategies=[_StubStrategy()]), copied)

    assert first["run_id"].startswith("bt-")
    assert first["run_id"] == second["run_id"]
    assert first["manifest_hash"] == second["manifest_hash"]


@pytest.mark.parametrize(
    "engine_kwargs",
    [
        {"initial_capital": 1_000_000.0},
        {"strategies": [_StubStrategy(threshold=0.9)]},
        {"position_sizer": EqualWeightSizer(max_position_pct=0.5)},
        {"cost_model": CostModel(spread_bps=25.0)},
        {"benchmark_symbol": "QQQ"},
    ],
    ids=["capital", "strategy-param", "position-sizer", "cost-model", "benchmark"],
)
def test_config_changes_change_run_id(data, engine_kwargs) -> None:
    # Regression: the first manifest ignored capital, sizing and strategy
    # params, so runs with different results shared one run_id.
    assert _run_id(data, **engine_kwargs) != _run_id(data)


def test_price_change_changes_run_id(data) -> None:
    edited = {symbol: df.copy() for symbol, df in data.items()}
    close = edited["AAPL"].columns.get_loc("close")
    edited["AAPL"].iloc[-1, close] += 0.01

    assert _run_id(edited) != _run_id(data)


def test_model_file_contents_change_run_id(data, tmp_path) -> None:
    model = tmp_path / "model.joblib"
    model.write_bytes(b"model-v1")
    first = _run_id(data, strategies=[_StubStrategy(model_path=str(model))])
    model.write_bytes(b"model-v2")
    second = _run_id(data, strategies=[_StubStrategy(model_path=str(model))])

    assert first != second


def test_provider_details_and_timestamp_do_not_change_run_id(data) -> None:
    engine = BacktestEngine(strategies=[_StubStrategy()])
    first = build_backtest_manifest(engine, data, data_provider={"failed_symbols": {"X": "e1"}})
    second = build_backtest_manifest(engine, data, data_provider={"failed_symbols": {"X": "e2"}})

    assert first["run_id"] == second["run_id"]
    assert first["provenance"]["data_provider"] == {"failed_symbols": {"X": "e1"}}


def test_manifest_is_json_serialisable(data) -> None:
    manifest = build_backtest_manifest(BacktestEngine(strategies=[_StubStrategy()]), data)

    assert json.loads(json.dumps(manifest))["run_id"] == manifest["run_id"]


def test_builtin_strategies_fingerprint_deterministically(data) -> None:
    # Guards against a strategy exposing a time- or memory-dependent public
    # attribute, which would give every run a different run_id.
    from quantify.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy
    from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy
    from quantify.strategy.pairs_mean_reversion import PairsMeanReversionStrategy
    from quantify.strategy.quality_value import QualityValueStrategy
    from quantify.strategy.trend_following import TrendFollowingStrategy
    from quantify.strategy.volatility_regime import VolatilityRegimeStrategy

    classes = [
        CrossSectionalMomentumStrategy,
        MLReturnPredictorStrategy,
        PairsMeanReversionStrategy,
        QualityValueStrategy,
        TrendFollowingStrategy,
        VolatilityRegimeStrategy,
    ]

    def run_id() -> str:
        return _run_id(data, strategies=[cls() for cls in classes])

    assert run_id() == run_id()
