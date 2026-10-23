"""
Trend screen: the stock picker behind /predict and the screener.

Why this and not the ML ensemble
--------------------------------
In October 2026 every candidate was replayed walk-forward on 2021-01 .. 2026-10 daily data
(S&P 500, point-in-time liquid universe, picks traded at the next close, 6 bps per side):

* ML ensemble (ml_return_predictor): top-10 picks lost to SPY after costs, and its list was
  replaced almost entirely every day.
* Early June-2026 model (1-day target, 100 names): lost to SPY by 3-6 %/yr after costs.
* This trend screen, 15 picks from the 100 most-traded S&P 500 names, monthly: 26.4 %/yr vs
  SPY 15.0 %/yr (+11.4 %/yr, +10.4 % at 16 bps/side), beat SPY in 57 % of months.
  Caveats: Sharpe 0.91 vs SPY 0.92, max drawdown -35.5 % vs SPY -24.5 %, it lagged SPY in
  2021-2023 and won in 2023-2026, and the universe is today's S&P 500 (survivorship bias).

The definition below must stay identical to the backtested one; tests pin it down. Re-run
the pick-backtest skill before changing any constant.

Signal (all causal, using closes up to the anchor date):
    score = mean(cross-sectional pct rank of the 126d return, pct rank of the 252d return)
    minus 1 for names closing below their 200-day average, restricted to the `liquid_top`
    names by 63-day median dollar volume. The top `n_picks` scores are the picks.
Rebalance: monthly. Picks are computed from the last close of the previous calendar month
and held for the whole month, as in the backtest.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

LIQUID_TOP = 100
N_PICKS = 15
MA_DAYS = 200
LIQUIDITY_DAYS = 63
RET_SHORT = 126
RET_LONG = 252
MIN_HISTORY = RET_LONG + 1

# Walk-forward results for this exact configuration (6 bps per side), shown to users.
BACKTEST = {
    "start": "2021-01",
    "end": "2026-10",
    "cagr_pct": 26.4,
    "spy_cagr_pct": 15.0,
    "excess_cagr_pct": 11.4,
    "excess_cagr_stress_pct": 10.4,  # at 16 bps per side
    "sharpe": 0.91,
    "spy_sharpe": 0.92,
    "max_drawdown_pct": -35.5,
    "spy_max_drawdown_pct": -24.5,
    "months_beat_spy_pct": 57.1,
    "picks": N_PICKS,
    "liquid_universe": LIQUID_TOP,
}


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
    picks = table.dropna(subset=["score"]).nlargest(n_picks, "score")
    top_score = float(picks["score"].max()) if len(picks) else 1.0

    signals = []
    for sym, row in picks.iterrows():
        signals.append({
            "symbol": sym,
            "strength": round(float(row["score"]) / top_score, 4) if top_score > 0 else 0.0,
            "side": "long",
            "sector": sectors.get(sym, "Unknown"),
            "name": names.get(sym) or sym,
            "predicted_return_pct": 0.0,
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


__all__ = ["BACKTEST", "N_PICKS", "LIQUID_TOP", "score_trend", "monthly_anchor", "run_trend_screen", "download_prices"]
