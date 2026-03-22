"""
quantify.evaluation.metrics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Performance metrics for quantitative trading strategies.

All primary functions accept a ``pd.Series`` of daily returns indexed by
datetime.  Edge cases (empty series, all-zero returns, single data point,
NaN values) are handled gracefully — functions return ``float('nan')`` or
``0.0`` as documented rather than raising.

Usage
-----
    from quantify.evaluation.metrics import calculate_all, sharpe_ratio

    metrics = calculate_all(daily_returns, benchmark_returns=spy_returns)
    print(f"Sharpe: {metrics['sharpe_ratio']:.3f}")
    print(f"Max DD: {metrics['max_drawdown']:.2%}")
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

try:
    from scipy import stats as scipy_stats
    _HAS_SCIPY = True
except ImportError:
    scipy_stats = None  # type: ignore[assignment]
    _HAS_SCIPY = False

log = logging.getLogger(__name__)

# Annualisation constant (trading days per year)
_TRADING_DAYS = 252


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean(returns: pd.Series) -> pd.Series:
    """Drop NaN/Inf values and return a clean copy."""
    s = returns.dropna()
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    return s


def _require_min(s: pd.Series, n: int = 2) -> bool:
    """Return True if series has at least *n* valid observations."""
    return len(s) >= n


# ---------------------------------------------------------------------------
# Return metrics
# ---------------------------------------------------------------------------


def total_return(returns: pd.Series) -> float:
    """
    Compute the cumulative total return over the period.

    Parameters
    ----------
    returns:
        Daily return series.

    Returns
    -------
    float
        Total return as a decimal (e.g. 0.15 = 15%).  Returns 0.0 for an
        empty or all-NaN series.
    """
    s = _clean(returns)
    if s.empty:
        return 0.0
    return float((1.0 + s).prod() - 1.0)


def cagr(returns: pd.Series) -> float:
    """
    Compound Annual Growth Rate.

    Uses the actual calendar-day count between the first and last index
    entry; falls back to ``len(returns) / 252`` when the index is not
    datetime-based.

    Parameters
    ----------
    returns:
        Daily return series with a DatetimeIndex (preferred).

    Returns
    -------
    float
        CAGR as a decimal.  Returns 0.0 for < 2 observations.
    """
    s = _clean(returns)
    if not _require_min(s, 2):
        return 0.0

    cumulative = (1.0 + s).prod()
    if cumulative <= 0.0:
        return -1.0

    try:
        years = (s.index[-1] - s.index[0]).days / 365.25
    except (TypeError, AttributeError):
        years = len(s) / _TRADING_DAYS

    if years <= 0:
        return 0.0

    return float(cumulative ** (1.0 / years) - 1.0)


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Annualised Sharpe ratio (annualisation factor = sqrt(252)).

    Parameters
    ----------
    returns:
        Daily return series.
    risk_free_rate:
        Annual risk-free rate as a decimal (e.g. 0.02 = 2%).

    Returns
    -------
    float
        Sharpe ratio.  Returns 0.0 if volatility is zero or series is empty.
    """
    s = _clean(returns)
    if not _require_min(s, 2):
        return 0.0

    daily_rf = risk_free_rate / _TRADING_DAYS
    excess = s - daily_rf
    std = excess.std(ddof=1)

    if std == 0.0 or math.isnan(std):
        return 0.0

    return float(excess.mean() / std * math.sqrt(_TRADING_DAYS))


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Annualised Sortino ratio using downside deviation.

    Parameters
    ----------
    returns:
        Daily return series.
    risk_free_rate:
        Annual risk-free rate as a decimal.

    Returns
    -------
    float
        Sortino ratio.  Returns 0.0 if there are no negative returns or
        the series is empty.
    """
    s = _clean(returns)
    if not _require_min(s, 2):
        return 0.0

    daily_rf = risk_free_rate / _TRADING_DAYS
    excess = s - daily_rf
    downside = excess[excess < 0]

    if downside.empty:
        # No negative excess returns — theoretically infinite Sortino
        return float("inf")

    downside_std = math.sqrt((downside ** 2).mean())

    if downside_std == 0.0:
        return 0.0

    return float(excess.mean() / downside_std * math.sqrt(_TRADING_DAYS))


def max_drawdown(returns: pd.Series) -> float:
    """
    Maximum peak-to-trough decline (always <= 0).

    Parameters
    ----------
    returns:
        Daily return series.

    Returns
    -------
    float
        Maximum drawdown as a negative decimal (e.g. -0.35 = -35%).
        Returns 0.0 for an empty series.
    """
    s = _clean(returns)
    if s.empty:
        return 0.0

    cum = (1.0 + s).cumprod()
    running_max = cum.cummax()
    drawdowns = cum / running_max - 1.0
    return float(drawdowns.min())


def max_drawdown_duration(returns: pd.Series) -> int:
    """
    Number of days in the longest drawdown period.

    A drawdown period starts when the equity curve falls below its
    previous peak and ends when it recovers to (or exceeds) that peak.

    Parameters
    ----------
    returns:
        Daily return series.

    Returns
    -------
    int
        Length of the longest drawdown in trading days.  Returns 0 for
        an empty series or when no drawdown exists.
    """
    s = _clean(returns)
    if s.empty:
        return 0

    cum = (1.0 + s).cumprod()
    running_max = cum.cummax()
    underwater = cum < running_max

    if not underwater.any():
        return 0

    max_dur = 0
    current_dur = 0

    for in_dd in underwater:
        if in_dd:
            current_dur += 1
            max_dur = max(max_dur, current_dur)
        else:
            current_dur = 0

    return int(max_dur)


def calmar_ratio(returns: pd.Series) -> float:
    """
    Calmar ratio = CAGR / |max drawdown|.

    Parameters
    ----------
    returns:
        Daily return series.

    Returns
    -------
    float
        Calmar ratio.  Returns 0.0 when max drawdown is zero.
        Returns ``float('inf')`` when max drawdown is zero but CAGR > 0.
    """
    s = _clean(returns)
    if not _require_min(s, 2):
        return 0.0

    mdd = max_drawdown(s)
    if mdd == 0.0:
        c = cagr(s)
        return float("inf") if c > 0 else 0.0

    return float(cagr(s) / abs(mdd))


# ---------------------------------------------------------------------------
# Trade-level metrics
# ---------------------------------------------------------------------------


def win_rate(trade_returns: pd.Series) -> float:
    """
    Fraction of trades with a positive return.

    Parameters
    ----------
    trade_returns:
        Series of per-trade returns.

    Returns
    -------
    float
        Win rate in [0, 1].  Returns 0.0 for an empty series.
    """
    s = _clean(trade_returns)
    if s.empty:
        return 0.0
    return float((s > 0).sum() / len(s))


def profit_factor(trade_returns: pd.Series) -> float:
    """
    Gross profit divided by gross loss (absolute value).

    Parameters
    ----------
    trade_returns:
        Series of per-trade returns.

    Returns
    -------
    float
        Profit factor.  Returns ``float('inf')`` when there are no losing
        trades.  Returns 0.0 when there are no winning trades.
    """
    s = _clean(trade_returns)
    if s.empty:
        return 0.0

    wins = s[s > 0].sum()
    losses = s[s < 0].abs().sum()

    if losses == 0.0:
        return float("inf") if wins > 0 else 0.0

    return float(wins / losses)


def avg_win_loss_ratio(trade_returns: pd.Series) -> float:
    """
    Average winning trade return divided by average losing trade return.

    Parameters
    ----------
    trade_returns:
        Series of per-trade returns.

    Returns
    -------
    float
        Ratio of average win to average loss (absolute).  Returns
        ``float('inf')`` when there are no losses, 0.0 when there are no wins.
    """
    s = _clean(trade_returns)
    if s.empty:
        return 0.0

    winners = s[s > 0]
    losers = s[s < 0]

    if winners.empty:
        return 0.0
    if losers.empty:
        return float("inf")

    return float(winners.mean() / abs(losers.mean()))


# ---------------------------------------------------------------------------
# Distribution metrics
# ---------------------------------------------------------------------------


def skewness(returns: pd.Series) -> float:
    """
    Sample skewness of the return distribution.

    Parameters
    ----------
    returns:
        Daily return series.

    Returns
    -------
    float
        Skewness.  Returns 0.0 for < 3 observations.
    """
    s = _clean(returns)
    if not _require_min(s, 3):
        return 0.0
    if _HAS_SCIPY:
        return float(scipy_stats.skew(s.values, bias=False))
    # Pure-NumPy unbiased skewness
    n = len(s)
    x = s.values - s.values.mean()
    m2 = (x ** 2).mean()
    m3 = (x ** 3).mean()
    if m2 == 0.0:
        return 0.0
    skew_b = m3 / (m2 ** 1.5)
    # Fisher & Pearson correction
    return float(skew_b * math.sqrt(n * (n - 1)) / (n - 2))


def kurtosis(returns: pd.Series) -> float:
    """
    Excess kurtosis (Fisher's definition: normal dist = 0).

    Parameters
    ----------
    returns:
        Daily return series.

    Returns
    -------
    float
        Excess kurtosis.  Returns 0.0 for < 4 observations.
    """
    s = _clean(returns)
    if not _require_min(s, 4):
        return 0.0
    if _HAS_SCIPY:
        return float(scipy_stats.kurtosis(s.values, fisher=True, bias=False))
    # Pure-NumPy unbiased excess kurtosis (Fisher's definition)
    n = len(s)
    x = s.values - s.values.mean()
    m2 = (x ** 2).mean()
    m4 = (x ** 4).mean()
    if m2 == 0.0:
        return 0.0
    kurt_b = m4 / (m2 ** 2) - 3.0
    # Unbiased correction
    correction = (n - 1) / ((n - 2) * (n - 3)) * ((n + 1) * kurt_b + 6)
    return float(correction)


def var(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Historical Value at Risk (VaR) at the given confidence level.

    Returns the *loss* at the given percentile — expressed as a positive
    number representing the magnitude of the potential loss.

    Parameters
    ----------
    returns:
        Daily return series.
    confidence:
        Confidence level in (0, 1).  Default 0.95.

    Returns
    -------
    float
        VaR as a positive decimal (e.g. 0.02 = 2% daily loss at 95% conf).
        Returns 0.0 for an empty series.
    """
    s = _clean(returns)
    if s.empty:
        return 0.0
    return float(-np.percentile(s.values, (1.0 - confidence) * 100))


def cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    """
    Conditional VaR (Expected Shortfall) at the given confidence level.

    The average of returns that fall below the VaR threshold.

    Parameters
    ----------
    returns:
        Daily return series.
    confidence:
        Confidence level in (0, 1).  Default 0.95.

    Returns
    -------
    float
        CVaR as a positive decimal.  Returns 0.0 for an empty series.
    """
    s = _clean(returns)
    if s.empty:
        return 0.0

    threshold = np.percentile(s.values, (1.0 - confidence) * 100)
    tail = s[s <= threshold]

    if tail.empty:
        return 0.0

    return float(-tail.mean())


# ---------------------------------------------------------------------------
# Benchmark-relative metrics
# ---------------------------------------------------------------------------


def beta(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    Regression beta versus a benchmark.

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark_returns:
        Benchmark daily return series (must overlap with *returns*).

    Returns
    -------
    float
        Beta.  Returns 1.0 if regression cannot be computed.
    """
    s = _clean(returns)
    b = _clean(benchmark_returns)
    aligned = pd.concat([s, b], axis=1).dropna()

    if len(aligned) < 2:
        return float("nan")

    strat = aligned.iloc[:, 0].values
    bench = aligned.iloc[:, 1].values

    bench_var = np.var(bench, ddof=1)
    if bench_var == 0.0:
        return float("nan")

    cov = np.cov(strat, bench, ddof=1)[0, 1]
    return float(cov / bench_var)


def alpha(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Jensen's alpha (annualised).

    alpha = annualised_return - (rf + beta * (benchmark_annualised - rf))

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark_returns:
        Benchmark daily return series.
    risk_free_rate:
        Annual risk-free rate as a decimal.

    Returns
    -------
    float
        Annualised Jensen's alpha.  Returns 0.0 if calculation fails.
    """
    s = _clean(returns)
    b = _clean(benchmark_returns)

    if not _require_min(s, 2) or not _require_min(b, 2):
        return 0.0

    beta_val = beta(s, b)
    if math.isnan(beta_val):
        return 0.0

    strat_cagr = cagr(s)
    bench_cagr = cagr(b)

    return float(strat_cagr - (risk_free_rate + beta_val * (bench_cagr - risk_free_rate)))


def information_ratio(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    Information ratio = annualised active return / tracking error.

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark_returns:
        Benchmark daily return series.

    Returns
    -------
    float
        Information ratio.  Returns 0.0 if tracking error is zero.
    """
    s = _clean(returns)
    b = _clean(benchmark_returns)
    aligned = pd.concat([s, b], axis=1).dropna()

    if len(aligned) < 2:
        return 0.0

    active = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    te = active.std(ddof=1) * math.sqrt(_TRADING_DAYS)

    if te == 0.0:
        return 0.0

    return float(active.mean() * _TRADING_DAYS / te)


def treynor_ratio(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Treynor ratio = (annualised excess return) / beta.

    Parameters
    ----------
    returns:
        Strategy daily return series.
    benchmark_returns:
        Benchmark daily return series.
    risk_free_rate:
        Annual risk-free rate.

    Returns
    -------
    float
        Treynor ratio.  Returns 0.0 if beta is zero or NaN.
    """
    s = _clean(returns)
    b = _clean(benchmark_returns)

    if not _require_min(s, 2):
        return 0.0

    beta_val = beta(s, b)
    if math.isnan(beta_val) or beta_val == 0.0:
        return 0.0

    strat_cagr = cagr(s)
    return float((strat_cagr - risk_free_rate) / beta_val)


# ---------------------------------------------------------------------------
# Operational metric
# ---------------------------------------------------------------------------


def annual_turnover(trades: pd.Series, avg_portfolio_value: float) -> float:
    """
    Annualised portfolio turnover.

    Turnover = total traded value / average portfolio value, annualised.

    Parameters
    ----------
    trades:
        Series of trade values (absolute notional per trade), indexed by
        datetime.
    avg_portfolio_value:
        Average portfolio value over the period.

    Returns
    -------
    float
        Annual turnover as a decimal (e.g. 2.0 = 200% annual turnover).
        Returns 0.0 if ``avg_portfolio_value`` is zero or ``trades`` is empty.
    """
    if trades is None or trades.empty or avg_portfolio_value == 0.0:
        return 0.0

    t = _clean(trades).abs()
    if t.empty:
        return 0.0

    # Determine number of years
    try:
        years = (t.index[-1] - t.index[0]).days / 365.25
    except (TypeError, AttributeError):
        years = len(t) / _TRADING_DAYS

    if years <= 0:
        return 0.0

    total_traded = float(t.sum())
    return float(total_traded / avg_portfolio_value / years)


# ---------------------------------------------------------------------------
# Master aggregator
# ---------------------------------------------------------------------------


def calculate_all(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    trade_returns: Optional[pd.Series] = None,
    risk_free_rate: float = 0.0,
) -> dict:
    """
    Compute all available metrics and return them as a flat dict.

    Parameters
    ----------
    returns:
        Strategy daily return series (DatetimeIndex preferred).
    benchmark_returns:
        Optional benchmark daily return series.  When supplied, the
        benchmark-relative metrics (alpha, beta, IR, Treynor) are included.
    trade_returns:
        Optional per-trade return series.  When supplied, trade-level
        metrics (win rate, profit factor, avg win/loss) are included.
    risk_free_rate:
        Annual risk-free rate used in Sharpe, Sortino, alpha, and Treynor.

    Returns
    -------
    dict
        Dictionary of metric name → float value.
    """
    m: dict = {}

    # --- Core return metrics ---
    m["total_return"] = total_return(returns)
    m["cagr"] = cagr(returns)
    m["sharpe_ratio"] = sharpe_ratio(returns, risk_free_rate)
    m["sortino_ratio"] = sortino_ratio(returns, risk_free_rate)
    m["calmar_ratio"] = calmar_ratio(returns)

    # --- Drawdown ---
    m["max_drawdown"] = max_drawdown(returns)
    m["max_drawdown_duration_days"] = max_drawdown_duration(returns)

    # --- Distribution ---
    m["skewness"] = skewness(returns)
    m["kurtosis"] = kurtosis(returns)
    m["var_95"] = var(returns, confidence=0.95)
    m["cvar_95"] = cvar(returns, confidence=0.95)
    m["var_99"] = var(returns, confidence=0.99)
    m["cvar_99"] = cvar(returns, confidence=0.99)

    # --- Volatility ---
    s = _clean(returns)
    m["annual_volatility"] = float(s.std(ddof=1) * math.sqrt(_TRADING_DAYS)) if len(s) >= 2 else 0.0
    m["daily_volatility"] = float(s.std(ddof=1)) if len(s) >= 2 else 0.0

    # --- Benchmark-relative metrics ---
    if benchmark_returns is not None:
        m["beta"] = beta(returns, benchmark_returns)
        m["alpha"] = alpha(returns, benchmark_returns, risk_free_rate)
        m["information_ratio"] = information_ratio(returns, benchmark_returns)
        m["treynor_ratio"] = treynor_ratio(returns, benchmark_returns, risk_free_rate)
    else:
        m["beta"] = float("nan")
        m["alpha"] = float("nan")
        m["information_ratio"] = float("nan")
        m["treynor_ratio"] = float("nan")

    # --- Trade-level metrics ---
    if trade_returns is not None:
        m["win_rate"] = win_rate(trade_returns)
        m["profit_factor"] = profit_factor(trade_returns)
        m["avg_win_loss_ratio"] = avg_win_loss_ratio(trade_returns)
        m["n_trades"] = int(len(_clean(trade_returns)))
        m["avg_trade_return"] = float(_clean(trade_returns).mean()) if not _clean(trade_returns).empty else 0.0
    else:
        m["win_rate"] = float("nan")
        m["profit_factor"] = float("nan")
        m["avg_win_loss_ratio"] = float("nan")
        m["n_trades"] = 0
        m["avg_trade_return"] = float("nan")

    return m


__all__ = [
    "total_return",
    "cagr",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "max_drawdown_duration",
    "calmar_ratio",
    "win_rate",
    "profit_factor",
    "avg_win_loss_ratio",
    "skewness",
    "kurtosis",
    "var",
    "cvar",
    "beta",
    "alpha",
    "information_ratio",
    "treynor_ratio",
    "annual_turnover",
    "calculate_all",
]
