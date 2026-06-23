#!/usr/bin/env python
"""
Scan the S&P 500 for intraday gainers and POST results to the Heroku callback.
Called by GitHub Actions on a 5-minute cron schedule during US market hours.

Exit 0 always — failures are logged but not fatal so the workflow stays green.
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pytz

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] – %(message)s")
log = logging.getLogger("run_gain_scan")

_ET = pytz.timezone("America/New_York")
_MARKET_OPEN_H, _MARKET_OPEN_M = 9, 30
_MARKET_CLOSE_H, _MARKET_CLOSE_M = 16, 0
_THRESHOLD = float(os.getenv("GAIN_ALERT_THRESHOLD_PCT", "4.0"))
_WORKERS = 25


def _is_market_open(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    t = (now_et.hour, now_et.minute)
    return (_MARKET_OPEN_H, _MARKET_OPEN_M) <= t < (_MARKET_CLOSE_H, _MARKET_CLOSE_M)


def _fetch_gain(symbol: str):
    """Return (symbol, {gain_pct, price, prev_close}) or (symbol, None) on failure."""
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="5d")
        if hist is None or len(hist) < 2:
            return symbol, None
        closes = hist["Close"].dropna()
        if len(closes) < 2:
            return symbol, None
        prev_close = float(closes.iloc[-2])
        today_price = float(closes.iloc[-1])
        if prev_close <= 0:
            return symbol, None
        gain_pct = (today_price - prev_close) / prev_close * 100
        return symbol, {
            "gain_pct": round(gain_pct, 4),
            "price": round(today_price, 2),
            "prev_close": round(prev_close, 2),
        }
    except Exception as exc:
        log.debug("Price fetch failed for %s: %s", symbol, exc)
        return symbol, None


def get_day_gains(symbols: list) -> dict:
    results = {}
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = {pool.submit(_fetch_gain, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym, data = future.result()
            if data is not None:
                results[sym] = data
    return results


def _send_callback(url: str, secret: str, gainers: list, scan_date: str) -> None:
    if not url:
        log.info("No callback URL set — results not posted.")
        return

    payload = json.dumps({"gainers": gainers, "scan_date": scan_date}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if secret:
        req.add_header("X-Internal-Secret", secret)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log.info("Callback sent (HTTP %d)", resp.status)
    except urllib.error.HTTPError as exc:
        log.error("Callback HTTP error %d: %s", exc.code, exc.read().decode())
    except Exception as exc:
        log.error("Callback failed: %s", exc)


def main() -> None:
    now_et = datetime.now(_ET)
    if not _is_market_open(now_et):
        log.info("Market closed (%s ET) — skipping scan.", now_et.strftime("%H:%M %A"))
        return

    heroku_url = os.getenv("HEROKU_APP_URL", "").rstrip("/")
    callback_url = f"{heroku_url}/api/internal/gain-alert-complete" if heroku_url else ""
    internal_secret = os.getenv("INTERNAL_API_SECRET", "")

    from quantify.data.universe import Universe, get_russell1000
    try:
        universe = Universe.from_wikipedia().tickers[:500]
        log.info("Universe loaded from Wikipedia (%d tickers)", len(universe))
    except Exception as exc:
        log.warning("Wikipedia fetch failed, using Russell 1000 fallback: %s", exc)
        universe = get_russell1000()[:500]

    log.info("Scanning %d symbols for ≥%.1f%% day gain…", len(universe), _THRESHOLD)
    gains = get_day_gains(universe)
    log.info("Prices fetched: %d/%d succeeded", len(gains), len(universe))

    gainers = [
        {"symbol": sym, **data}
        for sym, data in gains.items()
        if data["gain_pct"] >= _THRESHOLD
    ]
    gainers.sort(key=lambda x: x["gain_pct"], reverse=True)

    scan_date = now_et.strftime("%Y-%m-%d")
    log.info(
        "Found %d gainer(s) ≥%.1f%% on %s: %s",
        len(gainers), _THRESHOLD, scan_date,
        [g["symbol"] for g in gainers[:10]],
    )

    _send_callback(callback_url, internal_secret, gainers, scan_date)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.exception("Unhandled error in gain scan: %s", exc)
        sys.exit(0)  # Non-fatal — don't fail the Actions job
