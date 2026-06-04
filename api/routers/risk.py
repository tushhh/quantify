"""
/api/risk  — Risk preset definitions (Conservative / Moderate / Aggressive / Custom).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from api.schemas import RiskConfig, RiskPreset, StrategyConfig

router = APIRouter(prefix="/risk", tags=["risk"])

# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------
PRESETS: list[RiskPreset] = [
    RiskPreset(
        id="conservative",
        label="Conservative",
        description=(
            "Capital preservation first. Tight drawdown limits, small positions, "
            "hard stops. Favours quality/value and pairs strategies over momentum."
        ),
        risk=RiskConfig(
            max_portfolio_drawdown=0.08,
            max_gross_leverage=1.0,
            max_single_position=0.05,
            max_sector_exposure=0.20,
            daily_loss_limit=0.015,
            default_stop_loss=0.01,
            default_take_profit=0.02,
            default_position_sizer="equal_weight",
        ),
        strategy_overrides={
            "trend_following":          StrategyConfig(enabled=True,  allocation=0.15),
            "cross_sectional_momentum": StrategyConfig(enabled=False, allocation=0.00),
            "pairs_mean_reversion":     StrategyConfig(enabled=True,  allocation=0.30),
            "quality_value":            StrategyConfig(enabled=True,  allocation=0.40),
            "ml_return_predictor":      StrategyConfig(enabled=False, allocation=0.00),
            "volatility_regime":        StrategyConfig(enabled=True,  allocation=0.15),
        },
    ),
    RiskPreset(
        id="moderate",
        label="Moderate",
        description=(
            "Balanced risk/reward with the system defaults. All six strategies active "
            "with equal-weight allocations and standard stop-loss levels."
        ),
        risk=RiskConfig(
            max_portfolio_drawdown=0.15,
            max_gross_leverage=1.5,
            max_single_position=0.10,
            max_sector_exposure=0.30,
            daily_loss_limit=0.03,
            default_stop_loss=0.02,
            default_take_profit=0.04,
            default_position_sizer="equal_weight",
        ),
        strategy_overrides={
            "trend_following":          StrategyConfig(enabled=True, allocation=0.15),
            "cross_sectional_momentum": StrategyConfig(enabled=True, allocation=0.20),
            "pairs_mean_reversion":     StrategyConfig(enabled=True, allocation=0.20),
            "quality_value":            StrategyConfig(enabled=True, allocation=0.20),
            "ml_return_predictor":      StrategyConfig(enabled=True, allocation=0.15),
            "volatility_regime":        StrategyConfig(enabled=True, allocation=0.10),
        },
    ),
    RiskPreset(
        id="aggressive",
        label="Aggressive",
        description=(
            "Maximise returns with higher leverage, wider stops, and momentum-heavy "
            "strategy weights. Suitable for risk-tolerant investors with long horizons."
        ),
        risk=RiskConfig(
            max_portfolio_drawdown=0.25,
            max_gross_leverage=2.0,
            max_single_position=0.20,
            max_sector_exposure=0.50,
            daily_loss_limit=0.05,
            default_stop_loss=0.035,
            default_take_profit=0.08,
            default_position_sizer="half_kelly",
        ),
        strategy_overrides={
            "trend_following":          StrategyConfig(enabled=True, allocation=0.10),
            "cross_sectional_momentum": StrategyConfig(enabled=True, allocation=0.40),
            "pairs_mean_reversion":     StrategyConfig(enabled=False, allocation=0.00),
            "quality_value":            StrategyConfig(enabled=True, allocation=0.10),
            "ml_return_predictor":      StrategyConfig(enabled=True, allocation=0.30),
            "volatility_regime":        StrategyConfig(enabled=True, allocation=0.10),
        },
    ),
    RiskPreset(
        id="custom",
        label="Custom",
        description="Fully customisable — adjust every parameter to your liking.",
        risk=RiskConfig(),
        strategy_overrides={},
    ),
]

_PRESET_MAP = {p.id: p for p in PRESETS}


@router.get("/presets", response_model=list[RiskPreset])
async def list_presets() -> list[RiskPreset]:
    """Return all available risk presets."""
    return PRESETS


@router.get("/presets/{preset_id}", response_model=RiskPreset)
async def get_preset(preset_id: str) -> RiskPreset:
    """Return a single risk preset by ID."""
    preset = _PRESET_MAP.get(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    return preset
