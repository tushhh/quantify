"""
Quantify FastAPI Backend
========================
Serves the Quantify trading system as a REST API for the web front-end.
"""

from __future__ import annotations

import logging
import os
import sys

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Bulletproof path injection for Heroku
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from contextlib import asynccontextmanager  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402

from api.routers import backtest, risk, strategies, universe, predict, trades, auth, utils, internal  # noqa: E402
from api.database import engine, ensure_trade_columns, ensure_user_columns, ensure_gain_alert_columns  # noqa: E402
from api import models  # noqa: E402
from api.telegram_bot import check_alerts_loop  # noqa: E402
from api.gain_scanner import run_gain_scan  # noqa: E402

@asynccontextmanager
async def lifespan(app: FastAPI):
    from api.telegram_bot import start_telegram_bot, stop_telegram_bot
    from api.prediction_bot import start_prediction_bot, stop_prediction_bot
    
    # Initialize DB tables only if they don't exist. SQLAlchemy's checkfirst=True
    # (default) makes this a no-op on existing schema, so it's safe to call at startup.
    models.Base.metadata.create_all(bind=engine)
    ensure_trade_columns()
    ensure_user_columns()
    ensure_gain_alert_columns()
    
    # Only run telegram bot on worker dyno, not web dyno (prevents polling conflicts on Heroku)
    # unless FORCE_RUN_BOTS is explicitly set.
    dyno_type = os.getenv("DYNO", "local")
    force_run = os.getenv("FORCE_RUN_BOTS", "").lower() in ("true", "1", "yes")
    is_web_dyno = dyno_type.startswith("web.") and not force_run
    
    if not is_web_dyno:
        log.info(f"Starting Telegram bot polling on dyno: {dyno_type}")
        # Start telegram bot polling
        await start_telegram_bot()
        await start_prediction_bot()
    else:
        log.info("Skipping Telegram bot polling on web dyno (Heroku). Run on worker dyno instead.")
    
    # Start the background task for telegram alerts only on worker dynos
    scheduler = AsyncIOScheduler()
    if not is_web_dyno:
        # Every 10 minutes during US market hours (9 AM–4:30 PM ET, Mon–Fri)
        scheduler.add_job(
            check_alerts_loop,
            'cron',
            day_of_week='mon-fri',
            hour='9-16',
            minute='*/10',
            timezone='America/New_York',
        )
        # Every 3 hours for overnight/weekend coverage (hold expiry, etc.)
        scheduler.add_job(check_alerts_loop, 'interval', hours=3)
        scheduler.add_job(
            run_gain_scan,
            'cron',
            day_of_week='mon-fri',
            hour='9-16',
            minute='*/7',
            timezone='America/New_York',
        )
        scheduler.start()
    else:
        # On web dyno, schedule the ML predictions to run at 4:00 AM UTC daily
        from api.routers.predict import _run_and_cache_predictions
        scheduler.add_job(_run_and_cache_predictions, 'cron', hour=4, minute=0)
        scheduler.start()
    
    yield
    
    if scheduler.running:
        scheduler.shutdown()
    if not is_web_dyno:
        await stop_telegram_bot()
        await stop_prediction_bot()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
log = logging.getLogger("quantify.api")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Quantify API",
    description="Quantitative trading system – backtesting, strategy exploration and risk management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS – allow the Vercel frontend and local dev
# ---------------------------------------------------------------------------
_frontend_url = os.getenv("FRONTEND_URL", "")
# Support multiple comma-separated URLs and handle trailing slashes
frontend_urls = [
    url.strip().rstrip("/") 
    for url in _frontend_url.split(",") 
    if url.strip()
]

ALLOWED_ORIGINS = list(dict.fromkeys([
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    *frontend_urls
]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Allow any HTTPS origin — safe for Bearer-token auth (no cookies = no CSRF risk).
    # Explicit origins in ALLOWED_ORIGINS cover localhost and the FRONTEND_URL env var.
    allow_origin_regex=r"https://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(universe.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(utils.router, prefix="/api")
app.include_router(internal.router, prefix="/api")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"message": "Quantify API – see /docs for usage"}
