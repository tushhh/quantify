from __future__ import annotations

import os
from datetime import date

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.main import app
from api.routers import backtest as backtest_router
from api.schemas import BacktestRequest, StrategyConfig


_STRATEGY_NAMES = [
    "trend_following",
    "cross_sectional_momentum",
    "pairs_mean_reversion",
    "quality_value",
    "ml_return_predictor",
    "volatility_regime",
]


def _strategy_configs(allocation: float = 0.30) -> dict[str, StrategyConfig]:
    configs: dict[str, StrategyConfig] = {}
    for name in _STRATEGY_NAMES:
        if name == "trend_following":
            configs[name] = StrategyConfig(
                enabled=True,
                allocation=allocation,
                params={"universe": ["AAPL"]},
            )
        else:
            configs[name] = StrategyConfig(enabled=False, allocation=0.0, params={})
    return configs


def _strategy_payload(allocation: float = 0.30) -> dict[str, dict]:
    payload: dict[str, dict] = {}
    for name in _STRATEGY_NAMES:
        if name == "trend_following":
            payload[name] = {
                "enabled": True,
                "allocation": allocation,
                "params": {"universe": ["AAPL"]},
            }
        else:
            payload[name] = {
                "enabled": False,
                "allocation": 0.0,
                "params": {},
            }
    return payload


def test_build_strategy_instances_sets_allocation() -> None:
    req = BacktestRequest(
        start_date=date(2022, 1, 3),
        end_date=date(2023, 12, 29),
        strategies=_strategy_configs(allocation=0.35),
    )
    strategies = backtest_router._build_strategy_instances(req)
    assert len(strategies) == 1
    assert strategies[0].name == "trend_following"
    assert strategies[0].allocation == pytest.approx(0.35)


def test_backtest_endpoint_instantiates_strategies(monkeypatch, long_ohlcv_data) -> None:
    def _fake_fetch_data(tickers, start, end):
        data = {
            "AAPL": long_ohlcv_data.copy(),
            "SPY": long_ohlcv_data.copy(),
        }
        return {k: v for k, v in data.items() if k in tickers}

    monkeypatch.setattr(backtest_router, "_fetch_data", _fake_fetch_data)

    start_date = long_ohlcv_data.index[0].date()
    end_date = long_ohlcv_data.index[-1].date()

    payload = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "initial_capital": 100000.0,
        "benchmark": "SPY",
        "universe": ["AAPL", "SPY"],
        "strategies": _strategy_payload(allocation=0.25),
    }

    client = TestClient(app)
    res = client.post("/api/backtest?run_sync=true", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert "trend_following" in body["metadata"]["strategies_run"]


def test_backtest_endpoint_async(monkeypatch, long_ohlcv_data) -> None:
    def _fake_fetch_data(tickers, start, end):
        data = {
            "AAPL": long_ohlcv_data.copy(),
            "SPY": long_ohlcv_data.copy(),
        }
        return {k: v for k, v in data.items() if k in tickers}

    monkeypatch.setattr(backtest_router, "_fetch_data", _fake_fetch_data)

    start_date = long_ohlcv_data.index[0].date()
    end_date = long_ohlcv_data.index[-1].date()

    payload = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "initial_capital": 100000.0,
        "benchmark": "SPY",
        "universe": ["AAPL", "SPY"],
        "strategies": _strategy_payload(allocation=0.25),
    }

    client = TestClient(app)
    # 1. Submit async job
    res = client.post("/api/backtest?job_id=test_job_123", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "running"
    assert body["job_id"] == "test_job_123"

    # 2. Poll for results (since it runs in background task thread, it will complete very quickly on mock data)
    import time
    for _ in range(10):
        res = client.get("/api/backtest/result/test_job_123")
        assert res.status_code == 200
        body = res.json()
        if body.get("status") == "running":
            time.sleep(0.5)
            continue
        break

    assert body["status"] == "ok"
    assert "trend_following" in body["metadata"]["strategies_run"]

