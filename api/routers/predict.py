import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException

from api.schemas import PredictionResponse, PredictionItem

router = APIRouter(prefix="/predict", tags=["predict"])
log = logging.getLogger("quantify.api.predict")


def _run_prediction_sync(top_n: int) -> PredictionResponse:
    """Blocking prediction logic — run in a thread pool from the async route."""
    from quantify.data.providers.yfinance_provider import YFinanceProvider
    from quantify.data.features import FeatureEngine
    from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=365)

    strat = MLReturnPredictorStrategy()
    universe = strat.universe[:30]

    log.info("Fetching data for %d symbols…", len(universe))
    provider = YFinanceProvider()
    data = provider.get_multiple(universe, start=start_dt, end=end_dt)

    if not data:
        raise ValueError("Market data provider returned empty results.")

    log.info("Computing features…")
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

    log.info("Generating signals…")
    signals = strat.generate_signals(enriched)

    longs = sorted(
        [s for s in signals if s.direction == "long"],
        key=lambda x: x.strength,
        reverse=True,
    )

    items = [
        PredictionItem(symbol=s.symbol, strength=s.strength, side=s.direction)
        for s in longs[:top_n]
    ]
    return PredictionResponse(
        status="ok",
        date=end_dt.strftime("%Y-%m-%d"),
        signals=items,
    )


@router.get("/best", response_model=PredictionResponse)
async def get_best_predictions(top_n: int = 5):
    """Run the ensemble ML model and return the top bullish predictions."""
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _run_prediction_sync, top_n)
        return result
    except Exception as e:
        log.exception("Prediction failed")
        raise HTTPException(status_code=500, detail="An internal server error occurred during prediction.")
