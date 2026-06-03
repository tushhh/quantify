"""
Pydantic v2 schemas shared across all Quantify API routers.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Risk / Configuration schemas
# ---------------------------------------------------------------------------

class RiskConfig(BaseModel):
    """Portfolio-level risk limits."""
    max_portfolio_drawdown: float = Field(0.15, ge=0.01, le=1.0, description="Max drawdown before halting (0–1)")
    max_gross_leverage: float = Field(1.5, ge=0.1, le=5.0)
    max_single_position: float = Field(0.10, ge=0.01, le=1.0)
    max_sector_exposure: float = Field(0.30, ge=0.01, le=1.0)
    daily_loss_limit: float = Field(0.03, ge=0.001, le=0.5)
    default_stop_loss: float = Field(0.02, ge=0.001, le=0.5)
    default_take_profit: float = Field(0.04, ge=0.001, le=1.0)
    default_position_sizer: str = Field("equal_weight", description="equal_weight | volatility_target | half_kelly")


class StrategyConfig(BaseModel):
    """Per-strategy enable flag + allocation + arbitrary hyper-params."""
    enabled: bool = True
    allocation: float = Field(0.20, ge=0.0, le=1.0)
    params: Dict[str, Any] = Field(default_factory=dict)


class BacktestCostConfig(BaseModel):
    commission_per_share: float = Field(0.005, ge=0.0)
    spread_bps: float = Field(5.0, ge=0.0)
    slippage_pct: float = Field(0.05, ge=0.0)


# ---------------------------------------------------------------------------
# Backtest request / response
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    strategies: Dict[str, StrategyConfig] = Field(
        default_factory=dict,
        description="Map of strategy name → config. Omit to use defaults.",
    )
    start_date: date = Field(..., description="Backtest start date (YYYY-MM-DD)")
    end_date: date = Field(..., description="Backtest end date (YYYY-MM-DD)")
    initial_capital: float = Field(100_000.0, ge=1_000.0, le=100_000_000.0)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    costs: BacktestCostConfig = Field(default_factory=BacktestCostConfig)
    benchmark: str = Field("SPY", description="Benchmark ticker for comparison")
    universe: Optional[List[str]] = Field(None, description="Override stock universe (tickers)")

    @model_validator(mode="after")
    def end_after_start(self) -> "BacktestRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class TradeRecord(BaseModel):
    symbol: str
    strategy_name: str
    entry_date: Optional[date]
    exit_date: Optional[date]
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    return_pct: float
    holding_days: int
    side: str = "long"


class BacktestMetrics(BaseModel):
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_holding_days: float


class BacktestResponse(BaseModel):
    status: str = "ok"
    metrics: BacktestMetrics
    equity_curve: List[Dict[str, Any]]    # [{date, value, benchmark_value}]
    drawdown_curve: List[Dict[str, Any]]  # [{date, drawdown}]
    trades: List[TradeRecord]
    signals_count: int
    metadata: Dict[str, Any]


class BacktestSubmitResponse(BaseModel):
    status: str = "running"
    job_id: str



# ---------------------------------------------------------------------------
# Strategy info
# ---------------------------------------------------------------------------

class ParamSpec(BaseModel):
    key: str
    label: str
    type: str       # "int" | "float" | "bool" | "select"
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[str]] = None
    description: str = ""


class StrategyInfo(BaseModel):
    name: str
    label: str
    description: str
    default_allocation: float
    params: List[ParamSpec]


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

class TickerInfo(BaseModel):
    symbol: str
    sector: str
    name: str = ""


class UniverseResponse(BaseModel):
    tickers: List[TickerInfo]
    sectors: List[str]


# ---------------------------------------------------------------------------
# Risk presets
# ---------------------------------------------------------------------------

class RiskPreset(BaseModel):
    id: str
    label: str
    description: str
    risk: RiskConfig
    strategy_overrides: Dict[str, StrategyConfig]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str
    password: str
    telegram_username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    username: str
    telegram_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    """Schema for updating user account settings."""
    telegram_username: Optional[str] = None
    new_password: Optional[str] = None

# ---------------------------------------------------------------------------
# Prediction & Trade Tracking
# ---------------------------------------------------------------------------

class PredictionExplanation(BaseModel):
    feature: str
    zscore: float
    value: Optional[float] = None
    weight: Optional[float] = None
    direction: str = "higher"
    score: float = 0.0

class PredictionItem(BaseModel):
    symbol: str
    strength: float
    side: str
    sector: str = "Unknown"
    name: str = ""
    predicted_return_pct: float = 0.0
    explanations: List[PredictionExplanation] = Field(default_factory=list)

class PredictionResponse(BaseModel):
    status: str = "ok"
    mode: str = "previous_close"
    date: str = ""
    signals: List[PredictionItem] = Field(default_factory=list)
    cached: bool = False
    cache_age_minutes: float = 0.0
    universe_size: int = 0
    model_metrics: Optional[Dict[str, float]] = None
    message: Optional[str] = None

class TradeCreate(BaseModel):
    symbol: str
    shares: float
    buy_price: float
    hold_days: Optional[int] = None
    hold_unit: Optional[str] = None
    hold_value: Optional[int] = None
    dip_threshold_pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=0.9,
        description="Percent drop from entry that triggers an alert (0–0.9)",
    )


class TradeDipUpdate(BaseModel):
    dip_threshold_pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=0.9,
        description="Updated percent drop threshold (0–0.9); null disables",
    )

class TrackedTrade(TradeCreate):
    id: int
    created_at: str
    sell_date: str
    status: str
    current_strength: Optional[float] = None
    current_price: Optional[float] = None
    hold_unit: Optional[str] = None
    hold_value: Optional[int] = None
    last_health_reason: Optional[str] = None
    alert: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
