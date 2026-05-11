from __future__ import annotations

import logging
from typing import Tuple

from fastapi import APIRouter, HTTPException

log = logging.getLogger("quantify.api.utils")

router = APIRouter(prefix="/utils", tags=["utils"])


def _is_us_equity(symbol: str) -> Tuple[bool, str]:
    """Check whether a ticker symbol refers to a US-listed equity.

    Uses yfinance to probe the ticker and checks common indicators.
    Returns (True, exchange) when confident, otherwise (False, reason).
    """
    try:
        import yfinance as yf
    except Exception as exc:
        log.error("yfinance is required for symbol validation: %s", exc)
        return False, "yfinance not available on server"

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
    except Exception as exc:
        log.debug("yfinance lookup failed for %s: %s", symbol, exc)
        return False, "lookup_failed"

    # If info contains explicit country, prefer that
    country = info.get("country")
    exchange = info.get("exchange") or info.get("primaryExchange") or info.get("market")
    quote_type = info.get("quoteType") or info.get("instrumentType")

    if country:
        if "United" in str(country):
            return True, exchange or "US"
        return False, "not_us_equity"

    # Common exchange names signalling US listing
    if exchange:
        exch = str(exchange).upper()
        for known in ("NASDAQ", "NYSE", "AMEX", "NMS", "ARCA", "BATS"):
            if known in exch:
                return True, exchange

    # Fallback: ensure it is an equity type
    if quote_type and str(quote_type).upper() in ("EQUITY", "STOCK"):
        return True, exchange or "unknown"

    return False, "not_us_equity"


@router.get("/validate_symbol")
async def validate_symbol(symbol: str):
    """Validate a ticker symbol is a US-listed equity.

    Returns JSON: { valid: bool, reason?: str, exchange?: str }
    """
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    sym = symbol.strip().upper()
    valid, meta = _is_us_equity(sym)
    if valid:
        return {"valid": True, "exchange": meta}
    else:
        return {"valid": False, "reason": meta}
