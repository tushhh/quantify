import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException

from api.schemas import PredictionResponse, PredictionItem
from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.features import FeatureEngine

router = APIRouter(prefix="/predict", tags=["predict"])
log = logging.getLogger("quantify.api.predict")

@router.get("/best", response_model=PredictionResponse)
async def get_best_predictions(top_n: int = 5):
    """Run the ensemble ML model and return the top bullish predictions."""
    try:
        provider = YFinanceProvider()
        end_dt = datetime.now(timezone.utc)
        # Use 1 year of data instead of 5 to speed up the fetch significantly
        start_dt = end_dt - timedelta(days=365)
        
        # Instantiate strategy (lazy-load to save RAM on boot)
        from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy
        strat = MLReturnPredictorStrategy()
        # Limit universe to top 30 symbols for live API speed
        universe = strat.universe[:30]
        
        # Fetch data in bulk (much faster)
        log.info(f"Fetching data for {len(universe)} symbols...")
        data = provider.get_multiple(universe, start=start_dt, end=end_dt)
                
        if not data:
            raise HTTPException(status_code=502, detail="Market data provider is currently unavailable or returned empty results.")
            
        # Compute features
        log.info("Computing features...")
        required = strat.get_required_features()
        engine = FeatureEngine()
        features = engine.compute(data, required=list(required))
        
        enriched = {}
        for sym, raw_df in data.items():
            feat_df = features.get(sym)
            if feat_df is not None:
                # Ensure indices are aligned
                enriched[sym] = raw_df.join(feat_df, how="left", rsuffix="_feat")
            else:
                enriched[sym] = raw_df
                
        # Generate signals
        log.info("Generating signals...")
        signals = strat.generate_signals(enriched)
        
        # Filter and sort LONG signals
        longs = [s for s in signals if s.side == "long"]
        longs.sort(key=lambda x: x.strength, reverse=True)
        
        items = []
        for s in longs[:top_n]:
            items.append(PredictionItem(symbol=s.symbol, strength=s.strength, side=s.side))
            
        return PredictionResponse(
            status="ok",
            date=end_dt.strftime("%Y-%m-%d"),
            signals=items
        )
    except Exception as e:
        log.exception("Prediction failed")
        raise HTTPException(status_code=500, detail="An internal server error occurred during prediction.")
