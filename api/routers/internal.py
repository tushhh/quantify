"""
Internal API endpoints for async GitHub Actions screener workflow.
"""
import json
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.database import SessionLocal
from api.models import AsyncPredictionJob

router = APIRouter(prefix="/internal", tags=["internal"])
log = logging.getLogger("quantify.api.internal")

_INTERNAL_SECRET = os.getenv("INTERNAL_API_SECRET", "")


def _verify_secret(x_internal_secret: Optional[str]) -> None:
    if _INTERNAL_SECRET and x_internal_secret != _INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")


class TriggerScreenerRequest(BaseModel):
    chat_id: str


class JobCompletePayload(BaseModel):
    chat_id: str
    status: str  # "complete" or "failed"
    result_json: Optional[str] = None  # serialized PredictionResponse JSON
    error: Optional[str] = None


class GainerInfo(BaseModel):
    symbol: str
    gain_pct: float
    price: float
    prev_close: float


class GainAlertPayload(BaseModel):
    gainers: list[GainerInfo]
    scan_date: str  # YYYY-MM-DD in ET


class BacktestCompletePayload(BaseModel):
    job_id: str
    status: str  # "complete" or "failed"
    result_json: Optional[str] = None  # serialized BacktestResponse JSON
    error: Optional[str] = None


@router.post("/trigger-screener")
async def trigger_screener(
    body: TriggerScreenerRequest,
    x_internal_secret: Optional[str] = Header(None),
):
    """Trigger the full 500-stock screener GitHub Actions workflow for a chat."""
    _verify_secret(x_internal_secret)

    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GH_WORKFLOW_TOKEN") or os.getenv("GITHUB_TOKEN")
    heroku_url = os.getenv("HEROKU_APP_URL", "").rstrip("/")

    if not repo or not token:
        raise HTTPException(status_code=503, detail="GitHub integration not configured (GITHUB_REPOSITORY or GH_WORKFLOW_TOKEN missing)")

    # Create a pending job record
    db = SessionLocal()
    try:
        job = AsyncPredictionJob(chat_id=body.chat_id, status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id
    finally:
        db.close()

    # Trigger workflow_dispatch on full_screener.yml
    payload = json.dumps({
        "ref": "main",
        "inputs": {
            "chat_id": body.chat_id,
            "job_id": str(job_id),
            "heroku_callback_url": f"{heroku_url}/api/internal/job-complete",
        }
    }).encode()

    url = f"https://api.github.com/repos/{repo}/actions/workflows/full_screener.yml/dispatches"
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info("Triggered full_screener workflow for chat_id=%s job_id=%d (HTTP %d)", body.chat_id, job_id, resp.status)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        log.error("Failed to trigger workflow: HTTP %d — %s", e.code, body_text)
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e.code}")

    return {"status": "triggered", "job_id": job_id}


@router.post("/job-complete")
async def job_complete(
    body: JobCompletePayload,
    x_internal_secret: Optional[str] = Header(None),
):
    """Receive screener results from GitHub Actions and notify the user via Telegram."""
    _verify_secret(x_internal_secret)

    db = SessionLocal()
    try:
        # Update the job record
        job = db.query(AsyncPredictionJob).filter(
            AsyncPredictionJob.chat_id == body.chat_id,
            AsyncPredictionJob.status == "pending",
        ).order_by(AsyncPredictionJob.created_at.desc()).first()

        if job:
            job.status = body.status
            job.completed_at = datetime.now(timezone.utc)
            job.result_json = body.result_json
            db.commit()

        # If successful, also persist as the main prediction cache
        if body.status == "complete" and body.result_json:
            try:
                from api.schemas import PredictionResponse
                from api.routers.predict import update_memory_cache, _get_ticker_name
                result = PredictionResponse(**json.loads(body.result_json))
                # Screener stores ticker symbol as the name field; enrich it here
                # so /top and /bottom show company names rather than echoing the ticker.
                enriched = [
                    sig.model_copy(update={"name": _get_ticker_name(sig.symbol)})
                    for sig in result.signals
                ]
                result = result.model_copy(update={"signals": enriched})
                update_memory_cache("previous_close", result)
            except Exception as e:
                log.warning("Could not persist screener results to main cache: %s", e)

    finally:
        db.close()

    # Send Telegram notification to the requesting chat
    bot_token = os.getenv("TELEGRAM_PREDICTION_BOT_TOKEN")
    if bot_token and body.chat_id:
        try:
            import asyncio
            from api.prediction_bot import _send_fullscan_result
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_send_fullscan_result(body.chat_id, body.result_json, body.error))
            except RuntimeError:
                asyncio.run(_send_fullscan_result(body.chat_id, body.result_json, body.error))
        except Exception as e:
            log.error("Failed to send Telegram notification: %s", e)

    return {"status": "received"}


@router.get("/gain-scan-status")
async def gain_scan_status():
    """Diagnostic: show subscriptions, today's state records, and server time."""
    import pytz
    from api.models import GainAlertState, GainAlertSubscription

    et = pytz.timezone("America/New_York")
    now_et = datetime.now(et)
    alert_date = now_et.strftime("%Y-%m-%d")

    db = SessionLocal()
    try:
        subs = db.query(GainAlertSubscription).all()
        states = db.query(GainAlertState).filter(GainAlertState.alert_date == alert_date).all()
    finally:
        db.close()

    return {
        "server_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "subscriptions": [{"chat_id": s.chat_id, "threshold_pct": s.threshold_pct} for s in subs],
        "todays_state_records": [
            {"symbol": s.symbol, "chat_id": s.chat_id, "last_alerted_pct": s.last_alerted_pct}
            for s in states
        ],
    }


@router.get("/clear-gain-state-today")
async def clear_gain_alert_state_today():
    """One-time helper: delete today's gain alert dedup records so the next scan sends fresh alerts."""
    import pytz
    from api.models import GainAlertState

    alert_date = datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d")
    db = SessionLocal()
    try:
        deleted = db.query(GainAlertState).filter(GainAlertState.alert_date == alert_date).delete()
        db.commit()
    finally:
        db.close()

    return {"deleted": deleted, "alert_date": alert_date, "message": "Done. Next scan will send fresh alerts."}


@router.post("/gain-alert-complete")
async def gain_alert_complete(
    body: GainAlertPayload,
    x_internal_secret: Optional[str] = Header(None),
):
    """Manual/external gain scan fallback endpoint.

    The primary scan now runs on the worker dyno via APScheduler. This endpoint
    remains for manual curl testing or external triggers.
    """
    _verify_secret(x_internal_secret)

    from api.gain_scanner import process_and_broadcast

    gainers = [g.model_dump() for g in body.gainers]
    try:
        total_new = await process_and_broadcast(gainers, body.scan_date)
    except Exception as exc:
        log.exception("gain_alert_complete processing failed: %s", exc)
        raise HTTPException(status_code=500, detail="Processing failed")

    return {"received": len(body.gainers), "new_alerts": total_new}


@router.post("/backtest-complete")
async def backtest_complete(
    body: BacktestCompletePayload,
    x_internal_secret: Optional[str] = Header(None),
):
    """Receive a backtest result from the GitHub Actions runner and store it so
    the frontend's /api/backtest/result/{job_id} polling can serve it."""
    _verify_secret(x_internal_secret)

    from api.routers.backtest import store_offloaded_result

    # Persist to DB for durability (survives future dyno restarts)
    _update_backtest_job_db(body.job_id, body.status, body.result_json, body.error)

    if body.status == "complete" and body.result_json:
        try:
            from api.schemas import BacktestResponse
            result = BacktestResponse(**json.loads(body.result_json))
            store_offloaded_result(body.job_id, result)
            log.info("Stored offloaded backtest result for job_id=%s", body.job_id)
        except Exception as e:
            log.exception("Failed to parse offloaded backtest result: %s", e)
            store_offloaded_result(body.job_id, RuntimeError(f"Result parse error: {e}"))
    else:
        store_offloaded_result(body.job_id, RuntimeError(body.error or "Backtest failed on runner"))

    return {"status": "received"}


def _update_backtest_job_db(job_id: str, status: str, result_json: Optional[str], error: Optional[str]) -> None:
    try:
        from api.models import BacktestJob
        db = SessionLocal()
        try:
            job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()
            if job:
                job.status = status
                job.completed_at = datetime.now(timezone.utc)
                job.result_json = result_json
                job.error = error
                db.commit()
                log.info("Updated backtest job %s in DB (status=%s)", job_id, status)
        finally:
            db.close()
    except Exception as exc:
        log.warning("Failed to update backtest job %s in DB: %s", job_id, exc)
