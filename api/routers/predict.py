import json
import logging
import os
import time
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.schemas import PredictionResponse, PredictionItem
from api.database import get_db, SessionLocal
from api.models import PredictionCache

router = APIRouter(prefix="/predict", tags=["predict"])
log = logging.getLogger("quantify.api.predict")

# ---------------------------------------------------------------------------
# 24-hour in-memory cache
# ---------------------------------------------------------------------------
PredictionMode = Literal["live", "previous_close"]

_cache: dict[PredictionMode, dict[str, object | None]] = {
    "live": {"result": None, "timestamp": None},
    "previous_close": {"result": None, "timestamp": None},
}
_is_computing = False
_LIVE_CACHE_TTL_SECONDS = int(os.getenv("PREDICTION_LIVE_CACHE_TTL_SECONDS", "300"))
_PREVIOUS_CLOSE_CACHE_TTL_SECONDS = int(os.getenv("PREDICTION_PREVIOUS_CLOSE_CACHE_TTL_SECONDS", "604800"))

# Full S&P 500 universe — inference is fast since model is pre-trained
_SCREENER_UNIVERSE_SIZE = 500


def _should_force_run_synchronously() -> bool:
    override = os.getenv("PREDICTION_FORCE_SYNC")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes", "on"}

    dyno_type = os.getenv("DYNO", "")
    return not dyno_type.startswith("web.")

# ---------------------------------------------------------------------------
# Ticker name lookup (common tickers)
# ---------------------------------------------------------------------------
_TICKER_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "NVDA": "NVIDIA Corp.",
    "GOOGL": "Alphabet Inc.", "GOOG": "Alphabet Inc. (C)", "META": "Meta Platforms",
    "AMZN": "Amazon.com Inc.", "TSLA": "Tesla Inc.", "AVGO": "Broadcom Inc.",
    "ORCL": "Oracle Corp.", "CRM": "Salesforce Inc.", "AMD": "Advanced Micro Devices",
    "INTC": "Intel Corp.", "QCOM": "Qualcomm Inc.", "TXN": "Texas Instruments",
    "MU": "Micron Technology", "AMAT": "Applied Materials", "LRCX": "Lam Research",
    "ADI": "Analog Devices", "KLAC": "KLA Corp.", "MRVL": "Marvell Technology",
    "NOW": "ServiceNow Inc.", "SNPS": "Synopsys Inc.", "CDNS": "Cadence Design",
    "FTNT": "Fortinet Inc.", "PANW": "Palo Alto Networks", "IBM": "IBM Corp.",
    "CSCO": "Cisco Systems", "ANET": "Arista Networks", "CRWD": "CrowdStrike Holdings",
    "ZS": "Zscaler Inc.", "OKTA": "Okta Inc.", "PAYC": "Paycom Software",
    "PCTY": "Paylocity Holding", "MANH": "Manhattan Associates",
    "HPQ": "HP Inc.", "HPE": "Hewlett Packard Enterprise", "DELL": "Dell Technologies",
    "JPM": "JPMorgan Chase", "V": "Visa Inc.", "MA": "Mastercard Inc.",
    "BAC": "Bank of America", "WFC": "Wells Fargo", "GS": "Goldman Sachs",
    "MS": "Morgan Stanley", "AXP": "American Express", "BLK": "BlackRock Inc.",
    "SPGI": "S&P Global Inc.", "MCO": "Moody's Corp.", "ICE": "Intercontinental Exchange",
    "CME": "CME Group Inc.", "COF": "Capital One", "SYF": "Synchrony Financial",
    "DFS": "Discover Financial", "ALLY": "Ally Financial", "BRK-B": "Berkshire Hathaway",
    "PRU": "Prudential Financial", "MET": "MetLife Inc.", "AFL": "Aflac Inc.",
    "ALL": "Allstate Corp.", "PGR": "Progressive Corp.", "CB": "Chubb Ltd.",
    "UNH": "UnitedHealth Group", "JNJ": "Johnson & Johnson", "LLY": "Eli Lilly",
    "ABBV": "AbbVie Inc.", "MRK": "Merck & Co.", "TMO": "Thermo Fisher Scientific",
    "ABT": "Abbott Laboratories", "DHR": "Danaher Corp.", "MDT": "Medtronic plc",
    "SYK": "Stryker Corp.", "ISRG": "Intuitive Surgical", "EW": "Edwards Lifesciences",
    "DXCM": "DexCom Inc.", "REGN": "Regeneron Pharmaceuticals", "VRTX": "Vertex Pharma.",
    "GILD": "Gilead Sciences", "AMGN": "Amgen Inc.", "BMY": "Bristol-Myers Squibb",
    "PFE": "Pfizer Inc.", "MRNA": "Moderna Inc.", "CVS": "CVS Health",
    "CI": "Cigna Group", "HUM": "Humana Inc.", "ELV": "Elevance Health",
    "HCA": "HCA Healthcare", "MCK": "McKesson Corp.",
    "HD": "Home Depot Inc.", "MCD": "McDonald's Corp.", "NKE": "Nike Inc.",
    "SBUX": "Starbucks Corp.", "TGT": "Target Corp.", "LOW": "Lowe's Companies",
    "BKNG": "Booking Holdings", "MAR": "Marriott International", "HLT": "Hilton Worldwide",
    "ABNB": "Airbnb Inc.", "UBER": "Uber Technologies", "DASH": "DoorDash Inc.",
    "CMG": "Chipotle Mexican Grill", "YUM": "Yum! Brands", "DRI": "Darden Restaurants",
    "ROST": "Ross Stores", "TJX": "TJX Companies", "BURL": "Burlington Stores",
    "FIVE": "Five Below", "DG": "Dollar General", "DLTR": "Dollar Tree",
    "AZO": "AutoZone Inc.", "ORLY": "O'Reilly Automotive", "KMX": "CarMax Inc.",
    "WMT": "Walmart Inc.", "PG": "Procter & Gamble", "KO": "Coca-Cola Co.",
    "PEP": "PepsiCo Inc.", "COST": "Costco Wholesale", "MDLZ": "Mondelez Int'l",
    "CL": "Colgate-Palmolive", "MO": "Altria Group", "PM": "Philip Morris Int'l",
    "KHC": "Kraft Heinz", "GIS": "General Mills", "K": "Kellogg Co.",
    "TSN": "Tyson Foods", "SYY": "Sysco Corp.", "KR": "Kroger Co.",
    "XOM": "Exxon Mobil", "CVX": "Chevron Corp.", "COP": "ConocoPhillips",
    "EOG": "EOG Resources", "SLB": "Schlumberger Ltd.", "PSX": "Phillips 66",
    "MPC": "Marathon Petroleum", "VLO": "Valero Energy", "OXY": "Occidental Petroleum",
    "HAL": "Halliburton Co.", "DVN": "Devon Energy", "HES": "Hess Corp.",
    "GE": "GE Aerospace", "CAT": "Caterpillar Inc.", "DE": "Deere & Company",
    "HON": "Honeywell Int'l", "RTX": "RTX Corp.", "LMT": "Lockheed Martin",
    "NOC": "Northrop Grumman", "GD": "General Dynamics", "BA": "Boeing Co.",
    "UPS": "United Parcel Service", "FDX": "FedEx Corp.", "NSC": "Norfolk Southern",
    "UNP": "Union Pacific", "CSX": "CSX Corp.", "ODFL": "Old Dominion Freight",
    "NFLX": "Netflix Inc.", "DIS": "Walt Disney Co.", "T": "AT&T Inc.",
    "VZ": "Verizon Communications", "CMCSA": "Comcast Corp.", "TMUS": "T-Mobile US",
    "CHTR": "Charter Communications", "EA": "Electronic Arts", "TTWO": "Take-Two Interactive",
    "SNAP": "Snap Inc.", "PINS": "Pinterest Inc.", "MTCH": "Match Group",
    "LIN": "Linde plc", "APD": "Air Products", "SHW": "Sherwin-Williams",
    "FCX": "Freeport-McMoRan", "NEM": "Newmont Corp.", "GOLD": "Barrick Gold",
    "ECL": "Ecolab Inc.", "ALB": "Albemarle Corp.", "NUE": "Nucor Corp.",
    "AMT": "American Tower", "PLD": "Prologis Inc.", "CCI": "Crown Castle",
    "EQIX": "Equinix Inc.", "SPG": "Simon Property Group", "O": "Realty Income",
    "PSA": "Public Storage", "EQR": "Equity Residential", "AVB": "AvalonBay Communities",
    "NEE": "NextEra Energy", "SO": "Southern Company", "DUK": "Duke Energy",
    "AEP": "American Electric Power", "SRE": "Sempra Energy", "D": "Dominion Energy",
    "EXC": "Exelon Corp.", "XEL": "Xcel Energy", "WEC": "WEC Energy Group",
}


def _get_ticker_name(symbol: str) -> str:
    return _TICKER_NAMES.get(symbol, symbol)


def _cache_bucket(mode: PredictionMode) -> dict[str, object | None]:
    return _cache[mode]


def _cache_ttl_seconds(mode: PredictionMode) -> int:
    return _LIVE_CACHE_TTL_SECONDS if mode == "live" else _PREVIOUS_CLOSE_CACHE_TTL_SECONDS


def _previous_weekday(check_date: date) -> date:
    current = check_date
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def _latest_completed_session_date(now_utc: datetime) -> date:
    """Return the most recent completed NYSE trading session date."""
    current_date = now_utc.astimezone(timezone.utc).date()

    try:
        import pandas_market_calendars as mcal  # type: ignore[import]
    except Exception:
        return current_date if current_date.weekday() < 5 else _previous_weekday(current_date)

    try:
        nyse = mcal.get_calendar("NYSE")
        schedule = nyse.schedule(
            start_date=str(current_date - timedelta(days=14)),
            end_date=str(current_date),
        )
        if schedule.empty:
            return current_date if current_date.weekday() < 5 else _previous_weekday(current_date)

        session_dates = [ts.date() for ts in schedule.index]
        if current_date in session_dates:
            close_ts = schedule.loc[schedule.index.date == current_date, "market_close"].iloc[0]
            close_utc = close_ts.tz_convert(timezone.utc) if getattr(close_ts, "tzinfo", None) else close_ts.replace(tzinfo=timezone.utc)
            if now_utc >= close_utc:
                return current_date

        for session_date in reversed(session_dates):
            if session_date < current_date:
                return session_date

        return session_dates[0]
    except Exception as exc:
        log.warning("Screener: failed to resolve NYSE session date (%s); falling back to weekday logic.", exc)
        return current_date if current_date.weekday() < 5 else _previous_weekday(current_date)


def _resolve_prediction_window(mode: PredictionMode, now_utc: datetime) -> tuple[date, datetime, datetime]:
    if mode == "live":
        session_date = now_utc.astimezone(timezone.utc).date()
        if session_date.weekday() >= 5:
            session_date = _previous_weekday(session_date)
        end_dt = now_utc
    else:
        session_date = _latest_completed_session_date(now_utc)
        end_dt = datetime.combine(session_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    start_dt = end_dt - timedelta(days=365 * 3)
    return session_date, start_dt, end_dt


def _cache_payload(mode: PredictionMode, result: PredictionResponse) -> str:
    return json.dumps({"mode": mode, "result": result.model_dump()})


def _persist_prediction_cache(mode: PredictionMode, result: PredictionResponse) -> None:
    db = SessionLocal()
    try:
        existing_rows = db.query(PredictionCache).order_by(PredictionCache.created_at.desc()).all()
        for row in existing_rows:
            try:
                payload = json.loads(row.result_json)
            except Exception:
                continue

            cached_mode = payload.get("mode", "previous_close")
            if cached_mode == mode:
                db.delete(row)

        db.add(PredictionCache(result_json=_cache_payload(mode, result)))
        db.commit()
        log.info("Screener: %s predictions saved to DB successfully.", mode)
    except Exception as e:
        log.error("Failed to save %s prediction cache to DB: %s", mode, e)
        db.rollback()
    finally:
        db.close()


def _load_prediction_cache(db: Session, mode: PredictionMode) -> tuple[Optional[PredictionResponse], Optional[float]]:
    db_rows = db.query(PredictionCache).order_by(PredictionCache.created_at.desc()).all()
    for db_cache in db_rows:
        try:
            payload = json.loads(db_cache.result_json)
        except Exception:
            continue

        cached_mode = payload.get("mode", "previous_close")
        if cached_mode != mode:
            continue

        result_dict = payload.get("result", payload)
        try:
            cached_result = PredictionResponse(**result_dict)
        except Exception:
            continue

        cached_ts = db_cache.created_at.replace(tzinfo=timezone.utc).timestamp() if db_cache.created_at.tzinfo is None else db_cache.created_at.timestamp()
        return cached_result, cached_ts

    return None, None


def _cache_is_valid(mode: PredictionMode, cached_result: Optional[PredictionResponse], cached_ts: Optional[float], now: float, now_utc: datetime) -> bool:
    if cached_result is None or cached_ts is None:
        return False

    if mode == "live":
        if now - cached_ts >= _cache_ttl_seconds(mode):
            return False
        return cached_result.date == now_utc.astimezone(timezone.utc).date().isoformat()

    session_date = _latest_completed_session_date(now_utc)
    if now - cached_ts >= _cache_ttl_seconds(mode):
        return False
    return cached_result.date == session_date.isoformat()


def _download_latest_model() -> bool:
    import urllib.request
    import os
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        log.info("Screener: GITHUB_REPOSITORY not set. Cannot fetch model from cloud.")
        return False
        
    log.info(f"Screener: Downloading latest ML model from GitHub ({repo})...")
    
    token = os.getenv("GITHUB_TOKEN")
    base_url = f"https://raw.githubusercontent.com/{repo}/model-cache"
    
    os.makedirs("models", exist_ok=True)
    try:
        req_model = urllib.request.Request(f"{base_url}/ml_return_predictor.joblib")
        if token:
            req_model.add_header("Authorization", f"token {token}")
        with urllib.request.urlopen(req_model) as response, open("models/ml_return_predictor.joblib", 'wb') as out_file:
            out_file.write(response.read())
            
        req_meta = urllib.request.Request(f"{base_url}/ml_return_predictor_meta.json")
        if token:
            req_meta.add_header("Authorization", f"token {token}")
        with urllib.request.urlopen(req_meta) as response, open("models/ml_return_predictor_meta.json", 'wb') as out_file:
            out_file.write(response.read())
            
        return True
    except Exception as e:
        log.warning(f"Screener: Failed to download model from GitHub: {e}")
        return False


def _run_prediction_sync(mode: PredictionMode = "previous_close") -> PredictionResponse:
    """Blocking prediction logic — computes for the full universe."""
    from quantify.data.universe import get_sp500
    from quantify.screener import run_screener

    now_utc = datetime.now(timezone.utc)
    session_date, _start_dt, end_dt = _resolve_prediction_window(mode, now_utc)

    # Ensure we have the latest model downloaded from GitHub before starting
    _download_latest_model()

    universe = get_sp500()[:_SCREENER_UNIVERSE_SIZE]
    cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")

    result = run_screener(universe, end_dt=end_dt, cache_dir=cache_dir)

    items = [
        PredictionItem(
            symbol=sig["symbol"],
            strength=sig["strength"],
            side=sig["side"],
            sector=sig["sector"],
            name=_get_ticker_name(sig["symbol"]),
            predicted_return_pct=sig["predicted_return_pct"],
            explanations=sig["explanations"],
        )
        for sig in result["signals"]
    ]

    return PredictionResponse(
        status="ok",
        mode=mode,
        date=session_date.strftime("%Y-%m-%d"),
        signals=items,
        cached=False,
        cache_age_minutes=0.0,
        universe_size=result["universe_size"],
        model_metrics=result["model_metrics"],
    )


def _run_and_cache_predictions(source: str = "scheduler", mode: PredictionMode = "previous_close"):
    global _is_computing, _cache
    if _is_computing and source != "api":
        log.info("Screener: prediction already running, skipping.")
        return
    _is_computing = True
    log.info("Screener: starting background prediction task for mode=%s...", mode)
    try:
        result = _run_prediction_sync(mode=mode)

        _persist_prediction_cache(mode, result)

        # Update in-memory
        cache_slot = _cache_bucket(mode)
        cache_slot["result"] = result
        cache_slot["timestamp"] = time.time()
        
        # Broadcast prediction signals to subscribed Telegram chats/channels
        try:
            import asyncio
            from api.prediction_bot import broadcast_predictions
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(broadcast_predictions(result))
            except RuntimeError:
                asyncio.run(broadcast_predictions(result))
        except Exception as e:
            log.error("Failed to broadcast predictions to Telegram: %s", e)
            
    except Exception:
        log.exception("Screener prediction failed in background task")
    finally:
        _is_computing = False


@router.get("/best")
async def get_best_predictions(
    background_tasks: BackgroundTasks,
    top_n: int = Query(10, ge=1, le=100, description="Number of top predictions to return"),
    sector: Optional[str] = Query(None, description="Filter by GICS sector"),
    mode: PredictionMode = Query("previous_close", description="Prediction data mode: live or previous_close"),
    force: bool = Query(False, description="Force re-run, ignoring the daily cache"),
    db: Session = Depends(get_db)
):
    """
    Run the ensemble ML model and return the top bullish (and bearish) predictions.
    Uses a 24-hour database cache. If missing, runs as a background task and returns 202.
    """
    global _is_computing, _cache
    
    if _is_computing:
        return JSONResponse(
            status_code=202,
            content={"status": "computing", "message": "Models are training in the background. Please check back in a few minutes."}
        )

    now = time.time()
    
    cache_slot = _cache_bucket(mode)
    cached_result: Optional[PredictionResponse] = cache_slot.get("result")  # type: ignore[assignment]
    cached_ts: Optional[float] = cache_slot.get("timestamp")  # type: ignore[assignment]

    cache_valid = _cache_is_valid(mode, cached_result, cached_ts, now, datetime.now(timezone.utc)) and not force

    if not cache_valid and not force:
        db_cache_result, db_cache_ts = _load_prediction_cache(db, mode)
        if db_cache_result is not None and _cache_is_valid(mode, db_cache_result, db_cache_ts, now, datetime.now(timezone.utc)):
            cached_result = db_cache_result
            cached_ts = db_cache_ts
            cache_slot["result"] = cached_result
            cache_slot["timestamp"] = cached_ts
            cache_valid = True
            cache_age = (now - cached_ts) / 60 if cached_ts else 0.0
            log.info("Screener: loaded %s cache from database (age=%.1f min)", mode, cache_age)

    if force:
        # Check if 3 minutes have passed since the last computation
        if cached_ts is not None and (now - cached_ts) < 180:
            raise HTTPException(status_code=429, detail="Please wait at least 3 minutes between manual re-runs.")

    # If the caller requested a forced re-run, run synchronously on local/dev workers,
    # but queue work on Heroku web dynos to avoid request timeouts.
    if force and not _is_computing and _should_force_run_synchronously():
        log.info("Screener: performing forced synchronous recompute (api request, mode=%s)...", mode)
        try:
            result = _run_prediction_sync(mode=mode)

            _persist_prediction_cache(mode, result)

            # Update in-memory cache
            cache_slot["result"] = result
            cache_slot["timestamp"] = time.time()

            # Apply sector filter and top_n
            filtered = result.signals
            if sector:
                filtered = [s for s in filtered if s.sector.lower() == sector.lower()]
            filtered = filtered[:top_n]

            return PredictionResponse(
                status="ok",
                mode=mode,
                date=result.date,
                signals=filtered,
                cached=False,
                cache_age_minutes=0.0,
                universe_size=result.universe_size,
                model_metrics=result.model_metrics,
            )
        except Exception:
            log.exception("Forced synchronous prediction failed")
            raise HTTPException(status_code=500, detail="Forced prediction failed")
    if force and not _is_computing:
        log.info("Screener: forcing async recompute on web dyno to avoid timeout... mode=%s", mode)
        _is_computing = True
        background_tasks.add_task(_run_and_cache_predictions, source="api", mode=mode)

        return JSONResponse(
            status_code=202,
            content={"status": "computing", "message": "Model training started. Please check back in a few minutes."}
        )
    if cache_valid and cached_result is not None:
        age_minutes = round((now - cached_ts) / 60, 1) if cached_ts else 0.0
        log.info("Screener: serving from cache (age=%.1f min)", age_minutes)
        filtered = cached_result.signals
        if sector:
            filtered = [s for s in filtered if s.sector.lower() == sector.lower()]
        filtered = filtered[:top_n]
        return PredictionResponse(
            status="ok",
            mode=mode,
            date=cached_result.date,
            signals=filtered,
            cached=True,
            cache_age_minutes=age_minutes,
            universe_size=cached_result.universe_size,
            model_metrics=cached_result.model_metrics,
        )

    log.info("Screener: cache miss or force. Queuing background prediction task… mode=%s", mode)
    _is_computing = True
    background_tasks.add_task(_run_and_cache_predictions, source="api", mode=mode)
    
    return JSONResponse(
        status_code=202,
        content={"status": "computing", "message": "Model training started. Please check back in a few minutes."}
    )


@router.get("/sectors", response_model=list[str])
async def get_prediction_sectors():
    """Return the list of GICS sectors available in the screener universe."""
    from quantify.data.universe import get_sector_map, get_sp500
    sector_map = get_sector_map()
    universe = get_sp500()[:_SCREENER_UNIVERSE_SIZE]
    sectors = sorted({sector_map.get(t, "Unknown") for t in universe if sector_map.get(t, "Unknown") != "Unknown"})
    return sectors


@router.delete("/cache")
async def clear_prediction_cache(db: Session = Depends(get_db)):
    """Clear the prediction cache (admin use). Next request will recompute."""
    global _cache
    _cache["live"] = {"result": None, "timestamp": None}
    _cache["previous_close"] = {"result": None, "timestamp": None}
    db.query(PredictionCache).delete()
    db.commit()
    return {"status": "cleared"}
