from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.main import app
from api.routers import predict as predict_router


def test_force_prediction_on_web_dyno_queues_background_task(monkeypatch) -> None:
    monkeypatch.setenv("DYNO", "web.1")
    monkeypatch.delenv("PREDICTION_FORCE_SYNC", raising=False)

    queued: list[str] = []

    def _fake_background_task(source: str = "scheduler") -> None:
        queued.append(source)

    monkeypatch.setattr(predict_router, "_run_and_cache_predictions", _fake_background_task)

    client = TestClient(app)
    response = client.get("/api/predict/best?top_n=5&force=true")

    assert response.status_code == 202
    assert response.json()["status"] == "computing"
    assert queued == ["api"]
