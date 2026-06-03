"""
Feature engineering for the Quantify trading system.

Architecture
------------
``FeatureEngine`` maintains a registry of named feature functions.  Each
function takes a single-symbol OHLCV DataFrame and returns a pd.Series
aligned to that DataFrame's index.

Features are registered with the ``@register_feature(name)`` decorator:

    @register_feature("my_feature")
    def _my_feature(df: pd.DataFrame) -> pd.Series:
        return df["close"].rolling(10).mean()

Then computed via:

    engine = FeatureEngine()
    result = engine.compute({"AAPL": df_aapl}, required=["sma_50", "rsi_14"])

``pandas_ta`` is used for all technical indicators where available.

Registered features
-------------------
Returns        : return_1d, return_5d, return_21d, return_63d,
                 return_126d, return_252d
Volatility     : volatility_20d, volatility_60d, volatility_126d,
                 volatility_252d
Momentum       : rsi_14, macd_histogram
Bands          : bollinger_width
Moving averages: sma_50, sma_200, sma_crossover
Volume         : volume_ratio_20d, obv_slope
Liquidity      : amihud_illiquidity
Volatility ATR : atr_14
"""

from __future__ import annotations

import functools
import logging
from typing import Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional pandas_ta import
# ---------------------------------------------------------------------------
try:
    import pandas_ta as ta  # type: ignore[import]

    _TA_AVAILABLE = True
except ImportError:
    _TA_AVAILABLE = False
    logger.warning(
        "pandas_ta is not installed.  Technical indicators will fall back to "
        "manual implementations.  Install with: pip install pandas-ta"
    )

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
FeatureFn = Callable[[pd.DataFrame], pd.Series]

# ---------------------------------------------------------------------------
# Global feature registry
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, FeatureFn] = {}


def register_feature(name: str) -> Callable[[FeatureFn], FeatureFn]:
    """
    Decorator that registers a feature function under *name*.

    Parameters
    ----------
    name:
        Unique string key used to request the feature via
        :meth:`FeatureEngine.compute`.

    Returns
    -------
    Callable
        The original function, unmodified.

    Raises
    ------
    ValueError
        If *name* is already registered.

    Example
    -------
    >>> @register_feature("my_signal")
    ... def _my_signal(df: pd.DataFrame) -> pd.Series:
    ...     return df["close"].pct_change()
    """

    def decorator(fn: FeatureFn) -> FeatureFn:
        if name in _REGISTRY:
            raise ValueError(
                f"Feature {name!r} is already registered.  "
                "Use a unique name or call FeatureEngine.unregister() first."
            )
        _REGISTRY[name] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# FeatureEngine
# ---------------------------------------------------------------------------


class FeatureEngine:
    """
    Computes a named set of features for multiple symbols.

    Parameters
    ----------
    extra_features:
        Optional dict of additional ``{name: fn}`` entries that extend (or
        override) the global registry for this instance only.

    Examples
    --------
    >>> engine = FeatureEngine()
    >>> results = engine.compute(data, required=["rsi_14", "sma_crossover"])
    >>> results["AAPL"]["rsi_14"].tail()
    """

    def __init__(
        self,
        extra_features: dict[str, FeatureFn] | None = None,
    ) -> None:
        self._registry: dict[str, FeatureFn] = dict(_REGISTRY)
        if extra_features:
            self._registry.update(extra_features)

    def available_features(self) -> list[str]:
        """Return a sorted list of all registered feature names."""
        return sorted(self._registry)

    def register(self, name: str, fn: FeatureFn) -> None:
        """Register (or overwrite) a feature on this instance."""
        self._registry[name] = fn

    def unregister(self, name: str) -> None:
        """Remove a feature from this instance's registry."""
        self._registry.pop(name, None)

    def compute(
        self,
        data: dict[str, pd.DataFrame],
        required: list[str],
    ) -> dict[str, pd.DataFrame]:
        """
        Compute *required* features for every symbol in *data*.

        Parameters
        ----------
        data:
            Mapping from ticker symbol to its OHLCV DataFrame.
        required:
            List of feature names to compute (must all be registered).

        Returns
        -------
        dict[str, pd.DataFrame]
            Mapping from ticker symbol to a DataFrame whose columns are the
            requested feature names, aligned to the input DataFrame's index.

        Raises
        ------
        KeyError
            If a requested feature is not registered.
        """
        # Validate requested features upfront
        missing = [f for f in required if f not in self._registry]
        if missing:
            raise KeyError(
                f"Unknown features: {missing}.  "
                f"Available: {self.available_features()}"
            )

        results: dict[str, pd.DataFrame] = {}

        for symbol, df in data.items():
            if df.empty:
                logger.warning("Skipping %s: empty DataFrame.", symbol)
                continue

            feature_series: dict[str, pd.Series] = {}
            for feat_name in required:
                fn = self._registry[feat_name]
                try:
                    series = fn(df)
                    series = series.replace([np.inf, -np.inf], np.nan)
                    # Enforce consistent name
                    series.name = feat_name
                    feature_series[feat_name] = series
                except Exception as exc:
                    logger.warning(
                        "Feature %r failed for %s: %s", feat_name, symbol, exc
                    )
                    # Fill with NaN so callers can detect the failure
                    feature_series[feat_name] = pd.Series(
                        np.nan, index=df.index, name=feat_name
                    )

            results[symbol] = pd.DataFrame(feature_series, index=df.index)

        return results

    def compute_single(
        self,
        df: pd.DataFrame,
        required: list[str],
    ) -> pd.DataFrame:
        """
        Convenience wrapper for a single-symbol DataFrame.

        Returns a DataFrame with the requested features as columns.
        """
        sym_results = self.compute({"__single__": df}, required)
        return sym_results.get("__single__", pd.DataFrame(index=df.index))


# ---------------------------------------------------------------------------
# Helper: safe rolling returns
# ---------------------------------------------------------------------------


def _log_return(close: pd.Series) -> pd.Series:
    """Log return: ln(P_t / P_{t-1})."""
    return np.log(close / close.shift(1))


def _pct_return(close: pd.Series, periods: int) -> pd.Series:
    """Simple N-period percent return."""
    return close.pct_change(periods)


# ===========================================================================
# REGISTERED FEATURES
# ===========================================================================

# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------

for _N in [1, 5, 21, 63, 126, 252]:

    def _make_return_fn(n: int) -> FeatureFn:
        @functools.wraps(_pct_return)
        def _fn(df: pd.DataFrame) -> pd.Series:
            return _pct_return(df["close"], n)

        _fn.__name__ = f"return_{n}d"
        return _fn

    register_feature(f"return_{_N}d")(_make_return_fn(_N))

# ---------------------------------------------------------------------------
# Volatility (annualised, rolling std of log returns)
# ---------------------------------------------------------------------------

_ANN_FACTOR = np.sqrt(252)

for _N in [20, 60, 126, 252]:

    def _make_vol_fn(n: int) -> FeatureFn:
        def _fn(df: pd.DataFrame) -> pd.Series:
            lr = _log_return(df["close"])
            return lr.rolling(n).std() * _ANN_FACTOR

        _fn.__name__ = f"volatility_{n}d"
        return _fn

    register_feature(f"volatility_{_N}d")(_make_vol_fn(_N))

# ---------------------------------------------------------------------------
# RSI 14
# ---------------------------------------------------------------------------


@register_feature("rsi_14")
def _rsi_14(df: pd.DataFrame) -> pd.Series:
    """14-period Relative Strength Index (0–100)."""
    if _TA_AVAILABLE:
        result = ta.rsi(df["close"], length=14)
        if result is None:
            return pd.Series(np.nan, index=df.index)
        result = result.reindex(df.index)
        result.iloc[:14] = np.nan
        return result

    # Manual Wilder RSI
    delta = df["close"].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(com=13, min_periods=14).mean()
    avg_loss = loss.ewm(com=13, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi.iloc[:14] = np.nan
    return rsi


# ---------------------------------------------------------------------------
# MACD histogram
# ---------------------------------------------------------------------------


@register_feature("macd_histogram")
def _macd_histogram(df: pd.DataFrame) -> pd.Series:
    """MACD histogram: MACD line minus signal line (12/26/9 defaults)."""
    if _TA_AVAILABLE:
        try:
            result = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if result is not None and not result.empty:
                # pandas_ta returns a DataFrame; check for common histogram column patterns
                # Patterns: 'MACDh_12_26_9', 'MACD_Hist', etc.
                hist_col = [c for c in result.columns if "H" in c.upper().split("_")[-1] or "HIST" in c.upper()]
                if hist_col:
                    return result[hist_col[0]]
        except Exception:
            pass # fall through to manual

    # Manual MACD (Exponential Moving Average based)
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line - signal_line


# ---------------------------------------------------------------------------
# Bollinger Band Width
# ---------------------------------------------------------------------------


@register_feature("bollinger_width")
def _bollinger_width(df: pd.DataFrame) -> pd.Series:
    """
    Bollinger Band Width: (upper - lower) / middle, using 20-period SMA
    and 2 standard deviations.
    """
    if _TA_AVAILABLE:
        result = ta.bbands(df["close"], length=20, std=2)
        if result is not None and not result.empty:
            # pandas_ta BBands columns: BBL_20_2.0, BBM_20_2.0, BBU_20_2.0, BBB_20_2.0, BBP_20_2.0
            bbu_col = [c for c in result.columns if "BBU" in c.upper()]
            bbl_col = [c for c in result.columns if "BBL" in c.upper()]
            bbm_col = [c for c in result.columns if "BBM" in c.upper()]
            if bbu_col and bbl_col and bbm_col:
                return (result[bbu_col[0]] - result[bbl_col[0]]) / result[bbm_col[0]]
        return pd.Series(np.nan, index=df.index)

    # Manual
    middle = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    upper = middle + 2 * std
    lower = middle - 2 * std
    return (upper - lower) / middle


# ---------------------------------------------------------------------------
# Simple Moving Averages
# ---------------------------------------------------------------------------


@register_feature("sma_50")
def _sma_50(df: pd.DataFrame) -> pd.Series:
    """50-period simple moving average of close."""
    if _TA_AVAILABLE:
        result = ta.sma(df["close"], length=50)
        return result if result is not None else df["close"].rolling(50).mean()
    return df["close"].rolling(50).mean()


@register_feature("sma_200")
def _sma_200(df: pd.DataFrame) -> pd.Series:
    """200-period simple moving average of close."""
    if _TA_AVAILABLE:
        result = ta.sma(df["close"], length=200)
        return result if result is not None else df["close"].rolling(200).mean()
    return df["close"].rolling(200).mean()


@register_feature("sma_crossover")
def _sma_crossover(df: pd.DataFrame) -> pd.Series:
    """
    Golden/Death Cross indicator.

    Returns 1.0 when SMA-50 > SMA-200 (bullish), 0.0 otherwise.
    NaN where either SMA is undefined.
    """
    sma50 = _sma_50(df)
    sma200 = _sma_200(df)
    crossover = (sma50 > sma200).astype(float)
    # Mask rows where either SMA is NaN
    crossover[sma50.isna() | sma200.isna()] = np.nan
    return crossover


# ---------------------------------------------------------------------------
# Volume ratio
# ---------------------------------------------------------------------------


@register_feature("volume_ratio_20d")
def _volume_ratio_20d(df: pd.DataFrame) -> pd.Series:
    """
    Volume relative to 20-day average volume.

    Values > 1 indicate above-average activity; < 1 below-average.
    """
    avg_vol = df["volume"].rolling(20).mean()
    return df["volume"] / avg_vol


# ---------------------------------------------------------------------------
# OBV slope
# ---------------------------------------------------------------------------


@register_feature("obv_slope")
def _obv_slope(df: pd.DataFrame) -> pd.Series:
    """
    Slope of On-Balance Volume (OBV) over a 20-day rolling window.

    OBV accumulates volume with a sign determined by whether close was up
    or down.  The slope is computed via ordinary least squares on each
    20-day window and normalised by the mean OBV level in that window so
    it is dimensionless.
    """
    if _TA_AVAILABLE:
        obv = ta.obv(df["close"], df["volume"])
        if obv is None:
            obv = _compute_obv(df)
    else:
        obv = _compute_obv(df)

    # Rolling OLS slope (normalised)
    window = 20
    slopes = pd.Series(np.nan, index=df.index)
    x = np.arange(window, dtype=float)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()

    obv_arr = obv.values.astype(float)
    for i in range(window - 1, len(obv_arr)):
        y = obv_arr[i - window + 1 : i + 1]
        if np.any(np.isnan(y)):
            continue
        y_mean = y.mean()
        if y_mean == 0:
            continue
        slope = ((x - x_mean) * (y - y_mean)).sum() / x_var
        slopes.iloc[i] = slope / abs(y_mean)  # normalise

    return slopes


def _compute_obv(df: pd.DataFrame) -> pd.Series:
    """Manual OBV computation."""
    direction = np.sign(df["close"].diff().fillna(0))
    return (direction * df["volume"]).cumsum()


# ---------------------------------------------------------------------------
# Amihud Illiquidity
# ---------------------------------------------------------------------------


@register_feature("amihud_illiquidity")
def _amihud_illiquidity(df: pd.DataFrame) -> pd.Series:
    """
    Amihud (2002) illiquidity ratio.

    Defined as the 20-day rolling mean of |return| / dollar_volume.
    Higher values indicate less liquid stocks (price moves more per dollar
    traded).  Result is multiplied by 1e6 to give a more interpretable scale.
    """
    ret = df["close"].pct_change().abs()
    dollar_vol = df["close"] * df["volume"]
    # Avoid division by zero
    illiq = ret / dollar_vol.replace(0, np.nan)
    return illiq.rolling(20).mean() * 1e6


# ---------------------------------------------------------------------------
# ATR 14
# ---------------------------------------------------------------------------


@register_feature("atr_14")
def _atr_14(df: pd.DataFrame) -> pd.Series:
    """
    Average True Range over 14 periods.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|).
    """
    if _TA_AVAILABLE:
        result = ta.atr(df["high"], df["low"], df["close"], length=14)
        if result is not None:
            return result
        # fall through to manual

    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(com=13, min_periods=14).mean()


# ---------------------------------------------------------------------------
# Return dispersion / higher-moment features (Gu et al. 2020)
# ---------------------------------------------------------------------------


@register_feature("return_std_21d")
def _return_std_21d(df: pd.DataFrame) -> pd.Series:
    """21-day rolling standard deviation of daily returns (idiosyncratic risk proxy)."""
    return df["close"].pct_change().rolling(21, min_periods=15).std()


@register_feature("skewness_21d")
def _skewness_21d(df: pd.DataFrame) -> pd.Series:
    """21-day rolling skewness of daily returns (crash risk indicator)."""
    return df["close"].pct_change().rolling(21, min_periods=15).skew()


@register_feature("max_return_21d")
def _max_return_21d(df: pd.DataFrame) -> pd.Series:
    """Maximum single-day return over the last 21 trading days (lottery demand)."""
    return df["close"].pct_change().rolling(21, min_periods=15).max()


@register_feature("min_return_21d")
def _min_return_21d(df: pd.DataFrame) -> pd.Series:
    """Minimum single-day return over the last 21 trading days (tail risk)."""
    return df["close"].pct_change().rolling(21, min_periods=15).min()


# ---------------------------------------------------------------------------
# Anchoring / reference-point features (George & Hwang, 2004)
# ---------------------------------------------------------------------------


@register_feature("price_to_high_52w")
def _price_to_high_52w(df: pd.DataFrame) -> pd.Series:
    """Ratio of current price to 52-week (252-day) rolling high (anchoring bias)."""
    high_52w = df["high"].rolling(252, min_periods=126).max()
    return df["close"] / high_52w


@register_feature("price_to_low_52w")
def _price_to_low_52w(df: pd.DataFrame) -> pd.Series:
    """Ratio of current price to 52-week (252-day) rolling low."""
    low_52w = df["low"].rolling(252, min_periods=126).min()
    return df["close"] / low_52w


# ---------------------------------------------------------------------------
# Volume-based features
# ---------------------------------------------------------------------------


@register_feature("volume_trend")
def _volume_trend(df: pd.DataFrame) -> pd.Series:
    """Linear regression slope of volume over 20 days, normalised by mean volume."""
    window = 20
    slopes = pd.Series(np.nan, index=df.index)
    x = np.arange(window, dtype=float)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()

    vol_arr = df["volume"].values.astype(float)
    for i in range(window - 1, len(vol_arr)):
        y = vol_arr[i - window + 1 : i + 1]
        if np.any(np.isnan(y)):
            continue
        y_mean = y.mean()
        if y_mean == 0:
            continue
        slope = ((x - x_mean) * (y - y_mean)).sum() / x_var
        slopes.iloc[i] = slope / abs(y_mean)

    return slopes


# ---------------------------------------------------------------------------
# Return quality / consistency features
# ---------------------------------------------------------------------------


@register_feature("return_consistency")
def _return_consistency(df: pd.DataFrame) -> pd.Series:
    """Fraction of positive-return days over the last 21 trading days."""
    daily_ret = df["close"].pct_change()
    positive = (daily_ret > 0).astype(float)
    return positive.rolling(21, min_periods=15).mean()


@register_feature("gap_return")
def _gap_return(df: pd.DataFrame) -> pd.Series:
    """
    20-day average of overnight gap return: (open_t - close_{t-1}) / close_{t-1}.
    Captures overnight sentiment and news impact.
    """
    prev_close = df["close"].shift(1)
    gap = (df["open"] - prev_close) / prev_close
    return gap.rolling(20, min_periods=10).mean()


@register_feature("intraday_range")
def _intraday_range(df: pd.DataFrame) -> pd.Series:
    """
    20-day average of (high - low) / close.
    Proxy for realized intraday volatility.
    """
    daily_range = (df["high"] - df["low"]) / df["close"]
    return daily_range.rolling(20, min_periods=10).mean()


# ---------------------------------------------------------------------------
# Interaction / composite features
# ---------------------------------------------------------------------------


@register_feature("rsi_divergence")
def _rsi_divergence(df: pd.DataFrame) -> pd.Series:
    """
    RSI divergence: sign(21d price change) vs sign(21d RSI change).
    Returns +1 for bullish divergence (price down, RSI up),
    −1 for bearish divergence (price up, RSI down), 0 for agreement.
    """
    rsi = _rsi_14(df)
    price_change = df["close"].pct_change(21)
    rsi_change = rsi.diff(21)
    price_sign = np.sign(price_change)
    rsi_sign = np.sign(rsi_change)
    # Divergence = when they disagree
    divergence = rsi_sign - price_sign  # +2 = bullish div, -2 = bearish div
    return divergence / 2.0  # normalise to [-1, +1]


@register_feature("mean_reversion_5d")
def _mean_reversion_5d(df: pd.DataFrame) -> pd.Series:
    """
    Mean-reversion interaction: 5d return × 21d return.
    Negative values suggest short-term reversal of medium-term trend.
    """
    ret_5d = df["close"].pct_change(5)
    ret_21d = df["close"].pct_change(21)
    return ret_5d * ret_21d


# ---------------------------------------------------------------------------
# Expose the global registry for inspection
# ---------------------------------------------------------------------------


def list_features() -> list[str]:
    """Return a sorted list of all globally registered feature names."""
    return sorted(_REGISTRY)
