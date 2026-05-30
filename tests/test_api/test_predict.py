from __future__ import annotations

import os

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.main import app
from api.routers import predict as predict_router


def test_force_prediction_on_web_dyno_queues_background_task(monkeypatch) -> None:
    monkeypatch.setenv("DYNO", "web.1")
    monkeypatch.delenv("PREDICTION_FORCE_SYNC", raising=False)

    queued: list[tuple[str, str]] = []

    def _fake_background_task(source: str = "scheduler", mode: str = "previous_close") -> None:
        queued.append((source, mode))

    monkeypatch.setattr(predict_router, "_run_and_cache_predictions", _fake_background_task)

    client = TestClient(app)
    response = client.get("/api/predict/best?top_n=5&force=true")

    assert response.status_code == 202
    assert response.json()["status"] == "computing"
    assert queued == [("api", "previous_close")]


def test_force_prediction_live_mode_runs_synchronously(monkeypatch) -> None:
    monkeypatch.setenv("DYNO", "web.1")
    monkeypatch.setenv("PREDICTION_FORCE_SYNC", "1")
    monkeypatch.setattr(predict_router, "_is_computing", False)

    seen_modes: list[str] = []

    def _fake_run_prediction_sync(mode: str = "previous_close"):
        seen_modes.append(mode)
        return predict_router.PredictionResponse(
            status="ok",
            mode=mode,
            date="2026-05-30",
            cached=False,
            cache_age_minutes=0.0,
            universe_size=1,
            signals=[],
        )

    monkeypatch.setattr(predict_router, "_run_prediction_sync", _fake_run_prediction_sync)

    client = TestClient(app)
    response = client.get("/api/predict/best?top_n=5&force=true&mode=live")

    assert response.status_code == 200
    assert response.json()["mode"] == "live"
    assert seen_modes == ["live"]
