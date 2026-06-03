from __future__ import annotations

import os
import uuid

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/quantify.db")

from api.main import app
from api.routers import auth as auth_router
from api.routers import trades as trades_router


def _get_token(client: TestClient, username: str, password: str) -> str:
    register = client.post(
        "/api/auth/register",
        json={"username": username, "password": password, "telegram_username": None},
    )
    if register.status_code not in (200, 400):
        raise AssertionError(f"Unexpected register status: {register.status_code}")

    login = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_update_trade_dip_threshold(monkeypatch) -> None:
    monkeypatch.setattr(trades_router.utils_router, "_is_us_equity", lambda sym: (True, "TEST"))
    monkeypatch.setattr(auth_router.pwd_context, "hash", lambda pw: f"hashed-{pw}")
    monkeypatch.setattr(auth_router.pwd_context, "verify", lambda pw, hashed: True)

    with TestClient(app) as client:
        username = f"trader_{uuid.uuid4().hex[:8]}"
        token = _get_token(client, username, "pass1234")
        headers = {"Authorization": f"Bearer {token}"}

        trade_payload = {
            "symbol": "AAPL",
            "shares": 5.0,
            "buy_price": 150.0,
            "hold_unit": "days",
            "hold_value": 10,
        }
        create_res = client.post("/api/trades", json=trade_payload, headers=headers)
        assert create_res.status_code == 200
        trade_id = create_res.json()["id"]

        update_res = client.patch(
            f"/api/trades/{trade_id}/dip-threshold",
            json={"dip_threshold_pct": 0.12},
            headers=headers,
        )
        assert update_res.status_code == 200
        assert update_res.json()["dip_threshold_pct"] == 0.12

        disable_res = client.patch(
            f"/api/trades/{trade_id}/dip-threshold",
            json={"dip_threshold_pct": 0},
            headers=headers,
        )
        assert disable_res.status_code == 200
        assert disable_res.json()["dip_threshold_pct"] is None
