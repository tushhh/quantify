from __future__ import annotations

from dataclasses import dataclass

from quantify.backtest.costs import CostModel
from quantify.backtest.manifest import build_backtest_manifest
from quantify.strategy.base import Strategy


@dataclass
class _StubStrategy(Strategy):
    name: str = "stub"
    universe: list[str] = None  # type: ignore[assignment]
    lookback_days: int = 20
    rebalance_frequency: str = "daily"
    allocation: float = 0.5

    def __post_init__(self):
        if self.universe is None:
            self.universe = ["AAPL"]

    def generate_signals(self, data):
        return []

    def get_required_features(self):
        return []


def _build(cost: CostModel) -> dict:
    manifest = build_backtest_manifest(
        strategies=[_StubStrategy()],
        start_date=None,
        end_date=None,
        symbols=["AAPL"],
        symbol_rows={"AAPL": 100},
        cost_model=cost,
        data_provider={"name": "YFinanceProvider", "metadata": {"provider": "YFinanceProvider"}},
    )
    return manifest.to_dict()


def test_manifest_run_id_deterministic_for_same_inputs() -> None:
    first = _build(CostModel())
    second = _build(CostModel())

    assert first["run_id"] == second["run_id"]
    assert first["manifest_hash"] == second["manifest_hash"]


def test_manifest_changes_when_cost_assumptions_change() -> None:
    first = _build(CostModel(spread_bps=5.0))
    second = _build(CostModel(spread_bps=25.0))

    assert first["run_id"] != second["run_id"]
    assert first["manifest_hash"] != second["manifest_hash"]
