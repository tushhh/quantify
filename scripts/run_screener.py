#!/usr/bin/env python
"""
Run the full 500-stock screener and POST results to the Heroku callback URL.
Called by GitHub Actions after model training completes.
"""

import json
import logging
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quantify.data.universe import Universe, get_russell1000
from quantify.data.news import fetch_news_sentiment
from quantify.screener import run_screener

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s – %(message)s")
log = logging.getLogger("run_screener")

_SCREENER_UNIVERSE_SIZE = 500


def main():
    chat_id = os.getenv("INPUT_CHAT_ID", "")
    callback_url = os.getenv("INPUT_HEROKU_CALLBACK_URL", "")
    internal_secret = os.getenv("INTERNAL_API_SECRET", "")

    log.info("Starting full screener for %d stocks (chat_id=%s)", _SCREENER_UNIVERSE_SIZE, chat_id or "none")

    try:
        universe = Universe.from_wikipedia().tickers[:_SCREENER_UNIVERSE_SIZE]
    except Exception as e:
        log.warning("Failed to fetch from Wikipedia, falling back to Russell 1000: %s", e)
        universe = get_russell1000()[:_SCREENER_UNIVERSE_SIZE]
    cache_dir = os.getenv("PREDICTION_DATA_CACHE_DIR", "./data/cache")

    try:
        result = run_screener(universe, cache_dir=cache_dir)
    except Exception as exc:
        log.exception("Screener failed: %s", exc)
        _send_callback(callback_url, chat_id, internal_secret, status="failed", error=str(exc))
        sys.exit(1)

    if not result["signals"]:
        log.error("No signals generated.")
        _send_callback(callback_url, chat_id, internal_secret, status="failed", error="No signals generated")
        sys.exit(1)

    n_longs = sum(1 for s in result["signals"] if s["side"] == "long")
    n_shorts = sum(1 for s in result["signals"] if s["side"] == "short")
    log.info("Screener complete: %d longs, %d shorts", n_longs, n_shorts)

    # Enrich top signals with news sentiment (top 10 longs + top 10 shorts only)
    top_symbols = [
        s["symbol"] for s in result["signals"] if s["side"] == "long"
    ][:10] + [
        s["symbol"] for s in result["signals"] if s["side"] == "short"
    ][:10]
    if top_symbols:
        log.info("Fetching news sentiment for %d top signals…", len(top_symbols))
        try:
            news_map = fetch_news_sentiment(top_symbols, cache_dir=cache_dir)
            for sig in result["signals"]:
                if sig["symbol"] in news_map:
                    sig["news"] = news_map[sig["symbol"]]
        except Exception as exc:
            log.warning("News enrichment failed (non-fatal): %s", exc)

    output_json = os.getenv("OUTPUT_JSON_PATH")
    if output_json:
        try:
            with open(output_json, "w") as f:
                json.dump(result, f)
            log.info("Results saved to %s", output_json)
        except Exception as e:
            log.error("Failed to save results to %s: %s", output_json, e)

    _send_callback(callback_url, chat_id, internal_secret, status="complete", result=result)


def _send_callback(url: str, chat_id: str, secret: str, status: str, result: dict = None, error: str = None):
    if not url:
        log.info("No callback URL set — skipping notification.")
        return

    payload = {
        "chat_id": chat_id,
        "status": status,
        "result_json": json.dumps(result) if result else None,
        "error": error,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if secret:
        req.add_header("X-Internal-Secret", secret)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log.info("Callback sent to %s (HTTP %d)", url, resp.status)
    except Exception as e:
        log.error("Failed to send callback to %s: %s", url, e)


if __name__ == "__main__":
    main()
