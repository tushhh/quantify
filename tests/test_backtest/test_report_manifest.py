from __future__ import annotations

import json

import pandas as pd

from quantify.backtest.engine import BacktestResult
from quantify.backtest.report import BacktestReport


def test_report_save_writes_manifest_json(tmp_path) -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    equity = pd.Series([100000.0, 101000.0, 102000.0], index=idx)
    result = BacktestResult(
        equity_curve=equity,
        trades=[],
        daily_returns=equity.pct_change().dropna(),
        signals_log=[],
        portfolio_snapshots=[],
        fills=[],
        metadata={
            "start": idx[0].date(),
            "end": idx[-1].date(),
            "initial_capital": 100000.0,
            "strategies": ["demo"],
            "symbols": ["AAPL"],
            "n_trading_days": 3,
            "run_id": "bt-abc",
            "manifest_hash": "sha256:abc",
            "data_provider": {"name": "YFinanceProvider"},
            "execution_costs": {"spread_bps": 5.0},
            "run_manifest": {"run_id": "bt-abc", "manifest_hash": "sha256:abc"},
        },
    )

    report = BacktestReport(result)
    out_dir = report.save(str(tmp_path))

    manifest_path = out_dir / "manifest.json"
    assert manifest_path.exists()
    saved = json.loads(manifest_path.read_text())
    assert saved["run_id"] == "bt-abc"
