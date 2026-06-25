"""
Intraday gain scanner — runs on the worker dyno via APScheduler.

Fetches live prices for the S&P 500 universe every 7 minutes during US market
hours, computes the day's gain vs previous close, and broadcasts Telegram alerts
to subscribers who have crossed a new tier.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pytz

log = logging.getLogger("quantify.gain_scanner")

_ET = pytz.timezone("America/New_York")
_SCAN_THRESHOLD = 1.0   # fetch all stocks up ≥1%; per-subscriber thresholds filter at broadcast
_WORKERS = 25

# Universe cache: refresh once per day to avoid hitting Wikipedia on every scan
_universe: list[str] = []
_universe_date: str = ""


def _get_universe() -> list[str]:
    global _universe, _universe_date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _universe and _universe_date == today:
        return _universe
    try:
        from quantify.data.universe import Universe
        _universe = Universe.from_wikipedia().tickers[:500]
        _universe_date = today
        log.info("Universe refreshed from Wikipedia: %d tickers", len(_universe))
    except Exception as exc:
        log.warning("Wikipedia fetch failed, using fallback: %s", exc)
        if not _universe:
            from quantify.data.universe import get_russell1000
            _universe = get_russell1000()[:500]
            _universe_date = today
    return _universe


def _fetch_gain(symbol: str):
    """Blocking single-ticker price fetch. Returns (symbol, dict) or (symbol, None)."""
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
            "symbol": symbol,
            "gain_pct": round(gain_pct, 4),
            "price": round(today_price, 2),
            "prev_close": round(prev_close, 2),
        }
    except Exception as exc:
        log.debug("Price fetch failed for %s: %s", symbol, exc)
        return symbol, None


def _fetch_all_gains(symbols: list[str]) -> list[dict]:
    """Blocking: fetch gains for all symbols in parallel, return those ≥ threshold."""
    results = []
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        futures = {pool.submit(_fetch_gain, sym): sym for sym in symbols}
        for future in as_completed(futures):
            _, data = future.result()
            if data is not None and data["gain_pct"] >= _SCAN_THRESHOLD:
                results.append(data)
    results.sort(key=lambda x: x["gain_pct"], reverse=True)
    return results


async def process_and_broadcast(gainers: list[dict], scan_date: str) -> int:
    """Dedup gainers per subscriber and broadcast new tier crossings.

    Returns the total number of new alerts sent.
    Called both by the scheduler and by the /gain-alert-complete fallback endpoint.
    """
    from api.database import SessionLocal
    from api.models import GainAlertState, GainAlertSubscription
    from api.prediction_bot import broadcast_gain_alerts

    db = SessionLocal()
    per_chat_alerts: dict[str, list] = {}
    try:
        subscriptions = db.query(GainAlertSubscription).all()
        if not subscriptions:
            return 0

        for g in gainers:
            for sub in subscriptions:
                threshold = sub.threshold_pct or 4.0
                tiers = [threshold, threshold + 5.0, threshold + 10.0]
                crossed = max((t for t in tiers if g["gain_pct"] >= t), default=None)
                if crossed is None:
                    continue

                state = db.query(GainAlertState).filter(
                    GainAlertState.symbol == g["symbol"],
                    GainAlertState.alert_date == scan_date,
                    GainAlertState.chat_id == sub.chat_id,
                ).first()

                if state is None:
                    db.add(GainAlertState(
                        symbol=g["symbol"],
                        alert_date=scan_date,
                        chat_id=sub.chat_id,
                        last_alerted_pct=crossed,
                    ))
                    per_chat_alerts.setdefault(sub.chat_id, []).append((g, crossed))
                elif crossed > state.last_alerted_pct:
                    state.last_alerted_pct = crossed
                    state.updated_at = datetime.now(timezone.utc)
                    per_chat_alerts.setdefault(sub.chat_id, []).append((g, crossed))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    total_new = sum(len(v) for v in per_chat_alerts.values())
    log.info("Gain scan: %d gainers, %d new alerts across %d chats",
             len(gainers), total_new, len(per_chat_alerts))

    if per_chat_alerts:
        await broadcast_gain_alerts(per_chat_alerts)

    return total_new


async def run_gain_scan() -> None:
    """APScheduler entry point — called every 7 min during premarket/market/postmarket."""
    now_et = datetime.now(_ET)
    # APScheduler's cron already limits to extended hours, but double-check so
    # edge-of-window runs during the scheduler's minute=*/7 cycle exit cleanly.
    # Premarket opens 4:00 AM ET; postmarket closes 8:00 PM ET.
    open_h, open_m = 4, 0
    close_h, close_m = 20, 0
    t = (now_et.hour, now_et.minute)
    if not ((open_h, open_m) <= t < (close_h, close_m)):
        return

    log.info("Gain scan starting (%s ET)", now_et.strftime("%H:%M"))

    universe = _get_universe()
    scan_date = now_et.strftime("%Y-%m-%d")

    loop = asyncio.get_running_loop()
    try:
        gainers = await loop.run_in_executor(None, lambda: _fetch_all_gains(universe))
    except Exception as exc:
        log.exception("Price fetch failed: %s", exc)
        return

    log.info("Prices fetched: %d gainers ≥%.1f%% found", len(gainers), _SCAN_THRESHOLD)

    if gainers:
        try:
            await process_and_broadcast(gainers, scan_date)
        except Exception as exc:
            log.exception("Dedup/broadcast failed: %s", exc)
