"""
/api/backtest  — Run backtests and stream progress via SSE.

POST /api/backtest         – synchronous, returns full BacktestResponse
GET  /api/backtest/stream  – SSE endpoint that streams log lines while running
"""

from __future__ import annotations

import asyncio
import logging
import math
import queue
from datetime import date
from typing import Any, AsyncGenerator, Dict, Optional

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.schemas import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    TradeRecord,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])
log = logging.getLogger("quantify.api.backtest")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2  # exponential backoff: 2s, 4s, 8s
REQUEST_TIMEOUT = 120  # 2 minutes max per request

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_data(tickers: list[str], start: date, end: date) -> Dict[str, pd.DataFrame]:
    """Download OHLCV data from yfinance via YFinanceProvider (which uses ParquetCache and handles retries)."""
    from quantify.data.providers.yfinance_provider import YFinanceProvider
    from quantify.data.cache import ParquetCache
    from datetime import datetime
    
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.min.time())
    
    provider = YFinanceProvider(cache=ParquetCache())
    result = provider.get_multiple(tickers, start_dt, end_dt)
    
    if not result:
        raise HTTPException(
            status_code=502,
            detail="No valid market data was retrieved for any tickers. Check dates and ticker symbols."
        )
        
    # YFinanceProvider returns standard OHLCV, but we also want to drop any empty dataframes and ensure length > 5
    filtered_result = {}
    for sym, df in result.items():
        if not df.empty and len(df) > 5:
            filtered_result[sym] = df
        else:
            log.warning(f"Insufficient data for {sym}: {len(df) if not df.empty else 0} bars")
            
    if not filtered_result:
        raise HTTPException(
            status_code=502,
            detail="No valid market data was retrieved for any tickers (insufficient bars). Check dates and ticker symbols."
        )
        
    return filtered_result


def _build_strategy_instances(req: BacktestRequest) -> list:
    """Instantiate strategy objects from the request config."""
    from quantify.strategy.trend_following import TrendFollowingStrategy
    from quantify.strategy.cross_sectional_momentum import CrossSectionalMomentumStrategy
    from quantify.strategy.pairs_mean_reversion import PairsMeanReversionStrategy
    from quantify.strategy.quality_value import QualityValueStrategy
    from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy
    from quantify.strategy.volatility_regime import VolatilityRegimeStrategy

    STRATEGY_MAP = {
        "trend_following": TrendFollowingStrategy,
        "cross_sectional_momentum": CrossSectionalMomentumStrategy,
        "pairs_mean_reversion": PairsMeanReversionStrategy,
        "quality_value": QualityValueStrategy,
        "ml_return_predictor": MLReturnPredictorStrategy,
        "volatility_regime": VolatilityRegimeStrategy,
    }

    # Defaults if not overridden
    DEFAULT_ENABLED = {
        "trend_following": True,
        "cross_sectional_momentum": True,
        "pairs_mean_reversion": True,
        "quality_value": True,
        "ml_return_predictor": True,
        "volatility_regime": True,
    }
    DEFAULT_ALLOCATION = {
        "trend_following": 0.15,
        "cross_sectional_momentum": 0.20,
        "pairs_mean_reversion": 0.20,
        "quality_value": 0.20,
        "ml_return_predictor": 0.15,
        "volatility_regime": 0.10,
    }

    instances = []
    failed_strategies = []
    
    for name, cls in STRATEGY_MAP.items():
        cfg = req.strategies.get(name)
        enabled = cfg.enabled if cfg else DEFAULT_ENABLED[name]
        if not enabled:
            log.debug(f"Strategy {name} is disabled")
            continue
        allocation = cfg.allocation if cfg else DEFAULT_ALLOCATION[name]
        extra_params = cfg.params if cfg else {}

        # Ensure allocation and enabled are not in extra_params
        extra_params.pop("allocation", None)
        extra_params.pop("enabled", None)

        try:
            log.info(f"Instantiating {name} with allocation {allocation*100:.0f}% and params: {extra_params}")
            instance = cls(**extra_params)
            setattr(instance, "allocation", allocation)
            instances.append(instance)
            log.info(f"Successfully instantiated {name}")
        except Exception as exc:
            failed_strategies.append((name, str(exc)))
            log.warning(f"Failed to instantiate {name}: {exc}")

    if not instances:
        detail = "No strategies could be instantiated. "
        if failed_strategies:
            detail += "Errors: " + "; ".join([f"{n}: {e}" for n, e in failed_strategies])
        else:
            detail += "No strategies enabled in request"
        raise HTTPException(status_code=400, detail=detail)
    
    if failed_strategies:
        log.warning(f"Some strategies failed to instantiate: {failed_strategies}. Proceeding with {len(instances)} strategies.")
    
    return instances


def _build_cost_model(req: BacktestRequest):
    from quantify.backtest.costs import CostModel
    return CostModel(
        commission_per_share=req.costs.commission_per_share,
        spread_bps=req.costs.spread_bps,
        slippage_pct=req.costs.slippage_pct,
    )


def _build_position_sizer(req: BacktestRequest):
    from quantify.risk.position_sizer import (
        EqualWeightSizer,
        VolatilityTargetSizer,
    )
    sizer_name = req.risk.default_position_sizer
    if sizer_name == "volatility_target":
        return VolatilityTargetSizer(max_position_pct=req.risk.max_single_position)
    if sizer_name == "half_kelly":
        from quantify.risk.position_sizer import get_sizer
        return get_sizer("half_kelly", max_position_pct=req.risk.max_single_position)
    return EqualWeightSizer(max_position_pct=req.risk.max_single_position)


def _build_risk_manager(req: BacktestRequest):
    from quantify.risk.portfolio_risk import PortfolioRiskManager
    return PortfolioRiskManager(
        max_drawdown=req.risk.max_portfolio_drawdown,
        max_gross_leverage=req.risk.max_gross_leverage,
        max_sector_exposure=req.risk.max_sector_exposure,
        max_daily_loss=req.risk.daily_loss_limit,
    )


def _sortino(daily_returns: pd.Series, risk_free: float = 0.0) -> float:
    rets = daily_returns.dropna()
    excess = rets - risk_free / 252
    downside = excess[excess < 0]
    downside_std = downside.std() * math.sqrt(252)
    if downside_std == 0:
        return 0.0
    return float(excess.mean() * 252 / downside_std)


def _calmar(annualized_return: float, max_drawdown: float) -> float:
    if max_drawdown == 0:
        return 0.0
    return annualized_return / max_drawdown


def _avg_holding(trades: list[dict]) -> float:
    import numpy as np
    days = [t.get("holding_days", 0) for t in trades if t.get("holding_days") is not None]
    return float(np.mean(days)) if days else 0.0


def _serialize_equity(equity: pd.Series, benchmark: pd.Series | None = None) -> list[dict]:
    records = []
    base = float(equity.iloc[0]) if len(equity) else 1.0
    if base == 0:
        base = 1.0  # guard against division-by-zero on degenerate equity curves
    bbase = float(benchmark.iloc[0]) if benchmark is not None and len(benchmark) else None

    for dt, val in equity.items():
        rec: dict[str, Any] = {
            "date": str(dt.date() if hasattr(dt, "date") else dt),
            "value": round(float(val), 2),
            "pct": round((float(val) / base - 1) * 100, 3),
        }
        if benchmark is not None and bbase is not None and dt in benchmark.index:
            bval = float(benchmark[dt])
            rec["benchmark_value"] = round(bval, 2)
            rec["benchmark_pct"] = round((bval / bbase - 1) * 100, 3)
        records.append(rec)
    return records


def _serialize_drawdown(equity: pd.Series) -> list[dict]:
    cum_max = equity.cummax()
    dd = (equity - cum_max) / cum_max * 100
    return [
        {"date": str(dt.date() if hasattr(dt, "date") else dt), "drawdown": round(float(v), 3)}
        for dt, v in dd.items()
    ]


def _run_backtest_sync(req: BacktestRequest) -> BacktestResponse:
    """Blocking backtest execution — called in a thread from the async endpoint."""
    from quantify.backtest.engine import BacktestEngine

    def _progress(msg: str):
        log.info(msg)
        if q := _progress_queues.get("default"):
            q.put(msg)

    # ── Universe ──────────────────────────────────────────────────────────
    # Note: benchmark symbol is included in the universe for data fetching,
    # but is excluded from strategy signal generation and only used for performance
    # comparison metrics.
    default_universe = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
        "JPM", "BAC", "GS", "V", "MA", "UNH", "JNJ", "PFE",
        "XOM", "CVX", "WMT", "PG", "KO", req.benchmark,
    ]
    tickers = list(dict.fromkeys(req.universe or default_universe))  # deduplicate, preserve order
    _progress(f"Universe: {len(tickers)} tickers")

    # ── Fetch data ────────────────────────────────────────────────────────
    _progress(f"Step 1/5: Downloading market data for {len(tickers)} tickers…")
    data = _fetch_data(tickers, req.start_date, req.end_date)
    _progress(f"Successfully fetched data for {len(data)} tickers")

    # ── Build engine components ────────────────────────────────────────────
    _progress("Step 2/5: Instantiating strategies…")
    strategies = _build_strategy_instances(req)
    
    cost_model = _build_cost_model(req)
    position_sizer = _build_position_sizer(req)
    risk_manager = _build_risk_manager(req)
    _progress("Step 3/5: Risk, cost, and sizing models configured")

    engine = BacktestEngine(
        strategies=strategies,
        initial_capital=req.initial_capital,
        cost_model=cost_model,
        position_sizer=position_sizer,
        risk_manager=risk_manager,
        start_date=req.start_date,
        end_date=req.end_date,
        benchmark_symbol=req.benchmark,
    )

    # ── Run ───────────────────────────────────────────────────────────────
    _progress("Step 4/5: Running backtest engine (this may take a minute)…")
    try:
        result = engine.run(data)
    except Exception as exc:
        log.error(f"Backtest engine failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal server error occurred during backtest execution.") from exc
    
    log.info(
        "Backtest complete: %d trades, %.2f%% return",
        len(result.trades),
        result.total_return * 100,
    )

    # ── Build benchmark series ─────────────────────────────────────────────
    benchmark_series: Optional[pd.Series] = None
    if req.benchmark in data:
        bdf = data[req.benchmark]
        bdf = bdf.reindex(result.equity_curve.index, method="ffill")
        bval = bdf["close"] / float(bdf["close"].iloc[0]) * req.initial_capital
        benchmark_series = bval

    # ── Metrics ───────────────────────────────────────────────────────────
    log.info("Step 5/5: Computing metrics and serializing results…")
    metrics = BacktestMetrics(
        total_return=round(result.total_return, 6),
        annualized_return=round(result.annualized_return, 6),
        sharpe_ratio=round(result.sharpe_ratio, 4),
        sortino_ratio=round(_sortino(result.daily_returns), 4),
        calmar_ratio=round(_calmar(result.annualized_return, result.max_drawdown), 4),
        max_drawdown=round(result.max_drawdown, 6),
        win_rate=round(result.win_rate, 4),
        profit_factor=round(min(result.profit_factor, 999.0), 4),
        total_trades=len(result.trades),
        avg_holding_days=round(_avg_holding(result.trades), 1),
    )

    # ── Trades ────────────────────────────────────────────────────────────
    trades_out: list[TradeRecord] = []
    for t in result.trades:
        try:
            trades_out.append(TradeRecord(
                symbol=t.get("symbol", ""),
                strategy_name=t.get("strategy_name", ""),
                entry_date=t.get("entry_date"),
                exit_date=t.get("exit_date"),
                entry_price=round(float(t.get("entry_price", 0)), 4),
                exit_price=round(float(t.get("exit_price", 0)), 4),
                quantity=round(float(t.get("quantity", 0)), 4),
                pnl=round(float(t.get("pnl", 0)), 2),
                return_pct=round(float(t.get("return_pct", 0)), 6),
                holding_days=int(t.get("holding_days", 0) or 0),
                side=t.get("side", "long"),
            ))
        except Exception as exc:
            log.debug("Skipping trade record: %s", exc)

    response = BacktestResponse(
        status="ok",
        metrics=metrics,
        equity_curve=_serialize_equity(result.equity_curve, benchmark_series),
        drawdown_curve=_serialize_drawdown(result.equity_curve),
        trades=trades_out,
        signals_count=len(result.signals_log),
        metadata={
            **result.metadata,
            "strategies_run": [s.name for s in strategies],
            "start_date": str(req.start_date),
            "end_date": str(req.end_date),
            "initial_capital": req.initial_capital,
        },
    )

    _progress("__done__")
    return response


# ---------------------------------------------------------------------------
# SSE progress streaming
# ---------------------------------------------------------------------------
_progress_queues: Dict[str, "queue.Queue[str]"] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest) -> BacktestResponse:
    """
    Run a full backtest.

    Accepts strategy configs, date range, capital, risk profile, and cost model.
    Returns equity curve, drawdown, per-trade log, and aggregate metrics.
    """
    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(None, _run_backtest_sync, req)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Unhandled error during backtest")
        raise HTTPException(status_code=500, detail="An unhandled internal server error occurred.") from exc
    return response


@router.get("/stream")
async def stream_progress(job_id: str = "default") -> StreamingResponse:
    """
    SSE endpoint – clients subscribe before posting /api/backtest
    to receive live progress messages.
    """
    q: queue.Queue[str] = queue.Queue()
    _progress_queues[job_id] = q
    loop = asyncio.get_running_loop()

    async def _generate() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    msg = await loop.run_in_executor(None, lambda: q.get(timeout=25))
                    if msg == "__done__":
                        yield "data: done\n\n"
                        break
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            _progress_queues.pop(job_id, None)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
