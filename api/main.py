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

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from api.routers import backtest, risk, strategies, universe, predict, trades, auth, utils
from api.database import engine, ensure_trade_columns, ensure_user_columns
from api import models
from api.telegram_bot import check_alerts_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    from api.telegram_bot import start_telegram_bot, stop_telegram_bot
    
    # Initialize DB tables only if they don't exist. SQLAlchemy's checkfirst=True
    # (default) makes this a no-op on existing schema, so it's safe to call at startup.
    models.Base.metadata.create_all(bind=engine)
    ensure_trade_columns()
    ensure_user_columns()
    
    # Only run telegram bot on worker dyno, not web dyno (prevents polling conflicts on Heroku)
    dyno_type = os.getenv("DYNO", "local")
    is_web_dyno = dyno_type.startswith("web.")
    
    if not is_web_dyno:
        log.info(f"Starting Telegram bot polling on dyno: {dyno_type}")
        # Start telegram bot polling
        await start_telegram_bot()
    else:
        log.info("Skipping Telegram bot polling on web dyno (Heroku). Run on worker dyno instead.")
    
    # Start the background task for telegram alerts (scheduled every 3 hours)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_alerts_loop, 'interval', hours=3)
    scheduler.start()
    
    yield
    
    scheduler.shutdown()
    if not is_web_dyno:
        await stop_telegram_bot()

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
ALLOWED_ORIGINS = [o for o in [
    "http://localhost:3000",
    "http://localhost:3001",
    _frontend_url,
] if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if _frontend_url else ["*"],
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


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"message": "Quantify API – see /docs for usage"}
