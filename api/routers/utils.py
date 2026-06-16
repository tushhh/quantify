from __future__ import annotations

import asyncio
import logging
from typing import Tuple

from fastapi import APIRouter, HTTPException

log = logging.getLogger("quantify.api.utils")

router = APIRouter(prefix="/utils", tags=["utils"])


def _is_us_equity(symbol: str) -> Tuple[bool, str]:
    """Check whether a ticker symbol refers to a US-listed security (equity or ETF).

    Synchronous — always call via run_in_executor from async routes.
    """
    try:
        import yfinance as yf
    except Exception as exc:
        log.error("yfinance not available: %s", exc)
        return False, "yfinance not available on server"

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
    except Exception as exc:
        log.debug("yfinance lookup failed for %s: %s", symbol, exc)
        return False, "lookup_failed"

    country = info.get("country")
    exchange = info.get("exchange") or info.get("primaryExchange") or info.get("market")
    quote_type = info.get("quoteType") or info.get("instrumentType")
    market = info.get("market", "")

    if country:
        if "United" in str(country):
            return True, exchange or "US"
        return False, "not_us_listed"

    if exchange:
        exch = str(exchange).upper()
        for known in ("NASDAQ", "NYSE", "AMEX", "NMS", "ARCA", "BATS", "PCX", "CBOE"):
            if known in exch:
                return True, exchange

    if "us_market" in str(market).lower():
        return True, exchange or market

    if quote_type and str(quote_type).upper() in ("EQUITY", "STOCK", "ETF", "MUTUALFUND"):
        return True, exchange or "unknown"

    return False, "not_us_listed"


@router.get("/validate_symbol")
async def validate_symbol(symbol: str):
    """Validate a ticker symbol is a US-listed equity."""
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    sym = symbol.strip().upper()
    loop = asyncio.get_running_loop()
    valid, meta = await loop.run_in_executor(None, _is_us_equity, sym)
    if valid:
        return {"valid": True, "exchange": meta}
    return {"valid": False, "reason": meta}
