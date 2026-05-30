import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
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
_cache: dict = {
    "result": None,
    "timestamp": None,   # float epoch seconds
}
_is_computing = False
CACHE_TTL_SECONDS = int(os.getenv("PREDICTION_CACHE_TTL_SECONDS", "86400"))

# S&P 500 universe size (top ~100 liquid constituents)
_SCREENER_UNIVERSE_SIZE = 100

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


def _run_prediction_sync() -> PredictionResponse:
    """Blocking prediction logic — computes for the full universe."""
    from quantify.data.providers.yfinance_provider import YFinanceProvider
    from quantify.data.cache import ParquetCache
    from quantify.data.features import FeatureEngine
    from quantify.data.universe import get_sp500, get_sector_map
    from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=365 * 3)

    full_universe = get_sp500()
    universe = full_universe[:_SCREENER_UNIVERSE_SIZE]
    sector_map = get_sector_map()

    strat = MLReturnPredictorStrategy(universe=universe)

    log.info("Screener: fetching data for %d symbols from S&P 500…", len(universe))
    cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")
    provider = YFinanceProvider(cache=ParquetCache(cache_dir=cache_dir))
    data = provider.get_multiple(universe, start=start_dt, end=end_dt)

    if not data:
        raise ValueError("Market data provider returned empty results.")

    log.info("Screener: computing features for %d symbols…", len(data))
    required = strat.get_required_features()
    engine = FeatureEngine()
    features = engine.compute(data, required=list(required))

    enriched = {}
    for sym, raw_df in data.items():
        feat_df = features.get(sym)
        if feat_df is not None:
            enriched[sym] = raw_df.join(feat_df, how="left", rsuffix="_feat")
        else:
            enriched[sym] = raw_df

    log.info("Screener: generating signals…")
    signals = strat.generate_signals(enriched)

    longs = sorted(
        [s for s in signals if s.direction == "long"],
        key=lambda x: x.strength, reverse=True,
    )
    shorts = sorted(
        [s for s in signals if s.direction == "short"],
        key=lambda x: x.strength,
    )

    all_signals = longs + shorts

    items = []
    for s in all_signals:
        sym = s.symbol
        sector = sector_map.get(sym, "Unknown")
        pred_return = s.metadata.get("predicted_return_5d", 0.0) if s.metadata else 0.0
        explanations = s.metadata.get("explanations", []) if s.metadata else []
        items.append(PredictionItem(
            symbol=sym,
            strength=s.strength,
            side=s.direction,
            sector=sector,
            name=_get_ticker_name(sym),
            predicted_return_pct=round(float(pred_return) * 100, 2),
            explanations=explanations,
        ))

    return PredictionResponse(
        status="ok",
        date=end_dt.strftime("%Y-%m-%d"),
        signals=items,
        cached=False,
        cache_age_minutes=0.0,
        universe_size=len(universe),
        model_metrics=strat._model_metrics,
    )


def _run_and_cache_predictions(source: str = "scheduler"):
    global _is_computing, _cache
    if _is_computing and source != "api":
        log.info("Screener: prediction already running, skipping.")
        return
    _is_computing = True
    log.info("Screener: starting background prediction task...")
    try:
        result = _run_prediction_sync()
        
        # Save to database
        db = SessionLocal()
        try:
            db.query(PredictionCache).delete()
            cache_entry = PredictionCache(
                result_json=result.model_dump_json()
            )
            db.add(cache_entry)
            db.commit()
            log.info("Screener: predictions saved to DB successfully.")
        except Exception as e:
            log.error(f"Failed to save prediction cache to DB: {e}")
        finally:
            db.close()

        # Update in-memory
        _cache["result"] = result
        _cache["timestamp"] = time.time()
        
    except Exception as e:
        log.exception("Screener prediction failed in background task")
    finally:
        _is_computing = False


@router.get("/best")
async def get_best_predictions(
    background_tasks: BackgroundTasks,
    top_n: int = Query(10, ge=1, le=100, description="Number of top predictions to return"),
    sector: Optional[str] = Query(None, description="Filter by GICS sector"),
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
    
    cached_result: Optional[PredictionResponse] = _cache.get("result")
    cached_ts: Optional[float] = _cache.get("timestamp")

    cache_valid = (
        cached_result is not None
        and cached_ts is not None
        and (now - cached_ts) < CACHE_TTL_SECONDS
        and not force
    )

    if not cache_valid and not force:
        # Check DB cache
        db_cache = db.query(PredictionCache).order_by(PredictionCache.created_at.desc()).first()
        if db_cache:
            cache_age = (datetime.now(timezone.utc).replace(tzinfo=None) - db_cache.created_at).total_seconds()
            if cache_age < CACHE_TTL_SECONDS:
                try:
                    result_dict = json.loads(db_cache.result_json)
                    cached_result = PredictionResponse(**result_dict)
                    cached_ts = now - cache_age
                    _cache["result"] = cached_result
                    _cache["timestamp"] = cached_ts
                    cache_valid = True
                    log.info("Screener: loaded cache from database (age=%.1f min)", cache_age / 60)
                except Exception as e:
                    log.error(f"Failed to parse DB cache: {e}")

    if force:
        # Check if 3 minutes have passed since the last computation
        if cached_ts is not None and (now - cached_ts) < 180:
            raise HTTPException(status_code=429, detail="Please wait at least 3 minutes between manual re-runs.")

    # If the caller requested a forced re-run, run synchronously and return fresh results
    if force and not _is_computing:
        log.info("Screener: performing forced synchronous recompute (api request)...")
        try:
            result = _run_prediction_sync()

            # Save to database
            db_obj = SessionLocal()
            try:
                db_obj.query(PredictionCache).delete()
                cache_entry = PredictionCache(result_json=result.model_dump_json())
                db_obj.add(cache_entry)
                db_obj.commit()
                log.info("Screener: forced predictions saved to DB successfully.")
            except Exception as e:
                log.error(f"Failed to save forced prediction cache to DB: {e}")
            finally:
                db_obj.close()

            # Update in-memory cache
            _cache["result"] = result
            _cache["timestamp"] = time.time()

            # Apply sector filter and top_n
            filtered = result.signals
            if sector:
                filtered = [s for s in filtered if s.sector.lower() == sector.lower()]
            filtered = filtered[:top_n]

            return PredictionResponse(
                status="ok",
                date=result.date,
                signals=filtered,
                cached=False,
                cache_age_minutes=0.0,
                universe_size=result.universe_size,
                model_metrics=result.model_metrics,
            )
        except Exception as e:
            log.exception("Forced synchronous prediction failed")
            raise HTTPException(status_code=500, detail="Forced prediction failed")
    if cache_valid and cached_result is not None:
        age_minutes = round((now - cached_ts) / 60, 1) if cached_ts else 0.0
        log.info("Screener: serving from cache (age=%.1f min)", age_minutes)
        filtered = cached_result.signals
        if sector:
            filtered = [s for s in filtered if s.sector.lower() == sector.lower()]
        filtered = filtered[:top_n]
        return PredictionResponse(
            status="ok",
            date=cached_result.date,
            signals=filtered,
            cached=True,
            cache_age_minutes=age_minutes,
            universe_size=cached_result.universe_size,
            model_metrics=cached_result.model_metrics,
        )

    log.info("Screener: cache miss or force. Queuing background prediction task…")
    _is_computing = True
    background_tasks.add_task(_run_and_cache_predictions, source="api")
    
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
    _cache["result"] = None
    _cache["timestamp"] = None
    db.query(PredictionCache).delete()
    db.commit()
    return {"status": "cleared"}
