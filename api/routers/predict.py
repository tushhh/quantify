import json
import logging
import os
import time
from datetime import date, datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from api.schemas import PredictionResponse, PredictionItem

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


def update_memory_cache(mode: PredictionMode, result: PredictionResponse) -> None:
    cache_slot = _cache_bucket(mode)
    cache_slot["result"] = result
    cache_slot["timestamp"] = time.time()


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


def _fetch_screener_results_from_github() -> Optional[PredictionResponse]:
    import urllib.request
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    if not repo:
        log.warning("Screener: GITHUB_REPOSITORY not set. Cannot fetch cache.")
        return None
        
    base_url = f"https://raw.githubusercontent.com/{repo}/screener-cache"
    req = urllib.request.Request(f"{base_url}/screener_results.json")
    if token:
        req.add_header("Authorization", f"token {token}")
        
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            
        items = [
            PredictionItem(
                symbol=sig["symbol"],
                strength=sig["strength"],
                side=sig["side"],
                sector=sig["sector"],
                name=_get_ticker_name(sig["symbol"]),
                predicted_return_pct=sig.get("predicted_return_pct", 0.0),
                explanations=sig.get("explanations", []),
            )
            for sig in data["signals"]
        ]
        
        now_utc = datetime.now(timezone.utc)
        session_date = _latest_completed_session_date(now_utc)
        
        return PredictionResponse(
            status="ok",
            mode="previous_close",
            date=session_date.strftime("%Y-%m-%d"),
            signals=items,
            cached=True,
            cache_age_minutes=0.0,
            universe_size=data.get("universe_size", len(items)),
            model_metrics=data.get("model_metrics", {}),
        )
    except Exception as e:
        log.warning("Screener: Failed to fetch results from GitHub: %s", e)
        return None


@router.get("/best")
async def get_best_predictions(
    top_n: int = Query(10, ge=1, le=100, description="Number of top predictions to return"),
    sector: Optional[str] = Query(None, description="Filter by GICS sector"),
    mode: PredictionMode = Query("previous_close", description="Prediction data mode: live or previous_close"),
    force: bool = Query(False, description="Force re-run, ignoring the daily cache"),
):
    """
    Return the top bullish (and bearish) predictions by downloading from GitHub Actions cache.
    Uses a 5-minute memory cache to prevent spamming GitHub.
    """
    global _cache
    now = time.time()
    
    cache_slot = _cache_bucket(mode)
    cached_result: Optional[PredictionResponse] = cache_slot.get("result")
    cached_ts: Optional[float] = cache_slot.get("timestamp")

    cache_valid = False
    if cached_result and cached_ts:
        # Cache is valid for 5 minutes
        if now - cached_ts < 300:
            cache_valid = True

    if force or not cache_valid:
        new_result = _fetch_screener_results_from_github()
        if new_result:
            update_memory_cache(mode, new_result)
            cached_result = new_result
            cached_ts = now
            cache_valid = True

    if not cached_result:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "Prediction cache is currently unavailable. The background cron job may still be initializing."}
        )

    age_minutes = round((now - cached_ts) / 60, 1) if cached_ts else 0.0
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


@router.get("/sectors", response_model=list[str])
async def get_prediction_sectors():
    """Return the list of GICS sectors available in the screener universe."""
    from quantify.data.universe import Universe, get_sector_map, get_russell1000
    sector_map = get_sector_map()
    
    try:
        universe = Universe.from_wikipedia().tickers[:_SCREENER_UNIVERSE_SIZE]
    except Exception:
        universe = get_russell1000()[:_SCREENER_UNIVERSE_SIZE]
        
    sectors = sorted({sector_map.get(t, "Unknown") for t in universe if sector_map.get(t, "Unknown") != "Unknown"})
    return sectors


@router.delete("/cache")
async def clear_prediction_cache():
    """Clear the prediction memory cache (admin use). Next request will fetch from GitHub."""
    global _cache
    _cache["live"] = {"result": None, "timestamp": None}
    _cache["previous_close"] = {"result": None, "timestamp": None}
    return {"status": "cleared"}
