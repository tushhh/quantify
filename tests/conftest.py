"""
tests/conftest.py
~~~~~~~~~~~~~~~~~
Shared pytest fixtures for the Quantify test suite.

Fixtures
--------
sample_ohlcv_data   — 252 days of realistic OHLCV data for a single stock
sample_multi_stock_data — data for 5 stocks (AAPL, MSFT, GOOGL, AMZN, TSLA)
sample_returns      — daily returns Series derived from sample_ohlcv_data
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEED = 42
_N_DAYS = 252
_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

# Base prices per symbol (approximate real-world starting prices)
_BASE_PRICES = {
    "AAPL": 150.0,
    "MSFT": 280.0,
    "GOOGL": 100.0,
    "AMZN": 130.0,
    "TSLA": 200.0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(
    ticker: str,
    n_days: int = _N_DAYS,
    seed: int = _SEED,
    base_price: float = 150.0,
) -> pd.DataFrame:
    """
    Generate realistic synthetic OHLCV data.

    Uses geometric Brownian motion for the close price, with intraday
    spread and volume modelled separately.
    """
    rng = np.random.default_rng(seed)

    # Daily returns: mean 8% annualised, 25% annualised vol
    mu_daily = 0.08 / 252
    sigma_daily = 0.25 / np.sqrt(252)

    returns = rng.normal(mu_daily, sigma_daily, n_days)
    close = base_price * np.cumprod(1 + returns)

    # Intraday spread: open within ±0.5% of previous close
    open_ = close * (1 + rng.uniform(-0.005, 0.005, n_days))
    # High is max(open, close) + intraday upswing
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.015, n_days))
    # Low is min(open, close) - intraday downswing
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.015, n_days))
    # Volume: log-normal around 10M shares with daily variation
    volume = (rng.lognormal(mean=16.0, sigma=0.5, size=n_days)).astype(int)

    # Build business-day DatetimeIndex starting 2022-01-03
    dates = pd.bdate_range(start="2022-01-03", periods=n_days, freq="B")

    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )
    df.index.name = "timestamp"
    return df


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sample_ohlcv_data() -> pd.DataFrame:
    """
    252 trading days of realistic OHLCV data for a single stock.

    Returns a DataFrame with columns: open, high, low, close, volume
    and a DatetimeIndex (business days from 2022-01-03).
    """
    return _make_ohlcv("AAPL", n_days=_N_DAYS, seed=_SEED, base_price=150.0)


@pytest.fixture(scope="session")
def sample_multi_stock_data() -> dict[str, pd.DataFrame]:
    """
    252 trading days of OHLCV data for 5 S&P 500 stocks.

    Returns a dict mapping ticker -> DataFrame.
    Each DataFrame has a different random seed so the price paths are
    independent (though starting prices reflect approximate real values).
    """
    data: dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(_TICKERS):
        base = _BASE_PRICES.get(ticker, 100.0)
        df = _make_ohlcv(ticker, n_days=_N_DAYS, seed=_SEED + i, base_price=base)
        data[ticker] = df
    return data


@pytest.fixture(scope="session")
def sample_returns(sample_ohlcv_data: pd.DataFrame) -> pd.Series:
    """
    Daily simple returns derived from sample_ohlcv_data's close prices.

    Returns a pd.Series indexed by date, with name='returns'.
    """
    returns = sample_ohlcv_data["close"].pct_change().dropna()
    returns.name = "returns"
    return returns


@pytest.fixture(scope="session")
def long_ohlcv_data() -> pd.DataFrame:
    """
    500 trading days of OHLCV data — enough for strategies requiring
    252+ days of lookback (e.g. CrossSectionalMomentum).
    """
    return _make_ohlcv("AAPL", n_days=500, seed=_SEED + 99, base_price=150.0)


@pytest.fixture(scope="session")
def long_multi_stock_data() -> dict[str, pd.DataFrame]:
    """
    500 trading days of OHLCV data for 15 stocks.
    Used by strategies that rank stocks cross-sectionally.
    """
    tickers = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
        "NVDA", "META", "JPM", "BAC", "XOM",
        "JNJ", "PG", "V", "MA", "UNH",
    ]
    data: dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(tickers):
        base = _BASE_PRICES.get(ticker, 100.0 + i * 10)
        df = _make_ohlcv(ticker, n_days=500, seed=_SEED + 200 + i, base_price=base)
        data[ticker] = df
    return data
