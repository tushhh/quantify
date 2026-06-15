"""
quantify.data.news
~~~~~~~~~~~~~~~~~~
Fetch recent news headlines for a list of tickers via yfinance and score
them with VADER sentiment.  Results are cached on disk with a 6-hour TTL
so repeated runs within a trading session don't re-hit the network.

Only the top signals from the full screener are enriched (typically 20
tickers), so the total network cost is small.
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 6 * 3600
_MAX_WORKERS = 8


def _get_vader():
    """Return a VADER SentimentIntensityAnalyzer, downloading the lexicon if needed."""
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()
    except LookupError:
        import nltk
        nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        return SentimentIntensityAnalyzer()


def _score_headlines(headlines: list[str], sia) -> tuple[str, float]:
    """Return (label, avg_compound_score) for a list of headline strings."""
    if not headlines:
        return "NEUTRAL", 0.0
    scores = [sia.polarity_scores(h)["compound"] for h in headlines]
    avg = sum(scores) / len(scores)
    if avg >= 0.05:
        label = "BULLISH"
    elif avg <= -0.05:
        label = "BEARISH"
    else:
        label = "NEUTRAL"
    return label, round(avg, 4)


def _fetch_ticker_news(symbol: str, max_articles: int, cache_dir: str) -> Optional[dict]:
    """
    Fetch and score news for a single ticker.  Returns a dict with keys
    ``label``, ``score``, ``headlines`` or None on failure.

    Results are cached to ``{cache_dir}/news/{SYMBOL}_{date}.json``.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_path = os.path.join(cache_dir, "news", f"{symbol}_{today}.json")

    # Return cached result if fresh enough
    if os.path.exists(cache_path):
        try:
            mtime = os.path.getmtime(cache_path)
            if time.time() - mtime < _CACHE_TTL_SECONDS:
                with open(cache_path) as fh:
                    return json.load(fh)
        except Exception:
            pass

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news or []
    except Exception as exc:
        log.debug("news: failed to fetch yfinance news for %s: %s", symbol, exc)
        return None

    headlines = []
    for article in raw_news[:max_articles]:
        title = article.get("title") or article.get("content", {}).get("title", "")
        if title:
            headlines.append(title)

    if not headlines:
        return None

    try:
        sia = _get_vader()
        label, score = _score_headlines(headlines, sia)
    except Exception as exc:
        log.debug("news: VADER failed for %s: %s", symbol, exc)
        return None

    result = {"label": label, "score": score, "headlines": headlines[:3]}

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    try:
        with open(cache_path, "w") as fh:
            json.dump(result, fh)
    except Exception:
        pass

    return result


def fetch_news_sentiment(
    symbols: list[str],
    cache_dir: str = "./data/cache",
    max_articles_per_ticker: int = 5,
) -> dict[str, dict]:
    """
    Fetch and VADER-score recent headlines for each symbol in ``symbols``.

    Returns a mapping ``{symbol: {"label": str, "score": float, "headlines": [str]}}``.
    Symbols with no news or fetch failures are omitted from the result.
    Failures are silent — news enrichment should never block the screener.
    """
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(symbols))) as pool:
        futures = {
            pool.submit(_fetch_ticker_news, sym, max_articles_per_ticker, cache_dir): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                data = fut.result()
                if data:
                    results[sym] = data
            except Exception as exc:
                log.debug("news: unexpected error for %s: %s", sym, exc)

    log.info("news: enriched %d/%d tickers with sentiment", len(results), len(symbols))
    return results
