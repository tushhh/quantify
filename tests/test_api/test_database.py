# Regression: SQLAlchemy 2.1 maps a bare postgresql:// URL to psycopg v3, which
# isn't installed, so importing api.database crashed every Heroku boot (503s).
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

DATABASE_PY = Path(__file__).resolve().parents[2] / "api" / "database.py"


def _load_fresh_database_module(monkeypatch, url: str):
    """Execute api/database.py under a throwaway name so the real engine is untouched."""
    monkeypatch.setenv("DATABASE_URL", url)
    spec = importlib.util.spec_from_file_location("_database_under_test", DATABASE_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "postgres://user:pw@db.example.com:5432/quantify",  # what Heroku sets
        "postgresql://user:pw@db.example.com:5432/quantify",  # Render / Supabase style
    ],
)
def test_postgres_urls_use_the_installed_psycopg2_driver(monkeypatch, url) -> None:
    module = _load_fresh_database_module(monkeypatch, url)

    assert module.engine.dialect.name == "postgresql"
    assert module.engine.dialect.driver == "psycopg2"


def test_explicit_driver_in_url_is_respected(monkeypatch) -> None:
    module = _load_fresh_database_module(
        monkeypatch, "postgresql+psycopg2://user:pw@db.example.com:5432/quantify"
    )

    assert module.engine.dialect.driver == "psycopg2"
