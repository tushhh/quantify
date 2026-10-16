from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.main import app
from api.routers import internal

_GAIN_STATE_PATHS = [
    "/api/internal/gain-scan-status",
    "/api/internal/clear-gain-state-today",
]


class _FakeQuery:
    def filter(self, *args):
        return self

    def all(self):
        return []

    def delete(self):
        return 0


class _FakeSession:
    def query(self, *args):
        return _FakeQuery()

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(internal, "_INTERNAL_SECRET", "s3cret")
    monkeypatch.setattr(internal, "SessionLocal", _FakeSession)
    return TestClient(app)


@pytest.mark.parametrize("path", _GAIN_STATE_PATHS)
def test_gain_state_endpoints_reject_missing_or_wrong_secret(client, path) -> None:
    # Regression: these GETs were unauthenticated, exposing subscriber chat
    # IDs and letting anyone reset alert dedup (re-sending every alert).
    assert client.get(path).status_code == 403
    assert client.get(path, headers={"X-Internal-Secret": "wrong"}).status_code == 403
    assert client.get(path, params={"secret": "wrong"}).status_code == 403


@pytest.mark.parametrize("path", _GAIN_STATE_PATHS)
def test_gain_state_endpoints_accept_secret_as_header_or_query(client, path) -> None:
    assert client.get(path, headers={"X-Internal-Secret": "s3cret"}).status_code == 200
    assert client.get(path, params={"secret": "s3cret"}).status_code == 200


def test_callback_endpoints_reject_wrong_secret(client) -> None:
    res = client.post(
        "/api/internal/backtest-complete",
        json={"job_id": "j1", "status": "failed"},
        headers={"X-Internal-Secret": "wrong"},
    )
    assert res.status_code == 403


def test_verify_secret_allows_all_when_secret_unset(monkeypatch) -> None:
    # Deliberate: deployments without INTERNAL_API_SECRET keep working (a
    # warning is logged at startup) rather than breaking every callback.
    monkeypatch.setattr(internal, "_INTERNAL_SECRET", "")
    internal._verify_secret(None)
