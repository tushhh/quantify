import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from api.schemas import PredictionResponse, PredictionItem

router = APIRouter(prefix="/predict", tags=["predict"])
log = logging.getLogger("quantify.api.predict")

# ---------------------------------------------------------------------------
# 24-hour in-memory cache
# ---------------------------------------------------------------------------
_cache: dict = {
    "result": None,
    "timestamp": None,   # float epoch seconds
}
CACHE_TTL_SECONDS = 24 * 3600  # 24 hours

# Limit screener universe to top 60 most liquid tickers for speed
# (Ensures API responds well within Heroku's 30s timeout)
_SCREENER_UNIVERSE_SIZE = 60

# ---------------------------------------------------------------------------
# Ticker name lookup (top 150 most common tickers)
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
    "HCA": "HCA Healthcare", "MCK": "McKesson Corp.", "AMZN": "Amazon.com Inc.",
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


def _run_prediction_sync(top_n: int, sector_filter: Optional[str] = None) -> PredictionResponse:
    """Blocking prediction logic — run in a thread pool from the async route."""
    from quantify.data.providers.yfinance_provider import YFinanceProvider
    from quantify.data.features import FeatureEngine
    from quantify.data.universe import get_russell1000, get_sector_map
    from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=365 * 3)

    # Use Russell 1000 universe, capped at screener size for speed
    full_universe = get_russell1000()
    universe = full_universe[:_SCREENER_UNIVERSE_SIZE]
    sector_map = get_sector_map()

    strat = MLReturnPredictorStrategy(universe=universe)

    log.info("Screener: fetching data for %d symbols from Russell 1000…", len(universe))
    provider = YFinanceProvider()
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

    # Sort longs by strength desc, shorts by strength asc (most negative first)
    longs = sorted(
        [s for s in signals if s.direction == "long"],
        key=lambda x: x.strength, reverse=True,
    )
    shorts = sorted(
        [s for s in signals if s.direction == "short"],
        key=lambda x: x.strength,
    )

    all_signals = longs + shorts

    # Build prediction items with enriched metadata
    items = []
    for s in all_signals:
        sym = s.symbol
        sector = sector_map.get(sym, "Unknown")
        # Apply sector filter if provided
        if sector_filter and sector.lower() != sector_filter.lower():
            continue
        pred_return = s.metadata.get("predicted_return_5d", 0.0) if s.metadata else 0.0
        items.append(PredictionItem(
            symbol=sym,
            strength=s.strength,
            side=s.direction,
            sector=sector,
            name=_get_ticker_name(sym),
            predicted_return_pct=round(float(pred_return) * 100, 2),
        ))
        if len(items) >= top_n:
            break

    return PredictionResponse(
        status="ok",
        date=end_dt.strftime("%Y-%m-%d"),
        signals=items,
        cached=False,
        cache_age_minutes=0.0,
        universe_size=len(universe),
    )


@router.get("/best", response_model=PredictionResponse)
async def get_best_predictions(
    top_n: int = Query(10, ge=1, le=50, description="Number of top predictions to return"),
    sector: Optional[str] = Query(None, description="Filter by GICS sector"),
    force: bool = Query(False, description="Force re-run, ignoring the daily cache"),
):
    """
    Run the ensemble ML model and return the top bullish (and bearish) predictions.

    Results are cached for 24 hours. Pass `?force=true` to bypass the cache and
    recompute fresh predictions (takes 2–5 minutes).
    """
    now = time.time()
    cached_result: Optional[PredictionResponse] = _cache.get("result")
    cached_ts: Optional[float] = _cache.get("timestamp")

    # Check if cache is valid
    cache_valid = (
        cached_result is not None
        and cached_ts is not None
        and (now - cached_ts) < CACHE_TTL_SECONDS
        and not force
    )

    if cache_valid:
        age_minutes = round((now - cached_ts) / 60, 1)
        log.info("Screener: serving from cache (age=%.1f min)", age_minutes)
        # Apply on-the-fly filters to cached result
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
        )

    # Run fresh prediction in thread pool (blocking ML work)
    log.info("Screener: running fresh prediction (force=%s)…", force)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _run_prediction_sync, 50, None)
        # Cache the full unfiltered result
        _cache["result"] = result
        _cache["timestamp"] = time.time()

        # Apply filters to the returned payload
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
        )
    except Exception as e:
        log.exception("Screener prediction failed")
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}. Please try again later.",
        )


@router.get("/sectors", response_model=list[str])
async def get_prediction_sectors():
    """Return the list of GICS sectors available in the screener universe."""
    from quantify.data.universe import get_sector_map, get_russell1000
    sector_map = get_sector_map()
    universe = get_russell1000()[:_SCREENER_UNIVERSE_SIZE]
    sectors = sorted({sector_map.get(t, "Unknown") for t in universe if sector_map.get(t, "Unknown") != "Unknown"})
    return sectors


@router.delete("/cache")
async def clear_prediction_cache():
    """Clear the prediction cache (admin use). Next request will recompute."""
    _cache["result"] = None
    _cache["timestamp"] = None
    return {"status": "cleared"}
