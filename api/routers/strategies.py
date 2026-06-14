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
            ParamSpec(key="vol_target", label="Volatility Target (annual)", type="float", default=0.10, min=0.05, max=0.40, step=0.01, description="Annualised volatility target used to size each position."),
            ParamSpec(key="min_bars", label="Min History (days)", type="int", default=252, min=60, max=504, step=21, description="Minimum trading days of history required before a symbol can be traded."),
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
            ParamSpec(key="long_threshold", label="Long Percentile", type="float", default=0.90, min=0.55, max=0.95, step=0.05, description="Go long names ranked above this momentum percentile."),
            ParamSpec(key="short_threshold", label="Short Percentile", type="float", default=0.10, min=0.05, max=0.45, step=0.05, description="Go short names ranked below this momentum percentile."),
            ParamSpec(key="rebalance_days", label="Rebalance (days)", type="int", default=21, min=5, max=63, step=1, description="Trading days between portfolio rebalances."),
            ParamSpec(key="crash_filter", label="SPY Crash Filter", type="bool", default=True, description="Suppress new longs while the market (SPY) is in a drawdown."),
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
            ParamSpec(key="entry_zscore", label="Entry Z-Score", type="float", default=2.0, min=1.0, max=4.0, step=0.5, description="Spread z-score divergence that triggers a new pair entry."),
            ParamSpec(key="exit_zscore", label="Exit Z-Score", type="float", default=0.5, min=0.0, max=2.0, step=0.25, description="Spread z-score at which an open pair is closed."),
            ParamSpec(key="stop_zscore", label="Stop Z-Score", type="float", default=4.0, min=2.0, max=6.0, step=0.5, description="Spread z-score that forces a stop-out."),
            ParamSpec(key="max_active_pairs", label="Max Active Pairs", type="int", default=5, min=1, max=30, step=1, description="Maximum number of simultaneously open pairs."),
            ParamSpec(key="coint_pvalue", label="Cointegration p-value", type="float", default=0.05, min=0.01, max=0.2, step=0.01, description="Maximum Engle-Granger p-value for a pair to qualify."),
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
            ParamSpec(key="long_quintile", label="Long Quantile", type="float", default=0.80, min=0.5, max=0.95, step=0.05, description="Go long names above this composite quality/value percentile."),
            ParamSpec(key="short_quintile", label="Short Quantile", type="float", default=0.20, min=0.05, max=0.5, step=0.05, description="Short threshold (only applied when shorting is enabled)."),
            ParamSpec(key="rebalance_days", label="Rebalance (days)", type="int", default=21, min=5, max=63, step=1, description="Trading days between rebalances."),
            ParamSpec(key="enable_short", label="Enable Shorts", type="bool", default=False, description="Allow short positions on the lowest-ranked names."),
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
            ParamSpec(key="long_decile", label="Long Decile", type="float", default=0.90, min=0.5, max=0.95, step=0.05, description="Go long predictions ranked above this decile."),
            ParamSpec(key="short_decile", label="Short Decile", type="float", default=0.10, min=0.05, max=0.5, step=0.05, description="Go short predictions ranked below this decile."),
            ParamSpec(key="rebalance_days", label="Rebalance (days)", type="int", default=5, min=1, max=21, step=1, description="Trading days between portfolio rebalances."),
            ParamSpec(key="retrain_interval_days", label="Retrain Interval (days)", type="int", default=21, min=5, max=63, step=1, description="Trading days between model retrains on a rolling window."),
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
            ParamSpec(key="vix_low", label="VIX Low Regime (<)", type="float", default=15.0, min=5.0, max=30.0, step=1.0, description="Below this VIX level the market is treated as calm."),
            ParamSpec(key="vix_high", label="VIX High Regime (>)", type="float", default=25.0, min=15.0, max=60.0, step=1.0, description="Above this VIX level exposure is scaled down."),
            ParamSpec(key="high_vol_scale", label="High-Vol Scale", type="float", default=0.50, min=0.1, max=1.0, step=0.05, description="Exposure multiplier applied in high-volatility regimes."),
            ParamSpec(key="low_vol_boost", label="Low-Vol Boost", type="float", default=1.10, min=1.0, max=1.5, step=0.05, description="Exposure multiplier applied in calm regimes."),
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
