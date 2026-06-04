from __future__ import annotations

import types

import os

from fastapi.testclient import TestClient

# Ensure required env is set before importing the app
os.environ.setdefault("JWT_SECRET", "test-secret")

from api.main import app


class _DummyTicker:
    def __init__(self, info):
        self.info = info


class _DummyYF:
    def __init__(self, info):
        self._info = info

    def Ticker(self, symbol: str):
        return _DummyTicker(self._info)


def _install_yfinance(monkeypatch, info):
    dummy = types.SimpleNamespace(Ticker=_DummyYF(info).Ticker)
    monkeypatch.setitem(__import__("sys").modules, "yfinance", dummy)


def test_validate_symbol_us_equity(monkeypatch):
    _install_yfinance(monkeypatch, {"country": "United States", "exchange": "NASDAQ", "quoteType": "EQUITY"})
    client = TestClient(app)
    res = client.get("/api/utils/validate_symbol?symbol=AMD")
    assert res.status_code == 200
    payload = res.json()
    assert payload["valid"] is True
    assert payload["exchange"]


def test_validate_symbol_non_us(monkeypatch):
    _install_yfinance(monkeypatch, {"country": "Canada", "exchange": "TSX", "quoteType": "EQUITY"})
    client = TestClient(app)
    res = client.get("/api/utils/validate_symbol?symbol=SHOP")
    assert res.status_code == 200
    payload = res.json()
    assert payload["valid"] is False
    assert payload["reason"] in {"not_us_equity", "lookup_failed"}


def test_validate_symbol_missing(monkeypatch):
    _install_yfinance(monkeypatch, {})
    client = TestClient(app)
    res = client.get("/api/utils/validate_symbol?symbol=")
    assert res.status_code == 400