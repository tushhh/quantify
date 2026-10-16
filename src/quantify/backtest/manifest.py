from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from importlib import metadata as importlib_metadata
from typing import Any, Iterable

from quantify import __version__ as quantify_version
from quantify.backtest.costs import CostModel
from quantify.strategy.base import Strategy


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_hex(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _pkg_versions(names: Iterable[str]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _git_revision() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = proc.stdout.strip()
        return value or None
    except Exception:
        return None


@dataclass(frozen=True)
class BacktestRunManifest:
    run_id: str
    manifest_hash: str
    generated_at: str
    strategy: dict[str, Any]
    period: dict[str, Any]
    universe: dict[str, Any]
    data_provider: dict[str, Any]
    execution_costs: dict[str, Any]
    model: dict[str, Any]
    environment: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "manifest_hash": self.manifest_hash,
            "generated_at": self.generated_at,
            "strategy": self.strategy,
            "period": self.period,
            "universe": self.universe,
            "data_provider": self.data_provider,
            "execution_costs": self.execution_costs,
            "model": self.model,
            "environment": self.environment,
        }


def _strategy_signature(strategies: list[Strategy]) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for strategy in strategies:
        snapshot.append(
            {
                "name": strategy.name,
                "class": f"{strategy.__class__.__module__}.{strategy.__class__.__name__}",
                "version": getattr(strategy, "version", "unknown"),
                "allocation": float(getattr(strategy, "allocation", 0.0) or 0.0),
                "lookback_days": int(getattr(strategy, "lookback_days", 0) or 0),
                "rebalance_frequency": getattr(strategy, "rebalance_frequency", "unknown"),
            }
        )
    return sorted(snapshot, key=lambda item: item["name"])


def _model_signature(strategies: list[Strategy]) -> dict[str, Any]:
    ml = next((s for s in strategies if s.name == "ml_return_predictor"), None)
    if ml is None:
        return {"used": False}

    return {
        "used": True,
        "strategy": ml.name,
        "train_enabled": bool(getattr(ml, "train_enabled", True)),
        "model_path": getattr(ml, "_model_path", None),
        "model_metadata_path": getattr(ml, "_model_meta_path", None),
    }


def build_backtest_manifest(
    *,
    strategies: list[Strategy],
    start_date: date | None,
    end_date: date | None,
    symbols: list[str],
    symbol_rows: dict[str, int],
    cost_model: CostModel,
    data_provider: dict[str, Any],
) -> BacktestRunManifest:
    strategy = {
        "count": len(strategies),
        "items": _strategy_signature(strategies),
    }
    period = {
        "start": str(start_date) if start_date else None,
        "end": str(end_date) if end_date else None,
    }
    universe = {
        "symbols": sorted(symbols),
        "count": len(symbols),
        "rows_per_symbol": {k: int(symbol_rows[k]) for k in sorted(symbol_rows)},
    }
    execution_costs = {
        "commission_per_share": cost_model.commission_per_share,
        "min_commission": cost_model.min_commission,
        "spread_bps": cost_model.spread_bps,
        "market_impact_bps": cost_model.market_impact_bps,
        "slippage_pct": cost_model.slippage_pct,
    }
    model = _model_signature(strategies)
    environment = {
        "quantify_version": quantify_version,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "git_revision": _git_revision(),
        "package_versions": _pkg_versions(
            [
                "pandas",
                "numpy",
                "yfinance",
                "scikit-learn",
                "lightgbm",
                "xgboost",
                "catboost",
            ]
        ),
    }

    hash_payload = {
        "strategy": strategy,
        "period": period,
        "universe": universe,
        "data_provider": data_provider,
        "execution_costs": execution_costs,
        "model": model,
        "environment": environment,
    }
    digest = _hash_hex(hash_payload)
    run_id = f"bt-{digest[:12]}"

    return BacktestRunManifest(
        run_id=run_id,
        manifest_hash=f"sha256:{digest}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        strategy=strategy,
        period=period,
        universe=universe,
        data_provider=data_provider,
        execution_costs=execution_costs,
        model=model,
        environment=environment,
    )
