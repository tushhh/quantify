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

# VADER's default lexicon is tuned for social media and misses most financial
# vocabulary ("beats", "soars", "downgrade", etc. all score 0).  We augment it
# with finance-specific terms so headlines like "Apple beats earnings, stock
# soars" register as bullish.  Values are on VADER's roughly -4..+4 scale.
_FINANCE_LEXICON: dict[str, float] = {
    # bullish
    "beat": 2.0, "beats": 2.0, "soars": 3.0, "soar": 3.0, "surge": 2.5,
    "surges": 2.5, "rally": 2.0, "rallies": 2.0, "jumps": 2.0, "jump": 1.5,
    "upgrade": 2.5, "upgraded": 2.5, "outperform": 2.5, "bullish": 3.0,
    "record": 1.5, "soaring": 3.0, "gains": 1.5, "gain": 1.0, "rebound": 1.8,
    "tops": 1.5, "raises": 1.5, "raised": 1.2, "buyback": 1.5, "dividend": 1.0,
    # bearish
    "miss": -2.0, "misses": -2.0, "missed": -2.0, "plunge": -3.0,
    "plunges": -3.0, "plummet": -3.0, "plummets": -3.0, "slump": -2.0,
    "slumps": -2.0, "downgrade": -2.5, "downgraded": -2.5, "bearish": -3.0,
    "tumble": -2.5, "tumbles": -2.5, "sinks": -2.0, "sink": -1.5,
    "warning": -1.5, "warns": -1.8, "cut": -1.2, "cuts": -1.2, "lawsuit": -2.0,
    "probe": -1.8, "recall": -1.8, "layoffs": -2.0, "bankruptcy": -3.5,
    "selloff": -2.5, "sell-off": -2.5, "slashes": -2.0, "slash": -2.0,
}


def _get_vader():
    """Return a finance-augmented VADER analyzer, downloading the lexicon if needed."""
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
    except LookupError:
        import nltk
        nltk.download("vader_lexicon", quiet=True)
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
    sia.lexicon.update(_FINANCE_LEXICON)
    return sia


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


def _fetch_ticker_news(symbol: str, max_articles: int, cache_dir: str, sia) -> Optional[dict]:
    """
    Fetch and score news for a single ticker.  Returns a dict with keys
    ``label``, ``score``, ``headlines`` or None on failure.

    ``sia`` is a shared, pre-initialised VADER analyzer (initialising it inside
    each worker thread would race on the one-time lexicon download).

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
        # yfinance has shipped two shapes: a flat {"title": ...} (older) and a
        # nested {"content": {"title": ...}} (newer).  ``content`` may also be
        # present but None, so coalesce before indexing.
        content = article.get("content") or {}
        title = article.get("title") or content.get("title") or ""
        if title:
            headlines.append(title)

    if not headlines:
        return None

    try:
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
    if not symbols:
        return {}

    # De-duplicate (preserving order) so the same ticker isn't fetched twice and
    # two worker threads can't race writing the same cache file.
    symbols = list(dict.fromkeys(symbols))

    # Initialise VADER once (the lexicon download is not concurrency-safe) and
    # share the analyzer across worker threads — polarity_scores is read-only.
    try:
        sia = _get_vader()
    except Exception as exc:
        log.warning("news: could not initialise VADER (%s) — skipping enrichment", exc)
        return {}

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(symbols))) as pool:
        futures = {
            pool.submit(_fetch_ticker_news, sym, max_articles_per_ticker, cache_dir, sia): sym
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
