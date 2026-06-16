from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger("quantify.api.market_data")


def fetch_latest_prices(symbols: List[str]) -> Dict[str, Optional[float]]:
    """Fetch the most recent market price for each symbol via yfinance.

    Uses fast_info.last_price (real-time during market hours, previous close
    after hours) with a historical-close fallback. Per-ticker calls avoid the
    multi-ticker MultiIndex structure that changed across yfinance versions.
    """
    result: Dict[str, Optional[float]] = {s: None for s in symbols}
    if not symbols:
        return result
    try:
        import yfinance as yf
    except ImportError as exc:
        log.warning("yfinance not available: %s", exc)
        return result

    for sym in symbols:
        try:
            ticker = yf.Ticker(sym)
            # fast_info.last_price is the most recent trade price
            fi = ticker.fast_info
            price = fi.get("last_price") or fi.get("lastPrice")
            if price and float(price) > 0:
                result[sym] = round(float(price), 4)
                continue
            # Fallback: latest close from recent history
            hist = ticker.history(period="5d")
            if not hist.empty:
                closes = hist["Close"].dropna()
                if not closes.empty:
                    result[sym] = round(float(closes.iloc[-1]), 4)
        except Exception as exc:
            log.warning("Price fetch failed for %s: %s", sym, exc)

    return result
