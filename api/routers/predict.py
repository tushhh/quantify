import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException

from api.schemas import PredictionResponse, PredictionItem
from quantify.data.providers.yfinance_provider import YFinanceProvider
from quantify.data.features import FeatureEngine
from quantify.strategy.ml_return_predictor import MLReturnPredictorStrategy

router = APIRouter(prefix="/predict", tags=["predict"])
log = logging.getLogger("quantify.api.predict")

@router.get("/best", response_model=PredictionResponse)
async def get_best_predictions(top_n: int = 5):
    """Run the ensemble ML model and return the top bullish predictions."""
    try:
        provider = YFinanceProvider()
        end_dt = datetime.now(timezone.utc)
        # Use 5 years of data as configured in the CLI
        start_dt = end_dt - timedelta(days=1825)
        
        # Instantiate strategy (default universe)
        strat = MLReturnPredictorStrategy()
        universe = strat.universe
        
        # Fetch data
        data = {}
        for symbol in universe:
            df = provider.get_bars(symbol, start=start_dt, end=end_dt)
            if df is not None and not df.empty:
                data[symbol] = df
                
        if not data:
            raise HTTPException(status_code=502, detail="Failed to fetch market data")
            
        # Compute features
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
                
        # Generate signals
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
        raise HTTPException(status_code=500, detail=str(e))
