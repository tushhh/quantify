from __future__ import annotations

import os
import json
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.main import app
from api.routers import predict as predict_router


def test_predict_best_success(monkeypatch) -> None:
    mock_data = {
        "status": "ok",
        "mode": "previous_close",
        "date": "2026-06-12",
        "cached": True,
        "cache_age_minutes": 5,
        "universe_size": 500,
        "signals": [],
    }

    class MockResponse:
        def read(self):
            return json.dumps(mock_data).encode("utf-8")
            
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=10):
        return MockResponse()

    # The screener cache URL is built from GITHUB_REPOSITORY, which only CI sets.
    monkeypatch.setenv("GITHUB_REPOSITORY", "tushhh/quantify")
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    client = TestClient(app)
    response = client.get("/api/predict/best?top_n=5&force=true")

    assert response.status_code == 200
    assert response.json()["date"] == "2026-06-12"


def test_predict_best_not_found(monkeypatch) -> None:
    from urllib.error import HTTPError

    def mock_urlopen(req, timeout=10):
        raise HTTPError(url=req.full_url, code=404, msg="Not Found", hdrs=None, fp=None)

    monkeypatch.setenv("GITHUB_REPOSITORY", "tushhh/quantify")
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    monkeypatch.setattr(predict_router, "_cache", {"live": {}, "previous_close": {}})

    client = TestClient(app)
    response = client.get("/api/predict/best?top_n=5&force=true")

    assert response.status_code == 503


# Regression: the API rebuilt picks from a fixed field list, so trend-screen fields (method,
# list date, backtest, forecasts, company names) never reached the page, which fell back to
# its ML layout and showed "Rank score 4.10" and "SNDK SNDK".
def test_predict_best_passes_trend_fields_through(monkeypatch) -> None:
    from quantify.trend_screen import BACKTEST

    trend_file = {
        "status": "ok", "mode": "previous_close", "method": "trend", "date": "2026-10-23",
        "as_of": "2026-09-30", "next_refresh": "2026-11-01", "universe_size": 100,
        "backtest": BACKTEST, "forecast_horizon": "1 month", "model_metrics": None,
        "signals": [{"symbol": "SNDK", "name": "Sandisk", "side": "long", "strength": 1.0, "sector": "Information Technology",
                     "predicted_return_pct": 4.1, "forecast_beat_spy_pct": 54.5, "forecast_low_pct": -12.5,
                     "forecast_high_pct": 22.6, "forecast_median_pct": 1.8, "return_6m_pct": 173.8,
                     "return_12m_pct": 1432.9, "pct_above_ma200": 53.9, "explanations": []}],
    }

    class MockResponse:
        def read(self):
            return json.dumps(trend_file).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    monkeypatch.setenv("GITHUB_REPOSITORY", "tushhh/quantify")
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=10: MockResponse())
    monkeypatch.setattr(predict_router, "_cache", {"live": {}, "previous_close": {}})

    body = TestClient(app).get("/api/predict/best?top_n=5&force=true").json()

    assert body["method"] == "trend" and body["as_of"] == "2026-09-30" and body["next_refresh"] == "2026-11-01"
    assert body["backtest"]["excess_cagr_pct"] == BACKTEST["excess_cagr_pct"]
    pick = body["signals"][0]
    assert pick["name"] == "Sandisk"
    assert pick["forecast_beat_spy_pct"] == 54.5 and pick["return_6m_pct"] == 173.8
