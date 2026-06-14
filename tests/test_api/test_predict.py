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

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)

    client = TestClient(app)
    response = client.get("/api/predict/best?top_n=5&force=true")

    assert response.status_code == 200
    assert response.json()["date"] == "2026-06-12"


def test_predict_best_not_found(monkeypatch) -> None:
    from urllib.error import HTTPError

    def mock_urlopen(req, timeout=10):
        raise HTTPError(url=req.full_url, code=404, msg="Not Found", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    monkeypatch.setattr(predict_router, "_cache", {"live": {}, "previous_close": {}})

    client = TestClient(app)
    response = client.get("/api/predict/best?top_n=5&force=true")

    assert response.status_code == 503
