"""
Plain-English translation of ML model drivers for end users.

The model surfaces "explanations" as raw feature names with z-scores
(e.g. ``rsi_14: z=+1.23 (higher)``).  Most Telegram users won't understand
that, so this module converts those into human-readable phrases and builds a
single one-line "why" summary for each predicted stock.

Two public helpers:

* :func:`humanize_driver`    — one driver → ("Momentum", "stronger than usual ▲")
* :func:`build_plain_summary` — a PredictionItem → one-line plain-English string
"""

from __future__ import annotations

from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Feature glossary
# ---------------------------------------------------------------------------
# Each entry maps a raw model feature to:
#   label    — short human name
#   high     — what it means when the value is ABOVE average (z > 0)
#   low      — what it means when the value is BELOW average (z < 0)
#   phrase   — short clause used inside the one-line summary (direction-aware
#              via {dir} placeholder where helpful; falls back to high/low)
# ---------------------------------------------------------------------------

_GLOSSARY: dict[str, dict[str, str]] = {
    # Momentum / trend
    "rsi_14": {
        "label": "Momentum",
        "high": "stronger than usual ▲",
        "low": "weaker than usual ▼",
    },
    "macd_histogram": {
        "label": "Momentum shift",
        "high": "turning up ▲",
        "low": "turning down ▼",
    },
    "sma_crossover": {
        "label": "Trend",
        "high": "50-day above 200-day (uptrend) ▲",
        "low": "50-day below 200-day (downtrend) ▼",
    },
    "rsi_divergence": {
        "label": "Momentum vs price",
        "high": "momentum leading price up ▲",
        "low": "momentum lagging price ▼",
    },
    "mean_reversion_5d": {
        "label": "Short-term reversal",
        "high": "trend extending ▲",
        "low": "due for a bounce/pullback ▼",
    },
    # Returns
    "return_1d": {"label": "1-day return", "high": "positive ▲", "low": "negative ▼"},
    "return_5d": {"label": "1-week return", "high": "positive ▲", "low": "negative ▼"},
    "return_21d": {"label": "1-month return", "high": "positive ▲", "low": "negative ▼"},
    "return_63d": {"label": "3-month return", "high": "positive ▲", "low": "negative ▼"},
    "return_126d": {"label": "6-month return", "high": "positive ▲", "low": "negative ▼"},
    "return_252d": {"label": "12-month return", "high": "positive ▲", "low": "negative ▼"},
    # Volatility / risk
    "volatility_20d": {"label": "Volatility", "high": "elevated ▲", "low": "calm ▼"},
    "volatility_60d": {"label": "Volatility (3m)", "high": "elevated ▲", "low": "calm ▼"},
    "volatility_126d": {"label": "Volatility (6m)", "high": "elevated ▲", "low": "calm ▼"},
    "volatility_252d": {"label": "Volatility (1y)", "high": "elevated ▲", "low": "calm ▼"},
    "bollinger_width": {
        "label": "Price range",
        "high": "expanding (big moves) ▲",
        "low": "tightening (quiet) ▼",
    },
    "atr_14": {"label": "Daily range", "high": "wide ▲", "low": "narrow ▼"},
    "return_std_21d": {"label": "Choppiness", "high": "high ▲", "low": "low ▼"},
    "skewness_21d": {
        "label": "Return shape",
        "high": "upside-skewed ▲",
        "low": "downside-skewed ▼",
    },
    "max_return_21d": {"label": "Best recent day", "high": "large ▲", "low": "small ▼"},
    "min_return_21d": {"label": "Worst recent day", "high": "mild ▲", "low": "sharp ▼"},
    # Volume / confirmation
    "volume_ratio_20d": {
        "label": "Trading volume",
        "high": "above average ▲",
        "low": "below average ▼",
    },
    "obv_slope": {
        "label": "Volume trend",
        "high": "buyers accumulating ▲",
        "low": "sellers distributing ▼",
    },
    "volume_trend": {
        "label": "Volume trend",
        "high": "rising ▲",
        "low": "fading ▼",
    },
    "volume_price_corr_20d": {
        "label": "Volume confirmation",
        "high": "volume confirming the move ▲",
        "low": "move on thin volume ▼",
    },
    "mfi_14": {
        "label": "Money flow",
        "high": "money flowing in ▲",
        "low": "money flowing out ▼",
    },
    "vwap_ratio": {
        "label": "Price vs fair value",
        "high": "above volume-weighted average ▲",
        "low": "below volume-weighted average ▼",
    },
    "volume_price_divergence": {
        "label": "Volume/price",
        "high": "accumulation (bullish) ▲",
        "low": "thin-volume move (caution) ▼",
    },
    "amihud_illiquidity": {
        "label": "Liquidity",
        "high": "less liquid ▲",
        "low": "highly liquid ▼",
    },
    # Sector relative strength
    "sector_rs_5d": {
        "label": "vs sector (1w)",
        "high": "outperforming its sector ▲",
        "low": "lagging its sector ▼",
    },
    "sector_rs_21d": {
        "label": "vs sector (1m)",
        "high": "outperforming its sector ▲",
        "low": "lagging its sector ▼",
    },
    # Anchoring
    "price_to_high_52w": {
        "label": "Near 52-week high",
        "high": "close to highs ▲",
        "low": "well off highs ▼",
    },
    "price_to_low_52w": {
        "label": "Above 52-week low",
        "high": "far above lows ▲",
        "low": "near lows ▼",
    },
    "return_consistency": {
        "label": "Consistency",
        "high": "mostly up days ▲",
        "low": "mostly down days ▼",
    },
    "gap_return": {
        "label": "Overnight gaps",
        "high": "gapping up ▲",
        "low": "gapping down ▼",
    },
    "intraday_range": {
        "label": "Intraday swings",
        "high": "wide ▲",
        "low": "narrow ▼",
    },
    # Fundamentals
    "earnings_yield": {
        "label": "Valuation",
        "high": "cheap on earnings ▲",
        "low": "expensive on earnings ▼",
    },
    "book_to_market": {
        "label": "Valuation",
        "high": "value-priced ▲",
        "low": "growth-priced ▼",
    },
    "fcf_yield": {
        "label": "Cash generation",
        "high": "strong free cash flow ▲",
        "low": "weak free cash flow ▼",
    },
    "roe": {
        "label": "Profitability",
        "high": "high return on equity ▲",
        "low": "low return on equity ▼",
    },
}


def humanize_driver(feature: str, direction: str) -> tuple[str, str]:
    """
    Translate one model driver into ``(label, meaning)``.

    Parameters
    ----------
    feature:
        Raw model feature name (e.g. ``"rsi_14"``).
    direction:
        ``"higher"`` / ``"lower"`` (as produced by the model), or any string
        starting with ``"h"`` for higher.

    Returns
    -------
    (label, meaning)
        Human-readable label and a short direction-aware meaning.  Unknown
        features fall back to a tidied version of the raw name.
    """
    is_high = str(direction).lower().startswith("h")
    entry = _GLOSSARY.get(feature)
    if entry is None:
        # Fallback: tidy the raw feature name, e.g. "some_new_feat" → "Some new feat"
        label = feature.replace("_", " ").strip().capitalize()
        return label, ("above average ▲" if is_high else "below average ▼")
    meaning = entry["high"] if is_high else entry["low"]
    return entry["label"], meaning


def _clean_clause(meaning: str) -> str:
    """Strip the trailing ▲/▼ arrow for use inside a flowing sentence."""
    return meaning.replace("▲", "").replace("▼", "").strip()


def build_plain_summary(
    side: str,
    explanations: Iterable,
    max_drivers: int = 2,
) -> Optional[str]:
    """
    Build a one-line plain-English "why" summary from a signal's top drivers.

    Parameters
    ----------
    side:
        ``"long"`` (bullish) or ``"short"`` (bearish).
    explanations:
        Iterable of explanation objects/dicts each exposing ``feature`` and
        ``direction`` (PredictionExplanation or plain dict).
    max_drivers:
        How many drivers to fold into the sentence (default 2).

    Returns
    -------
    str or None
        A sentence like ``"strong momentum and volume confirming the move"``,
        or ``None`` if no usable drivers are present.
    """
    clauses: list[str] = []
    for exp in explanations:
        feature = getattr(exp, "feature", None) if not isinstance(exp, dict) else exp.get("feature")
        direction = getattr(exp, "direction", "higher") if not isinstance(exp, dict) else exp.get("direction", "higher")
        if not feature:
            continue
        _, meaning = humanize_driver(feature, direction)
        clause = _clean_clause(meaning)
        if clause and clause not in clauses:
            clauses.append(clause)
        if len(clauses) >= max_drivers:
            break

    if not clauses:
        return None

    if len(clauses) == 1:
        body = clauses[0]
    else:
        body = f"{', '.join(clauses[:-1])} and {clauses[-1]}"

    return body


__all__ = ["humanize_driver", "build_plain_summary"]
