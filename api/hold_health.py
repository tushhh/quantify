"""Hold health evaluation for long/short duration monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Iterable

import math
import numpy as np
import pandas as pd

from quantify.data.features import FeatureEngine
from quantify.data.providers.yfinance_provider import YFinanceProvider

_HOLD_FEATURES: list[str] = [
    "return_21d",
    "return_63d",
    "return_126d",
    "return_252d",
    "sma_crossover",
    "rsi_14",
    "macd_histogram",
    "volatility_60d",
]


@dataclass(frozen=True)
class HoldHealthResult:
    symbol: str
    strength: float
    reasons: list[str]
    evaluated_at: datetime
    horizon_days: int

    @property
    def reason_text(self) -> str:
        if not self.reasons:
            return "No major downside signals detected."
        return "; ".join(self.reasons)


def hold_days_from_unit(value: int, unit: str) -> int:
    unit = unit.lower().strip()
    if unit == "days":
        return value
    if unit == "months":
        return value * 30
    if unit == "years":
        return value * 365
    raise ValueError(f"Unsupported hold unit: {unit}")


def evaluate_hold_health(
    symbols: Iterable[str],
    horizon_days_by_symbol: dict[str, int],
    now: datetime | None = None,
) -> dict[str, HoldHealthResult]:
    symbols = [s.upper() for s in symbols]
    if not symbols:
        return {}

    now = now or datetime.now(timezone.utc)
    max_horizon = max(horizon_days_by_symbol.values()) if horizon_days_by_symbol else 30
    lookback_days = max(252, max_horizon + 60)
    start_dt = now - timedelta(days=int(lookback_days * 1.2))

    provider = YFinanceProvider()
    data = provider.get_multiple(symbols, start=start_dt, end=now)
    if not data:
        return {}

    engine = FeatureEngine()
    features = engine.compute(data, required=_HOLD_FEATURES)

    results: dict[str, HoldHealthResult] = {}

    for symbol in symbols:
        df = data.get(symbol)
        feat_df = features.get(symbol)
        if df is None or df.empty or feat_df is None or feat_df.empty:
            continue

        merged = df.join(feat_df, how="left", rsuffix="_feat")
        row = merged.iloc[-1]

        horizon_days = horizon_days_by_symbol.get(symbol, 30)
        strength, reasons = _score_row(row, horizon_days)

        results[symbol] = HoldHealthResult(
            symbol=symbol,
            strength=strength,
            reasons=reasons,
            evaluated_at=now,
            horizon_days=horizon_days,
        )

    return results


def _scaled_return(value: float | None, cap: float = 0.2) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    value = float(value)
    value = max(min(value, cap), -cap)
    return value / cap


def _scaled_signal(value: float | None, cap: float = 1.0) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    value = float(value)
    return float(np.tanh(value / cap))


def _score_row(row: pd.Series, horizon_days: int) -> tuple[float, list[str]]:
    ret_21 = _scaled_return(row.get("return_21d"))
    ret_63 = _scaled_return(row.get("return_63d"))
    ret_126 = _scaled_return(row.get("return_126d"))
    ret_252 = _scaled_return(row.get("return_252d"))

    sma = row.get("sma_crossover")
    if sma is None or (isinstance(sma, float) and math.isnan(sma)):
        sma_score = 0.0
    else:
        sma_score = 1.0 if float(sma) >= 1.0 else -1.0

    rsi = row.get("rsi_14")
    rsi_score = 0.0 if rsi is None else (float(rsi) - 50.0) / 50.0
    rsi_score = max(min(rsi_score, 1.0), -1.0)

    macd = _scaled_signal(row.get("macd_histogram"), cap=0.2)

    reasons: list[str] = []

    if horizon_days >= 365:
        score = (
            ret_126 * 0.35 +
            ret_252 * 0.35 +
            sma_score * 0.2 +
            rsi_score * 0.1
        )
        if ret_126 < 0:
            reasons.append("126d return negative")
        if ret_252 < 0:
            reasons.append("252d return negative")
        if sma_score < 0:
            reasons.append("SMA trend bearish")
        if rsi_score < -0.1:
            reasons.append("RSI momentum weak")
    elif horizon_days >= 180:
        score = (
            ret_63 * 0.35 +
            ret_126 * 0.35 +
            sma_score * 0.2 +
            rsi_score * 0.1
        )
        if ret_63 < 0:
            reasons.append("63d return negative")
        if ret_126 < 0:
            reasons.append("126d return negative")
        if sma_score < 0:
            reasons.append("SMA trend bearish")
        if rsi_score < -0.1:
            reasons.append("RSI momentum weak")
    else:
        score = (
            ret_21 * 0.4 +
            ret_63 * 0.2 +
            macd * 0.2 +
            rsi_score * 0.2
        )
        if ret_21 < 0:
            reasons.append("21d return negative")
        if ret_63 < 0:
            reasons.append("63d return negative")
        if macd < 0:
            reasons.append("MACD momentum negative")
        if rsi_score < -0.1:
            reasons.append("RSI momentum weak")

    score = float(max(min(score, 1.0), -1.0))
    return score, reasons
