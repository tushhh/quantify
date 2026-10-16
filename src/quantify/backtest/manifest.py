"""
Deterministic run manifest for a backtest.

The manifest records everything that determines a backtest's result — engine
configuration, strategy parameters, the input data, persisted ML model files,
the code revision and library versions — and hashes it into a ``run_id``.
Two runs share a ``run_id`` only when all of those inputs match.

Build it *before* :meth:`BacktestEngine.run`, so stateful components (risk
manager, stops) are captured as configured rather than as left by the run.

Usage
-----
>>> manifest = build_backtest_manifest(engine, data)
>>> result = engine.run(data)
>>> manifest["run_id"]
'bt-3f9c2a17b04e'
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from quantify import __version__ as quantify_version

if TYPE_CHECKING:
    from quantify.backtest.engine import BacktestEngine

_TRACKED_PACKAGES = (
    "pandas",
    "numpy",
    "yfinance",
    "scikit-learn",
    "lightgbm",
    "xgboost",
    "catboost",
)

# Environment variables that carry the deployed commit when there is no .git
# directory (GitHub Actions, Heroku dyno metadata, Heroku build).
_REVISION_ENV_VARS = ("GITHUB_SHA", "HEROKU_SLUG_COMMIT", "SOURCE_VERSION")


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_hex(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=1)
def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in _TRACKED_PACKAGES:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = None
    return versions


@functools.lru_cache(maxsize=1)
def _git_revision() -> str | None:
    for var in _REVISION_ENV_VARS:
        value = os.getenv(var, "").strip()
        if value:
            return value
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,  # this repo, not the caller's cwd
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    return proc.stdout.strip() or None


def _is_plain(value: Any) -> bool:
    """True for JSON-friendly values: scalars and lists/dicts made of them."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_plain(v) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _is_plain(v) for k, v in value.items())
    return False


def _component(obj: Any) -> dict[str, Any] | None:
    """Class path plus the public, JSON-friendly attributes of a configured object."""
    if obj is None:
        return None
    params = {
        key: value
        for key, value in sorted(getattr(obj, "__dict__", {}).items())
        if not key.startswith("_") and _is_plain(value)
    }
    cls = type(obj)
    return {"class": f"{cls.__module__}.{cls.__qualname__}", "params": params}


def _strategy_component(strategy: Any) -> dict[str, Any]:
    component = _component(strategy) or {"class": None, "params": {}}
    # Base-class settings are often class attributes, which __dict__ omits.
    for attr in ("name", "lookback_days", "rebalance_frequency", "allocation"):
        component["params"].setdefault(attr, getattr(strategy, attr, None))
    return component


def _file_sha256(path: str) -> str | None:
    if not Path(path).is_file():
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _model_fingerprints(strategies: list[Any]) -> list[dict[str, Any]]:
    """Content hashes of persisted model files that strategies load at runtime."""
    models = []
    for strategy in strategies:
        model_path = getattr(strategy, "_model_path", None)
        if not model_path:
            continue
        meta_path = getattr(strategy, "_model_meta_path", None)
        models.append(
            {
                "strategy": getattr(strategy, "name", type(strategy).__name__),
                "model_path": model_path,
                "model_sha256": _file_sha256(model_path),
                "meta_sha256": _file_sha256(meta_path) if meta_path else None,
            }
        )
    return sorted(models, key=lambda m: m["strategy"])


def _frame_fingerprint(df: pd.DataFrame) -> dict[str, Any]:
    numeric = df.select_dtypes("number")
    digest = hashlib.sha256(_canonical_json(list(map(str, numeric.columns))).encode("utf-8"))
    digest.update(pd.util.hash_pandas_object(numeric, index=True).to_numpy().tobytes())
    return {
        "rows": len(df),
        "first": str(df.index.min()) if len(df) else None,
        "last": str(df.index.max()) if len(df) else None,
        "sha256": digest.hexdigest()[:16],
    }


def build_backtest_manifest(
    engine: BacktestEngine,
    data: dict[str, pd.DataFrame],
    *,
    data_provider: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the run manifest (a JSON-serialisable dict) for *engine* on *data*.

    ``data_provider`` is recorded as provenance (provider name, skipped
    symbols) but is not hashed: the data fingerprint already captures what
    the provider returned.
    """
    fingerprint = {
        "config": {
            "initial_capital": float(engine.initial_capital),
            "start_date": str(engine.start_date) if engine.start_date else None,
            "end_date": str(engine.end_date) if engine.end_date else None,
            "benchmark_symbol": engine.benchmark_symbol,
            "strategies": sorted(
                (_strategy_component(s) for s in engine.strategies),
                key=lambda c: str(c["params"].get("name")),
            ),
            "cost_model": _component(engine.cost_model),
            "position_sizer": _component(engine.position_sizer),
            "risk_manager": _component(engine.risk_manager),
            "stop_manager": _component(engine.stop_manager),
        },
        "data": {symbol: _frame_fingerprint(df) for symbol, df in sorted(data.items())},
        "models": _model_fingerprints(engine.strategies),
        "code": {"quantify_version": quantify_version, "git_revision": _git_revision()},
        "libraries": {"python": platform.python_version(), **_package_versions()},
    }
    digest = _hash_hex(fingerprint)

    return {
        "run_id": f"bt-{digest[:12]}",
        "manifest_hash": f"sha256:{digest}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **fingerprint,
        "provenance": {"platform": platform.platform(), "data_provider": data_provider},
    }
