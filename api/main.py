"""
Quantify FastAPI Backend
========================
Serves the Quantify trading system as a REST API for the web front-end.
"""

from __future__ import annotations

import logging
import os
import sys

# Bulletproof path injection for Heroku
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from api.routers import backtest, risk, strategies, universe, predict, trades, auth
from api.database import engine
from api import models
from api.telegram_bot import check_alerts_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    from api.telegram_bot import start_telegram_bot, stop_telegram_bot
    
    # Initialize DB tables only if they don't exist. SQLAlchemy's checkfirst=True
    # (default) makes this a no-op on existing schema, so it's safe to call at startup.
    models.Base.metadata.create_all(bind=engine)
    
    # Start telegram bot polling
    await start_telegram_bot()
    
    # Start the background task for telegram alerts (scheduled every hour)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_alerts_loop, 'interval', minutes=60)
    scheduler.start()
    
    yield
    
    scheduler.shutdown()
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
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    os.getenv("FRONTEND_URL", ""),          # set in Render env vars
    "https://*.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to ALLOWED_ORIGINS in prod if desired
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


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"message": "Quantify API – see /docs for usage"}
