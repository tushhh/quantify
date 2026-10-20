# Regression: a Telegram or database failure during startup aborted the FastAPI
# lifespan, so gunicorn couldn't boot a worker and every route returned 503.
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from telegram.error import InvalidToken

os.environ.setdefault("JWT_SECRET", "test-secret")

import api.main as main  # noqa: E402
import api.prediction_bot as prediction_bot  # noqa: E402
import api.telegram_bot as telegram_bot  # noqa: E402

BOTS = (
    (telegram_bot, "start_telegram_bot", "stop_telegram_bot"),
    (prediction_bot, "start_prediction_bot", "stop_prediction_bot"),
)


class _NoopScheduler:
    running = False

    def add_job(self, *args, **kwargs) -> None:
        pass

    def start(self) -> None:
        pass


async def _ok() -> None:
    return None


@pytest.fixture
def hermetic_startup(monkeypatch):
    """Run the real lifespan with the database, scheduler and bots stubbed out."""
    monkeypatch.setattr(main.models.Base.metadata, "create_all", lambda **kwargs: None)
    for helper in ("ensure_trade_columns", "ensure_user_columns", "ensure_gain_alert_columns"):
        monkeypatch.setattr(main, helper, lambda: None)
    monkeypatch.setattr(main, "AsyncIOScheduler", _NoopScheduler)
    for module, start, stop in BOTS:
        monkeypatch.setattr(module, start, _ok)
        monkeypatch.setattr(module, stop, _ok)
    return monkeypatch


def test_api_serves_when_the_telegram_bots_fail(hermetic_startup) -> None:
    async def revoked_token() -> None:
        raise InvalidToken("The token was rejected by the server.")

    async def updater_not_running() -> None:
        raise RuntimeError("This Updater is not running!")

    for module, start, stop in BOTS:
        hermetic_startup.setattr(module, start, revoked_token)
        hermetic_startup.setattr(module, stop, updater_not_running)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200


def test_api_serves_when_the_database_is_down(hermetic_startup) -> None:
    def database_down(**kwargs) -> None:
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server"))

    hermetic_startup.setattr(main.models.Base.metadata, "create_all", database_down)

    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
