"""
/api/backtest  — Run backtests and stream progress via SSE.

POST /api/backtest         – synchronous, returns full BacktestResponse
GET  /api/backtest/stream  – SSE endpoint that streams log lines while running
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import queue
import urllib.error
import urllib.request
from datetime import date
from typing import Any, AsyncGenerator, Dict, Optional

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd
import collections
from typing import Union
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from api.schemas import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResponse,
    BacktestSubmitResponse,
    TradeRecord,
)

router = APIRouter(prefix="/backtest", tags=["backtest"])
log = logging.getLogger("quantify.api.backtest")

# In-memory caches for async backtest runs
_backtest_results = collections.OrderedDict()
_active_jobs = set()


def _save_result(job_id: str, result: Any):
    if len(_backtest_results) >= 3:
        _backtest_results.popitem(last=False)
    _backtest_results[job_id] = result


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
    from datetime import datetime, timedelta
    
    # Pad the start date to fetch historical lookback data for indicators
    # (e.g. 252-day momentum requires roughly 365 calendar days of history)
    padded_start = start - timedelta(days=400)
    
    start_dt = datetime.combine(padded_start, datetime.min.time())
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

    import inspect

    instances = []
    failed_strategies = []

    for name, cls in STRATEGY_MAP.items():
        cfg = req.strategies.get(name)
        enabled = cfg.enabled if cfg else DEFAULT_ENABLED[name]
        if not enabled:
            log.debug(f"Strategy {name} is disabled")
            continue
        allocation = cfg.allocation if cfg else DEFAULT_ALLOCATION[name]
        # Copy so we never mutate the request object's params dict.
        extra_params = dict(cfg.params) if cfg and cfg.params else {}

        # Ensure allocation and enabled are not in extra_params
        extra_params.pop("allocation", None)
        extra_params.pop("enabled", None)

        # For the ML strategy, prefer the pre-trained model from the model-cache
        # branch instead of retraining the LightGBM+XGBoost+CatBoost ensemble on
        # every walk-forward window. In-process retraining is the single biggest
        # memory consumer in a backtest and OOMs small dynos; cached inference
        # keeps the run within a ~512 MB budget and is much faster. Advanced
        # users can force walk-forward retraining via train_enabled=true.
        #
        # Only disable retraining when a cached model is actually available —
        # otherwise fall back to walk-forward so the strategy still contributes
        # signals. Trade-off: a single forward-trained model scored over
        # historical dates introduces lookahead bias — flagged in the metadata.
        if name == "ml_return_predictor" and "train_enabled" not in extra_params:
            import os as _os
            cached_available = False
            try:
                from api.routers.predict import _download_latest_model
                _download_latest_model()
                cached_available = _os.path.exists("./models/ml_return_predictor.joblib")
            except Exception as exc:
                log.warning("Could not pre-download cached ML model: %s", exc)
            if cached_available:
                extra_params["train_enabled"] = False
            else:
                log.warning(
                    "No cached ML model available — backtest will retrain "
                    "(higher memory; consider running the ml_train workflow)."
                )

        # Defensively drop any params the constructor does not accept. The UI
        # advertises a curated param set per strategy, but this guarantees a
        # stray or renamed key can never crash the whole backtest with a 400.
        try:
            sig = inspect.signature(cls.__init__)
            accepts_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            )
            if not accepts_kwargs:
                accepted = set(sig.parameters) - {"self"}
                unknown = [k for k in extra_params if k not in accepted]
                if unknown:
                    log.warning("%s: ignoring unsupported params %s", name, unknown)
                    for k in unknown:
                        extra_params.pop(k, None)
        except (TypeError, ValueError):
            pass

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


def _finite(value: float, default: float = 0.0) -> float:
    """Coerce NaN/inf metric values to a finite default. Degenerate runs (e.g.
    no downside returns → NaN Sortino) must not emit non-finite floats, which
    break strict JSON parsing in the browser and the offload round-trip."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


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


def _run_backtest_sync(req: BacktestRequest, job_id: str = "default") -> BacktestResponse:
    """Blocking backtest execution — called in a thread from the async endpoint."""
    from quantify.backtest.engine import BacktestEngine

    def _progress(msg: str):
        log.info(msg)
        if q := _progress_queues.get(job_id):
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

    try:
        from quantify.data.fundamentals import fetch_fundamentals, add_fundamental_features
        _progress(f"Fetching fundamental data for {len(data)} tickers…")
        fundamentals = fetch_fundamentals(list(data.keys()))
        data = add_fundamental_features(data, fundamentals)
        _progress("Successfully appended fundamental features")
    except Exception as exc:
        log.warning(f"Failed to fetch and append fundamental features: {exc}")

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
        try:
            bdf.index = bdf.index.tz_convert(result.equity_curve.index.tz) if result.equity_curve.index.tz else bdf.index.tz_localize(None)
        except Exception:
            pass
        bdf = bdf.reindex(result.equity_curve.index, method="ffill")
        bval = bdf["close"] / float(bdf["close"].iloc[0]) * req.initial_capital
        benchmark_series = bval

    # ── Metrics ───────────────────────────────────────────────────────────
    log.info("Step 5/5: Computing metrics and serializing results…")
    metrics = BacktestMetrics(
        total_return=round(_finite(result.total_return), 6),
        annualized_return=round(_finite(result.annualized_return), 6),
        sharpe_ratio=round(_finite(result.sharpe_ratio), 4),
        sortino_ratio=round(_finite(_sortino(result.daily_returns)), 4),
        calmar_ratio=round(_finite(_calmar(result.annualized_return, result.max_drawdown)), 4),
        max_drawdown=round(_finite(result.max_drawdown), 6),
        win_rate=round(_finite(result.win_rate), 4),
        profit_factor=round(_finite(min(result.profit_factor, 999.0)), 4),
        total_trades=len(result.trades),
        avg_holding_days=round(_finite(_avg_holding(result.trades)), 1),
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

    # Flag how the ML strategy sourced its model so the lookahead trade-off of
    # cached inference is transparent in the response.
    ml_strategy = next((s for s in strategies if s.name == "ml_return_predictor"), None)
    ml_metadata: dict[str, Any] = {}
    if ml_strategy is not None:
        used_cached = not getattr(ml_strategy, "train_enabled", True)
        ml_metadata["ml_model_mode"] = "cached_pretrained" if used_cached else "walk_forward"
        if used_cached:
            ml_metadata["ml_lookahead_warning"] = (
                "ML signals use the latest pre-trained model for every date "
                "(low memory, fast) rather than walk-forward retraining, so ML "
                "contribution is optimistic. Set train_enabled=true to retrain."
            )

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
            **ml_metadata,
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

def _run_backtest_bg(req: BacktestRequest, job_id: str):
    try:
        response = _run_backtest_sync(req, job_id)
        _save_result(job_id, response)
    except Exception as exc:
        log.exception(f"Unhandled error during backtest job {job_id}")
        _save_result(job_id, exc)
    finally:
        _active_jobs.discard(job_id)


# ---------------------------------------------------------------------------
# Cloud offload — run heavy backtests on a GitHub Actions runner (far more
# memory than a small dyno) and receive the result via an authenticated
# callback. The result lands in _backtest_results so the existing
# /result/{job_id} polling endpoint serves it with no client change.
# ---------------------------------------------------------------------------

def store_offloaded_result(job_id: str, result: Any) -> None:
    """Persist a result produced by an offloaded (GitHub Actions) backtest so the
    /result/{job_id} polling endpoint can serve it. `result` is a
    BacktestResponse on success or an Exception on failure."""
    _save_result(job_id, result)
    _active_jobs.discard(job_id)


def _db_persist_job(job_id: str, request_json: str) -> None:
    """Write a cloud job row to the DB so it survives a dyno restart."""
    try:
        from api.database import SessionLocal
        from api.models import BacktestJob
        db = SessionLocal()
        try:
            job = BacktestJob(id=job_id, status="running", request_json=request_json, is_cloud_run=True)
            db.merge(job)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        log.warning("Failed to persist cloud backtest job %s to DB: %s", job_id, exc)


def _db_lookup_job(job_id: str) -> Optional[dict]:
    """Check DB for a job. Returns None if not found or on error."""
    try:
        from api.database import SessionLocal
        from api.models import BacktestJob
        db = SessionLocal()
        try:
            job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()
            if job is None:
                return None
            return {"status": job.status, "result_json": job.result_json, "error": job.error}
        finally:
            db.close()
    except Exception as exc:
        log.warning("DB lookup for backtest job %s failed: %s", job_id, exc)
        return None


def _offload_is_configured() -> bool:
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_WORKFLOW_TOKEN") or os.getenv("GITHUB_TOKEN")
    heroku_url = os.getenv("HEROKU_APP_URL", "").strip()
    return bool(repo and token and heroku_url)


def _should_offload(req: BacktestRequest, offload: Optional[bool]) -> bool:
    """Decide whether to ship this run to GitHub Actions. An explicit `offload`
    flag wins; otherwise auto-offload heavy runs when BACKTEST_OFFLOAD_AUTO is on.
    Returns False unless offload is actually configured."""
    if not _offload_is_configured():
        return False
    if offload is not None:
        return offload
    if os.getenv("BACKTEST_OFFLOAD_AUTO", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
        
    return False


def _dispatch_backtest_workflow(req: BacktestRequest, job_id: str) -> bool:
    """Trigger the backtest GitHub Actions workflow via workflow_dispatch.
    Returns True on success; False if not configured or the dispatch failed
    (caller falls back to in-process execution).
    The internal_secret is intentionally NOT passed as an input so it never
    appears in Actions logs — the workflow reads it from the repo secret."""
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_WORKFLOW_TOKEN") or os.getenv("GITHUB_TOKEN")
    heroku_url = os.getenv("HEROKU_APP_URL", "").rstrip("/")
    if not (repo and token and heroku_url):
        return False

    inputs = {
        "job_id": job_id,
        "request_json": req.model_dump_json(),
        "heroku_callback_url": f"{heroku_url}/api/internal/backtest-complete",
        # internal_secret left empty — workflow falls back to secrets.INTERNAL_API_SECRET
        "internal_secret": "",
    }
    payload = json.dumps({"ref": os.getenv("GH_WORKFLOW_REF", "main"), "inputs": inputs}).encode()
    url = f"https://api.github.com/repos/{repo}/actions/workflows/backtest.yml/dispatches"
    gh_req = urllib.request.Request(url, data=payload, method="POST")
    gh_req.add_header("Authorization", f"token {token}")
    gh_req.add_header("Accept", "application/vnd.github.v3+json")
    gh_req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(gh_req, timeout=10) as resp:
            log.info("Dispatched backtest workflow for job_id=%s (HTTP %d)", job_id, resp.status)
        _db_persist_job(job_id, req.model_dump_json())
        return True
    except urllib.error.HTTPError as e:
        log.error("Failed to dispatch backtest workflow: HTTP %d — %s", e.code, e.read().decode()[:300])
        return False
    except Exception as e:
        log.error("Failed to dispatch backtest workflow: %s", e)
        return False


@router.post("", response_model=Union[BacktestResponse, BacktestSubmitResponse])
async def run_backtest(
    req: BacktestRequest,
    background_tasks: BackgroundTasks,
    job_id: str = "default",
    run_sync: bool = False,
    offload: Optional[bool] = None,
) -> Union[BacktestResponse, BacktestSubmitResponse]:
    """
    Run a full backtest.

    Accepts strategy configs, date range, capital, risk profile, and cost model.
    If run_sync is False (default), it runs in the background and returns a job_id.
    Clients poll /api/backtest/result/{job_id} to get the final results.

    Heavy runs can be offloaded to a GitHub Actions runner (more memory than a
    small dyno). Pass offload=true to force it, or set BACKTEST_OFFLOAD_AUTO=true
    on the server to auto-offload heavy runs. Either way the client keeps polling
    /result/{job_id}; the workflow POSTs the result back to the web process.
    """
    if run_sync:
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(None, _run_backtest_sync, req, job_id)
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("Unhandled error during backtest")
            raise HTTPException(status_code=500, detail="An unhandled internal server error occurred.") from exc
        return response

    # Offload heavy runs to GitHub Actions when requested/configured. Mark the
    # job active first so /result/{job_id} returns "running" until the callback
    # lands. Fall back to in-process execution if the dispatch fails.
    if _should_offload(req, offload):
        _active_jobs.add(job_id)
        loop = asyncio.get_running_loop()
        dispatched = await loop.run_in_executor(None, _dispatch_backtest_workflow, req, job_id)
        if dispatched:
            return BacktestSubmitResponse(status="running", job_id=job_id, is_cloud_run=True)
        log.info("Backtest offload unavailable; running in-process for job_id=%s", job_id)

    # Async background task (in-process)
    _active_jobs.add(job_id)
    background_tasks.add_task(_run_backtest_bg, req, job_id)
    return BacktestSubmitResponse(status="running", job_id=job_id)


@router.get("/result/{job_id}")
async def get_backtest_result(job_id: str):
    """Retrieve the results of a completed backtest job."""
    # Fast in-memory path
    if job_id in _backtest_results:
        res = _backtest_results[job_id]
        if isinstance(res, Exception):
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred during backtest execution: {res}",
            )
        return res

    if job_id in _active_jobs or job_id in _progress_queues:
        return {"status": "running"}

    # DB fallback: covers dyno restarts between cloud dispatch and callback.
    loop = asyncio.get_running_loop()
    job_row = await loop.run_in_executor(None, _db_lookup_job, job_id)
    if job_row:
        if job_row["status"] == "running":
            _active_jobs.add(job_id)  # re-register so next poll skips DB
            return {"status": "running"}
        if job_row["status"] == "failed":
            raise HTTPException(status_code=500, detail=job_row["error"] or "Backtest failed on runner")
        if job_row["status"] == "complete" and job_row["result_json"]:
            try:
                result = BacktestResponse(**json.loads(job_row["result_json"]))
                _save_result(job_id, result)
                return result
            except Exception as exc:
                log.error("Failed to re-parse stored result for job %s: %s", job_id, exc)
                raise HTTPException(status_code=500, detail="Failed to parse stored result")

    raise HTTPException(status_code=404, detail="Job not found or expired")



@router.get("/stream")
async def stream_progress(job_id: str = "default") -> StreamingResponse:
    """
    SSE endpoint – clients subscribe before posting /api/backtest
    to receive live progress messages.
    """
    q: queue.Queue[str] = queue.Queue(maxsize=200)
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
