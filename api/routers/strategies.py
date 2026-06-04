"""
/api/strategies  — Strategy metadata & default parameter specs.
"""

from __future__ import annotations

from fastapi import APIRouter
from api.schemas import ParamSpec, StrategyInfo

router = APIRouter(prefix="/strategies", tags=["strategies"])


STRATEGIES: list[StrategyInfo] = [
    StrategyInfo(
        name="trend_following",
        label="Trend Following",
        description=(
            "EMA crossover (fast/slow) filtered by ADX strength. "
            "Uses ATR-based trailing stops. Best in trending markets."
        ),
        default_allocation=0.15,
        params=[
            ParamSpec(key="fast_ema", label="Fast EMA (days)", type="int", default=50, min=5, max=100, step=5),
            ParamSpec(key="slow_ema", label="Slow EMA (days)", type="int", default=200, min=50, max=500, step=10),
            ParamSpec(key="atr_period", label="ATR Period", type="int", default=14, min=5, max=30, step=1),
            ParamSpec(key="atr_multiplier", label="ATR Stop Multiplier", type="float", default=2.0, min=0.5, max=5.0, step=0.5),
            ParamSpec(key="adx_threshold", label="ADX Trend Threshold", type="int", default=25, min=10, max=50, step=5),
            ParamSpec(key="max_positions", label="Max Positions", type="int", default=15, min=1, max=50, step=1),
        ],
    ),
    StrategyInfo(
        name="cross_sectional_momentum",
        label="Cross-Sectional Momentum",
        description=(
            "Long top-quintile / short bottom-quintile stocks ranked by 12-1 month returns "
            "(Jegadeesh & Titman). Positions are scaled by inverse volatility."
        ),
        default_allocation=0.20,
        params=[
            ParamSpec(key="formation_months", label="Formation Period (months)", type="int", default=12, min=3, max=24, step=1),
            ParamSpec(key="skip_months", label="Skip Recent (months)", type="int", default=1, min=0, max=3, step=1),
            ParamSpec(key="holding_months", label="Holding Period (months)", type="int", default=1, min=1, max=6, step=1),
            ParamSpec(key="long_quantile", label="Long Quantile", type="float", default=0.80, min=0.5, max=0.95, step=0.05),
            ParamSpec(key="short_quantile", label="Short Quantile", type="float", default=0.20, min=0.05, max=0.5, step=0.05),
            ParamSpec(key="max_positions", label="Max Positions (per leg)", type="int", default=20, min=5, max=50, step=5),
            ParamSpec(key="volatility_scale", label="Vol-Scale Positions", type="bool", default=True),
        ],
    ),
    StrategyInfo(
        name="pairs_mean_reversion",
        label="Pairs Mean Reversion",
        description=(
            "Engle-Granger cointegration between stock pairs. Enter when z-score diverges, "
            "exit when it reverts. Market-neutral by construction."
        ),
        default_allocation=0.20,
        params=[
            ParamSpec(key="lookback_days", label="Lookback (days)", type="int", default=60, min=20, max=252, step=10),
            ParamSpec(key="entry_zscore", label="Entry Z-Score", type="float", default=2.0, min=1.0, max=4.0, step=0.5),
            ParamSpec(key="exit_zscore", label="Exit Z-Score", type="float", default=0.5, min=0.0, max=2.0, step=0.25),
            ParamSpec(key="stop_zscore", label="Stop Z-Score", type="float", default=3.5, min=2.0, max=6.0, step=0.5),
            ParamSpec(key="max_pairs", label="Max Pairs", type="int", default=10, min=1, max=30, step=1),
            ParamSpec(key="cointegration_pvalue", label="Cointegration p-value", type="float", default=0.05, min=0.01, max=0.2, step=0.01),
        ],
    ),
    StrategyInfo(
        name="quality_value",
        label="Quality Value",
        description=(
            "Long stocks with high composite quality (ROE, ROA, margins) and value (P/E, P/B, EV/EBITDA) scores. "
            "Rebalances monthly."
        ),
        default_allocation=0.20,
        params=[
            ParamSpec(key="long_quantile", label="Long Quantile", type="float", default=0.80, min=0.5, max=0.95, step=0.05),
            ParamSpec(key="max_positions", label="Max Positions", type="int", default=20, min=5, max=50, step=5),
            ParamSpec(key="min_market_cap_m", label="Min Market Cap ($M)", type="float", default=2000, min=100, max=100000, step=100),
            ParamSpec(
                key="composite_method",
                label="Composite Method",
                type="select",
                default="equal_weight",
                options=["equal_weight", "rank_weighted"],
            ),
        ],
    ),
    StrategyInfo(
        name="ml_return_predictor",
        label="ML Return Predictor",
        description=(
            "LightGBM model trained on momentum, volatility, and technical features "
            "to predict 5-day forward returns. Retrains monthly on a rolling window."
        ),
        default_allocation=0.15,
        params=[
            ParamSpec(key="target_horizon_days", label="Prediction Horizon (days)", type="int", default=5, min=1, max=21, step=1),
            ParamSpec(key="train_years", label="Training Window (years)", type="int", default=3, min=1, max=10, step=1),
            ParamSpec(key="long_threshold", label="Long Threshold", type="float", default=0.60, min=0.5, max=0.95, step=0.05),
            ParamSpec(key="short_threshold", label="Short Threshold", type="float", default=0.40, min=0.05, max=0.5, step=0.05),
            ParamSpec(key="max_positions", label="Max Positions", type="int", default=20, min=5, max=50, step=5),
        ],
    ),
    StrategyInfo(
        name="volatility_regime",
        label="Volatility Regime",
        description=(
            "Uses VIX levels to detect low/high volatility regimes and dynamically "
            "re-weights the other strategies accordingly."
        ),
        default_allocation=0.10,
        params=[
            ParamSpec(key="vix_low_threshold", label="VIX Low Regime (<)", type="float", default=15.0, min=5.0, max=30.0, step=1.0),
            ParamSpec(key="vix_high_threshold", label="VIX High Regime (>)", type="float", default=25.0, min=15.0, max=60.0, step=1.0),
            ParamSpec(key="regime_lookback_days", label="Regime Lookback (days)", type="int", default=21, min=5, max=63, step=1),
            ParamSpec(key="transition_smoothing_days", label="Transition Smoothing (days)", type="int", default=5, min=1, max=21, step=1),
        ],
    ),
]


@router.get("", response_model=list[StrategyInfo])
async def list_strategies() -> list[StrategyInfo]:
    """Return metadata and configurable parameters for all strategies."""
    return STRATEGIES


@router.get("/{name}", response_model=StrategyInfo)
async def get_strategy(name: str) -> StrategyInfo:
    """Return metadata for a single strategy by name."""
    for s in STRATEGIES:
        if s.name == name:
            return s
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
