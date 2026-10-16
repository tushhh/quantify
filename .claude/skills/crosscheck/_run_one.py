"""Run one parity backtest against a given source tree and write its summary as JSON.

Invoked by parity.py as:  python _run_one.py <tree>/src <data.pkl> <strategy,names> <out.json>
Only uses APIs that exist on older revisions too (BacktestEngine, strategy classes).
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import logging
import math
import pickle
import sys

STRATEGY_CLASSES = {
    "trend_following": ("quantify.strategy.trend_following", "TrendFollowingStrategy"),
    "cross_sectional_momentum": (
        "quantify.strategy.cross_sectional_momentum",
        "CrossSectionalMomentumStrategy",
    ),
    "pairs_mean_reversion": (
        "quantify.strategy.pairs_mean_reversion",
        "PairsMeanReversionStrategy",
    ),
    "quality_value": ("quantify.strategy.quality_value", "QualityValueStrategy"),
    "volatility_regime": ("quantify.strategy.volatility_regime", "VolatilityRegimeStrategy"),
    "ml_return_predictor": ("quantify.strategy.ml_return_predictor", "MLReturnPredictorStrategy"),
}


def _build(name: str, universe: list[str], pairs: list[tuple[str, str]]):
    module_name, class_name = STRATEGY_CLASSES[name]
    cls = getattr(importlib.import_module(module_name), class_name)
    wanted = {
        "universe": universe,
        "candidate_pairs": pairs,
        # ML: train walk-forward on the parity data; never touch the network.
        "train_enabled": True,
        "use_fundamentals": False,
        "use_sector_rs": False,
        "use_earnings": False,
    }
    accepted = inspect.signature(cls.__init__).parameters
    return cls(**{k: v for k, v in wanted.items() if k in accepted})


def main() -> None:
    src, data_path, names, out_path = sys.argv[1:5]
    sys.path.insert(0, src)
    logging.disable(logging.CRITICAL)

    import numpy as np

    from quantify.backtest.engine import BacktestEngine

    with open(data_path, "rb") as fh:
        payload = pickle.load(fh)
    data, universe, pairs = payload["data"], payload["universe"], payload["pairs"]

    strategies = [_build(name, universe, pairs) for name in names.split(",")]
    for strategy in strategies:
        strategy.allocation = 1.0 / len(strategies)

    engine = BacktestEngine(strategies=strategies, initial_capital=100_000.0, benchmark_symbol="SPY")
    result = engine.run({symbol: df.copy() for symbol, df in data.items()})

    equity = result.equity_curve
    returns = result.daily_returns
    std = float(returns.std()) if len(returns) > 1 else 0.0
    trades_by_strategy: dict[str, int] = {}
    for trade in result.trades:
        key = str(trade.get("strategy_name", "?"))
        trades_by_strategy[key] = trades_by_strategy.get(key, 0) + 1

    summary = {
        "final_equity": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1.0),
        "sharpe": float(returns.mean() / std * math.sqrt(252)) if std > 0 else 0.0,
        "max_drawdown": float((equity / equity.cummax() - 1.0).min()),
        "trades": len(result.trades),
        "signals": len(result.signals_log),
        "trading_days": len(equity),
        "equity_curve_sha256": hashlib.sha256(
            np.round(equity.to_numpy(dtype=float), 6).tobytes()
        ).hexdigest()[:16],
        "trades_by_strategy": trades_by_strategy,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh)


if __name__ == "__main__":
    main()
