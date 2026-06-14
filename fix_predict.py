import re

with open('api/routers/predict.py', 'r') as f:
    content = f.read()

# 1. Replace imports (Remove BackgroundTasks and Session)
content = re.sub(
    r'from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends\nfrom fastapi.responses import JSONResponse\nfrom sqlalchemy.orm import Session\n\nfrom api.schemas import PredictionResponse, PredictionItem\nfrom api.database import get_db, SessionLocal\nfrom api.models import PredictionCache',
    'from fastapi import APIRouter, HTTPException, Query\nfrom fastapi.responses import JSONResponse\n\nfrom api.schemas import PredictionResponse, PredictionItem',
    content
)

# 2. Replace _cache_payload up to _download_latest_model with update_memory_cache
content = re.sub(
    r'def _cache_payload.*?def _download_latest_model',
    'def update_memory_cache(mode: PredictionMode, result: PredictionResponse) -> None:\n    cache_slot = _cache_bucket(mode)\n    cache_slot["result"] = result\n    cache_slot["timestamp"] = time.time()\n\n\ndef _download_latest_model',
    content,
    flags=re.DOTALL
)

# 3. Replace _run_prediction_sync up to clear_prediction_cache with our new fetch_screener logic and get_best_predictions
new_logic = '''def _fetch_screener_results_from_github() -> Optional[PredictionResponse]:
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


@router.get("/sectors", response_model=list[str])'''

content = re.sub(
    r'def _run_prediction_sync.*?@router\.get\("/sectors", response_model=list\[str\]\)',
    new_logic,
    content,
    flags=re.DOTALL
)

# 4. Fix clear_prediction_cache
content = re.sub(
    r'@router\.delete\("/cache"\)\nasync def clear_prediction_cache\(db: Session = Depends\(get_db\)\):\n    """Clear the prediction cache \(admin use\)\. Next request will recompute\."""\n    global _cache\n    _cache\["live"\] = {"result": None, "timestamp": None}\n    _cache\["previous_close"\] = {"result": None, "timestamp": None}\n    db\.query\(PredictionCache\)\.delete\(\)\n    db\.commit\(\)\n    return {"status": "cleared"}',
    '@router.delete("/cache")\nasync def clear_prediction_cache():\n    """Clear the prediction memory cache (admin use). Next request will fetch from GitHub."""\n    global _cache\n    _cache["live"] = {"result": None, "timestamp": None}\n    _cache["previous_close"] = {"result": None, "timestamp": None}\n    return {"status": "cleared"}',
    content,
    flags=re.DOTALL
)

with open('api/routers/predict.py', 'w') as f:
    f.write(content)
