"""
Trend screen: the stock picker behind /predict and the screener.

Why this and not the ML ensemble
--------------------------------
In October 2026 every candidate was replayed walk-forward on 2021-01 .. 2026-10 daily data
(S&P 500, point-in-time liquid universe, picks traded at the next close, 6 bps per side):

* ML ensemble (ml_return_predictor): top-10 picks lost to SPY after costs, and its list was
  replaced almost entirely every day.
* Early June-2026 model (1-day target, 100 names): lost to SPY by 3-6 %/yr after costs.
* This trend screen, 15 picks from the 100 most-traded S&P 500 names (one share class per
  company, no sector cap), monthly, Dec 2017 .. Oct 2026: 26.8 %/yr vs SPY 14.5 %/yr
  (+12.3 %/yr, +11.4 % at 16 bps/side), Sharpe 0.88 vs 0.81, max drawdown -37 % vs SPY -34 %.
  It lost to SPY in 2017, 2019, 2021 and 2023 and beat SPY in 54 % of months; 2026 alone was
  +58.5 pts (the AI-chip run). The universe is today's S&P 500 (survivorship bias).
* Concentration: 2025-26 lists were 60-67 % AI chips/hardware, and excluding tech left only
  +1.9 %/yr. A cap of 3 per sector made more in 2017-2025 with a higher Sharpe (0.96) but
  trailed in 2026; the user chose uncapped, betting the AI rally continues.

Tested and rejected (Oct 2026, walk-forward, same liquid universe, after costs):
* ML overlay (LightGBM on the 30 FeatureEngine features + trend score, monthly retrain,
  68 unseen months 2021-2026): ML alone +10.4 %/yr vs SPY, blend +9.9, trend +15.1; ML rank IC
  0.001 (no skill). A 96 %-in-sample classifier scored 50.0 % on 2023-2026.
* SEC EDGAR fundamentals (XBRL frames, assumed public 60 days after quarter end, 90 months
  2019-2026) as a filter on the trend top 30: earnings growth +14.7 %/yr, value +10.0, quality
  (ROA) +6.7, composite +5.8, vs trend alone +15.4. Rank ICs -0.003 .. 0.011.

The definition below must stay identical to the backtested one; tests pin it down. Re-run
the pick-backtest skill before changing any constant.

Signal (all causal, using closes up to the anchor date):
    score = mean(cross-sectional pct rank of the 126d return, pct rank of the 252d return)
    minus 1 for names closing below their 200-day average, restricted to the `liquid_top`
    names by 63-day median dollar volume. The top `n_picks` scores are the picks, one share
    class per company (and at most `MAX_PER_SECTOR` per GICS sector when that is set).
Rebalance: monthly. Picks are computed from the last close of the previous calendar month
and held for the whole month, as in the backtest.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

LIQUID_TOP = 100
N_PICKS = 15
# No sector cap: the user chose uncapped in Oct 2026. A cap of 3 had a higher Sharpe and made
# more in 2017-2025, but trailed in the 2026 AI-chip run. Pass a number to compare.
MAX_PER_SECTOR: Optional[int] = None
MA_DAYS = 200
LIQUIDITY_DAYS = 63
RET_SHORT = 126
RET_LONG = 252
MIN_HISTORY = RET_LONG + 1

# Walk-forward results for this exact configuration (6 bps per side), shown to users.
# Reproduce with scripts/backtest_picks.py (pick-backtest skill), 2026-10-23 run, no sector cap.
BACKTEST = {
    "start": "2017-12",
    "end": "2026-10",
    "cagr_pct": 26.8,
    "spy_cagr_pct": 14.5,
    "excess_cagr_pct": 12.3,
    "excess_cagr_stress_pct": 11.4,  # at 16 bps per side
    "sharpe": 0.88,
    "spy_sharpe": 0.81,
    "max_drawdown_pct": -37.0,
    "spy_max_drawdown_pct": -33.7,
    "months_beat_spy_pct": 54.0,
    "losing_years": "2017, 2019, 2021, 2023",
    "picks": N_PICKS,
    "liquid_universe": LIQUID_TOP,
}

# Next-month forecast by rank: what picks at that rank did over the following month in the
# same backtest (1,590 picks, Dec 2017 .. Sep 2026, bought at the close after the list date).
# Single stocks are noisy: the range is the 10th..90th percentile. In-sample (same period the
# rule was chosen on), so treat as optimistic. Regenerate with scripts/backtest_picks.py --forecast.
FORECAST_HORIZON = "1 month"
FORECAST = {
    "1-5": {"mean_pct": 4.1, "median_pct": 1.8, "low_pct": -12.5, "high_pct": 22.6, "beat_spy_pct": 54.5},
    "6-10": {"mean_pct": 1.4, "median_pct": 0.8, "low_pct": -12.0, "high_pct": 13.6, "beat_spy_pct": 47.9},
    "11-15": {"mean_pct": 2.3, "median_pct": 1.3, "low_pct": -9.7, "high_pct": 13.8, "beat_spy_pct": 52.5},
}


def forecast_bucket(rank: int) -> str:
    """Forecast bucket for a 1-based rank in the list."""
    return "1-5" if rank <= 5 else "6-10" if rank <= 10 else "11-15"


def score_trend(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    as_of: Optional[pd.Timestamp] = None,
    liquid_top: int = LIQUID_TOP,
) -> pd.DataFrame:
    """Score every symbol on `as_of` (default: the last row) using data up to that date only.

    `close` and `volume` are wide frames (dates x symbols) of adjusted closes and share volume.
    Returns one row per symbol with the inputs, `liquid`, `above_ma200` and `score`
    (NaN when the symbol isn't eligible).
    """
    if as_of is None:
        as_of = close.index[-1]
    close = close.loc[:as_of]
    volume = volume.reindex(index=close.index, columns=close.columns).loc[:as_of]
    if len(close) < MIN_HISTORY:
        raise ValueError(f"need at least {MIN_HISTORY} rows of price history, got {len(close)}")

    last = close.iloc[-1]
    history = close.notna().sum()
    eligible = last.notna() & (history >= MIN_HISTORY)

    ret_short = last / close.iloc[-1 - RET_SHORT] - 1
    ret_long = last / close.iloc[-1 - RET_LONG] - 1
    ma200 = close.iloc[-MA_DAYS:].mean()
    above = last > ma200

    dollar_vol = (close.iloc[-LIQUIDITY_DAYS:] * volume.iloc[-LIQUIDITY_DAYS:]).median()
    dollar_vol = dollar_vol.where(eligible)
    liquid = dollar_vol.rank(ascending=False) <= liquid_top

    rank_short = ret_short.where(eligible).rank(pct=True)
    rank_long = ret_long.where(eligible).rank(pct=True)
    score = (rank_short + rank_long) / 2
    score = score.where(above, score - 1.0).where(liquid)

    return pd.DataFrame({
        "return_6m": ret_short,
        "return_12m": ret_long,
        "pct_above_ma200": last / ma200 - 1,
        "dollar_volume": dollar_vol,
        "liquid": liquid,
        "above_ma200": above,
        "score": score,
    })


def _company(sym: str, names: dict[str, str]) -> str:
    """Company key that merges share classes: 'Alphabet Inc. (Class A)' -> 'alphabet inc.'."""
    name = names.get(sym)
    return re.sub(r"\s*\(class [^)]*\)\s*$", "", name.strip().lower()) if name else sym


def select_picks(
    scores: pd.Series,
    sectors: dict[str, str],
    n: int = N_PICKS,
    max_per_sector: Optional[int] = MAX_PER_SECTOR,
    names: Optional[dict[str, str]] = None,
) -> list[str]:
    """Highest scores first, one share class per company, optionally capped per GICS sector."""
    names = names or {}
    picks: list[str] = []
    counts: dict[str, int] = {}
    companies: set[str] = set()
    for sym in scores.dropna().sort_values(ascending=False, kind="stable").index:
        sector = sectors.get(sym) or f"unknown:{sym}"
        company = _company(sym, names)
        if company in companies or (max_per_sector is not None and counts.get(sector, 0) >= max_per_sector):
            continue
        picks.append(sym)
        companies.add(company)
        counts[sector] = counts.get(sector, 0) + 1
        if len(picks) == n:
            break
    return picks


def monthly_anchor(dates: pd.DatetimeIndex) -> pd.Timestamp:
    """The last trading day of the month before the latest date in `dates`."""
    dates = pd.DatetimeIndex(dates).sort_values()
    latest = dates[-1]
    earlier = dates[dates < latest.to_period("M").start_time]
    return earlier[-1] if len(earlier) else dates[0]


def run_trend_screen(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    sectors: dict[str, str],
    names: dict[str, str],
    n_picks: int = N_PICKS,
    liquid_top: int = LIQUID_TOP,
    now: Optional[datetime] = None,
) -> dict:
    """Run the screen and return a PredictionResponse-shaped dict (long picks only)."""
    if len(close) < MIN_HISTORY:
        raise ValueError(f"need at least {MIN_HISTORY} rows of price history, got {len(close)}")
    now = now or datetime.now(timezone.utc)
    anchor = monthly_anchor(close.index)
    table = score_trend(close, volume, as_of=anchor, liquid_top=liquid_top)
    picks = table.loc[select_picks(table["score"], sectors, n_picks, names=names)]
    top_score = float(picks["score"].max()) if len(picks) else 1.0

    signals = []
    for rank, (sym, row) in enumerate(picks.iterrows(), 1):
        fc = FORECAST[forecast_bucket(rank)]
        signals.append({
            "symbol": sym,
            "strength": round(float(row["score"]) / top_score, 4) if top_score > 0 else 0.0,
            "side": "long",
            "sector": sectors.get(sym, "Unknown"),
            "name": names.get(sym) or sym,
            "predicted_return_pct": fc["mean_pct"],
            "forecast_median_pct": fc["median_pct"],
            "forecast_low_pct": fc["low_pct"],
            "forecast_high_pct": fc["high_pct"],
            "forecast_beat_spy_pct": fc["beat_spy_pct"],
            "return_6m_pct": round(float(row["return_6m"]) * 100, 2),
            "return_12m_pct": round(float(row["return_12m"]) * 100, 2),
            "pct_above_ma200": round(float(row["pct_above_ma200"]) * 100, 2),
            "explanations": [
                {"feature": "return_126d", "zscore": 0.0, "value": float(row["return_6m"]), "direction": "higher"},
                {"feature": "return_252d", "zscore": 0.0, "value": float(row["return_12m"]), "direction": "higher"},
            ],
        })

    next_refresh = (anchor.to_period("M") + 2).start_time  # first day of the month after next close-of-month
    return {
        "status": "ok",
        "mode": "previous_close",
        "method": "trend",
        "date": now.date().isoformat(),
        "as_of": str(anchor.date()),
        "next_refresh": str(next_refresh.date()),
        "generated_at": now.isoformat(),
        "signals": signals,
        "cached": False,
        "cache_age_minutes": 0.0,
        "universe_size": int(table["liquid"].sum()),
        "model_metrics": None,
        "backtest": dict(BACKTEST),
        "forecast_horizon": FORECAST_HORIZON,
    }


def download_prices(tickers: list[str], period: str = "2y", chunk: int = 100) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Adjusted daily closes and volumes from yfinance, in chunks (network; not used in tests)."""
    import yfinance as yf

    closes, volumes = [], []
    for i in range(0, len(tickers), chunk):
        part = tickers[i:i + chunk]
        df = yf.download(part, period=period, auto_adjust=True, progress=False, threads=True, group_by="column")
        if df is None or df.empty:
            continue
        closes.append(df["Close"] if isinstance(df.columns, pd.MultiIndex) else df[["Close"]].rename(columns={"Close": part[0]}))
        volumes.append(df["Volume"] if isinstance(df.columns, pd.MultiIndex) else df[["Volume"]].rename(columns={"Volume": part[0]}))
    close = pd.concat(closes, axis=1).sort_index()
    volume = pd.concat(volumes, axis=1).sort_index()
    close.index = pd.DatetimeIndex(close.index).tz_localize(None)
    volume.index = pd.DatetimeIndex(volume.index).tz_localize(None)
    close = close.loc[:, ~close.columns.duplicated()].dropna(how="all", axis=1)
    return close, volume.reindex(columns=close.columns)


__all__ = ["BACKTEST", "N_PICKS", "LIQUID_TOP", "MAX_PER_SECTOR", "score_trend", "select_picks", "monthly_anchor", "run_trend_screen", "download_prices"]
