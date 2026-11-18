from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.main import app
from api.routers.strategies import STRATEGIES, TEST_RESULTS

REPO = Path(__file__).resolve().parents[2]
VERDICTS = {"did_not_beat_spy", "lost_money", "not_trustworthy", "not_testable"}


def test_every_strategy_carries_its_test_result():
    """No strategy may reach the UI without saying how it did when tested."""
    names = {s.name for s in STRATEGIES}
    assert set(TEST_RESULTS) == names

    body = TestClient(app).get("/api/strategies").json()
    assert {s["name"] for s in body} == names
    for s in body:
        result = s["test_result"]
        assert result is not None, s["name"]
        assert result["verdict"] in VERDICTS
        assert result["label"] and result["summary"]


def test_single_strategy_endpoint_includes_test_result():
    body = TestClient(app).get("/api/strategies/pairs_mean_reversion").json()
    assert body["test_result"]["verdict"] == "lost_money"


def test_test_result_sources_exist_in_repo():
    for name, result in TEST_RESULTS.items():
        assert (REPO / result.source).is_file(), f"{name}: missing {result.source}"
