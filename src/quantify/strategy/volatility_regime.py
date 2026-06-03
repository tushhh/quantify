"""
quantify.strategy.volatility_regime
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Volatility Regime Overlay (meta-strategy).

Academic basis
--------------
Ang, A., & Bekaert, G. (2002). "International asset allocation with regime
shifts." Review of Financial Studies, 15(4), 1137–1187.

Hidden Markov / regime-switching models show that financial markets alternate
between distinct volatility states.  Asset prices behave very differently in
high- vs. low-volatility regimes, and portfolio strategies benefit from scaling
risk exposure according to the current regime.

Turbulence measure
------------------
Kritzman, M., Li, Y., Page, S., & Rigobon, R. (2011). "Principal Components
as a Measure of Systemic Risk." Journal of Portfolio Management, 37(4), 112–126.

The Mahalanobis distance of a vector of current returns from its historical
mean (using the inverse covariance) captures systemic co-movement that simple
volatility measures miss.

Regime classification
---------------------
  - Low vol     : VIX < 15             → keep signals, slight +10% boost
  - Normal vol  : 15 ≤ VIX ≤ 25       → keep signals as-is
  - High vol    : VIX > 25             → reduce all strengths by 50%
  - Turbulence  : Mahalanobis distance > 95th-percentile historical level
                  → additional 25% reduction (stacks with high-vol cut)

Usage
-----
This is NOT a standalone strategy.  It wraps other strategies and adjusts
their signals:

    regime_overlay = VolatilityRegimeStrategy()
    adjusted = regime_overlay.adjust_signals(raw_signals, vix_data, sector_returns)

It also implements the ``Strategy`` ABC (``generate_signals`` returns []) so
it can optionally be registered with the engine as a noop source while its
``adjust_signals`` method is called from a portfolio-level orchestrator.

VIX data
--------
Fetched from yfinance (``^VIX``) with the same caching mechanism as other
strategies.  Pass ``vix_data`` as a pd.Series of VIX levels (index = dates)
or let the overlay fetch it automatically via ``get_current_vix()``.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
import pandas as pd

from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regime thresholds
# ---------------------------------------------------------------------------
_VIX_LOW: float = 15.0
_VIX_HIGH: float = 25.0

# Adjustment factors
_HIGH_VOL_SCALE: float = 0.50      # reduce 50% in high vol
_TURBULENCE_SCALE: float = 0.75    # additional 25% when turbulent
_LOW_VOL_BOOST: float = 1.10       # slight 10% boost in calm markets

# Turbulence detection
_TURBULENCE_PERCENTILE: float = 95.0
_MIN_MAHAL_HISTORY: int = 126      # bars needed for stable covariance

# Sector ETFs used for Mahalanobis distance calculation
_SECTOR_ETFS: list[str] = [
    "XLK",  # Technology
    "XLF",  # Financials
    "XLV",  # Health Care
    "XLE",  # Energy
    "XLI",  # Industrials
    "XLY",  # Consumer Discretionary
    "XLP",  # Consumer Staples
    "XLU",  # Utilities
    "XLB",  # Materials
    "XLRE", # Real Estate
    "XLC",  # Communication Services
]

# VIX cache TTL (seconds)
_VIX_CACHE_TTL: float = 3600.0  # 1 hour


class VolatilityRegimeStrategy(Strategy):
    """
    Volatility regime overlay — adjusts signal strengths based on VIX level
    and Mahalanobis distance of sector returns.

    This class implements the full ``Strategy`` ABC but its ``generate_signals``
    method intentionally returns an empty list.  Its primary interface is:

    - :meth:`adjust_signals` — scale a list of signals by regime factor
    - :meth:`get_regime`     — classify a VIX level into "low"/"normal"/"high"
    - :meth:`get_adjustment_factor` — current combined scaling factor

    Parameters
    ----------
    vix_low:
        VIX level below which regime is "low" (default 15).
    vix_high:
        VIX level above which regime is "high" (default 25).
    turbulence_percentile:
        Historical percentile for Mahalanobis turbulence flag (default 95).
    high_vol_scale:
        Multiplier applied to signal strengths in high-vol regime (default 0.50).
    turbulence_scale:
        Additional multiplier when turbulence is detected (default 0.75).
    low_vol_boost:
        Multiplier applied to signal strengths in low-vol regime (default 1.10).
    universe:
        Universe must include the sector ETFs so their data is fetched.
        If not provided, defaults to the 11 SPDR sector ETFs.
    """

    name: str = "volatility_regime"
    rebalance_frequency: str = "daily"
    lookback_days: int = 252

    def __init__(
        self,
        vix_low: float = _VIX_LOW,
        vix_high: float = _VIX_HIGH,
        turbulence_percentile: float = _TURBULENCE_PERCENTILE,
        high_vol_scale: float = _HIGH_VOL_SCALE,
        turbulence_scale: float = _TURBULENCE_SCALE,
        low_vol_boost: float = _LOW_VOL_BOOST,
        universe: Optional[list[str]] = None,
    ) -> None:
        self.vix_low = vix_low
        self.vix_high = vix_high
        self.turbulence_percentile = turbulence_percentile
        self.high_vol_scale = high_vol_scale
        self.turbulence_scale = turbulence_scale
        self.low_vol_boost = low_vol_boost

        # Universe = sector ETFs + VIX (used as a hint for data pipeline)
        self.universe: list[str] = universe if universe is not None else list(_SECTOR_ETFS)

        # State
        self._current_regime: str = "normal"
        self._current_vix: Optional[float] = None
        self._current_mahal: Optional[float] = None
        self._mahal_threshold: Optional[float] = None
        self._is_turbulent: bool = False

        # VIX data cache: (unix_ts, pd.Series)
        self._vix_cache: tuple[float, pd.Series] | None = None

        log.info(
            "VolatilityRegimeStrategy initialised: "
            "VIX thresholds [%.0f, %.0f], "
            "turbulence_pct=%.0f%%",
            vix_low, vix_high, turbulence_percentile,
        )

    def get_required_features(self) -> list[str]:
        """
        Regime overlay needs daily returns from sector ETFs.
        Return_1d is computed from close prices already present in data.
        """
        return ["return_1d"]

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        No stand-alone signals.  Updates internal regime state using the
        latest data, then returns an empty list.

        Side effects: updates ``_current_regime``, ``_current_vix``,
        ``_current_mahal``, ``_is_turbulent``.
        """
        self._update_regime_state(data)
        return []

    # ------------------------------------------------------------------
    # Core public API
    # ------------------------------------------------------------------

    def adjust_signals(
        self,
        signals: list[Signal],
        vix_data: Optional[pd.Series] = None,
        sector_returns: Optional[pd.DataFrame] = None,
    ) -> list[Signal]:
        """
        Apply regime-based scaling to a list of signals.

        Parameters
        ----------
        signals:
            Raw signals emitted by one or more strategies.
        vix_data:
            Optional pd.Series of VIX close levels (index = DatetimeIndex).
            If None, uses the cached value from the last ``generate_signals``
            call or fetches from yfinance.
        sector_returns:
            Optional DataFrame of sector daily returns (index = dates,
            columns = sector ETF tickers) for Mahalanobis computation.
            If None, skips turbulence check.

        Returns
        -------
        list[Signal]
            New Signal objects with adjusted ``strength`` values and
            regime metadata added to ``metadata``.
        """
        if not signals:
            return []

        # Determine VIX level
        vix_value = self._resolve_vix(vix_data)
        regime = self.get_regime(vix_value) if vix_value is not None else self._current_regime

        # Determine turbulence
        is_turbulent = self._check_turbulence(sector_returns)

        factor = self._compute_factor(regime, is_turbulent)

        log.debug(
            "%s: adjust_signals: regime=%s, VIX=%.1f, turbulent=%s, factor=%.2f, "
            "n_signals=%d",
            self.name,
            regime,
            vix_value or 0.0,
            is_turbulent,
            factor,
            len(signals),
        )

        adjusted: list[Signal] = []
        for sig in signals:
            new_strength = float(np.clip(sig.strength * factor, -1.0, 1.0))
            # Build updated metadata
            new_meta = dict(sig.metadata)
            new_meta.update({
                "regime": regime,
                "vix_level": round(vix_value, 2) if vix_value is not None else None,
                "is_turbulent": is_turbulent,
                "regime_factor": round(factor, 4),
                "original_strength": round(sig.strength, 4),
                "mahalanobis_distance": (
                    round(self._current_mahal, 4)
                    if self._current_mahal is not None
                    else None
                ),
            })
            # Signals are frozen dataclasses — create a new instance
            adjusted.append(
                Signal(
                    strategy_name=sig.strategy_name,
                    symbol=sig.symbol,
                    direction=sig.direction,
                    strength=new_strength,
                    timestamp=sig.timestamp,
                    metadata=new_meta,
                )
            )

        return adjusted

    def get_regime(self, vix_value: Optional[float]) -> str:
        """
        Classify a VIX level into a regime string.

        Parameters
        ----------
        vix_value:
            Current VIX index level (or None for unknown).

        Returns
        -------
        str
            ``"low"``, ``"normal"``, or ``"high"``.
            Returns ``"normal"`` for None input.
        """
        if vix_value is None:
            return "normal"
        if vix_value < self.vix_low:
            return "low"
        if vix_value > self.vix_high:
            return "high"
        return "normal"

    def get_adjustment_factor(self) -> float:
        """
        Return the current combined signal scaling factor.

        Based on the last call to ``generate_signals`` or ``adjust_signals``.
        Returns 1.0 if no regime state has been computed yet.
        """
        return self._compute_factor(self._current_regime, self._is_turbulent)

    # ------------------------------------------------------------------
    # VIX fetching
    # ------------------------------------------------------------------

    def get_current_vix(self) -> Optional[float]:
        """
        Fetch the most recent VIX close from yfinance.

        Uses an in-memory cache (TTL 1 hour) to avoid repeated API calls.

        Returns
        -------
        float | None
            The most recent VIX close level, or None on failure.
        """
        now_ts = time.time()
        if self._vix_cache is not None:
            cached_ts, cached_series = self._vix_cache
            if (now_ts - cached_ts) < _VIX_CACHE_TTL:
                return float(cached_series.iloc[-1]) if not cached_series.empty else None

        vix_series = self._fetch_vix()
        if vix_series is None or vix_series.empty:
            return None

        self._vix_cache = (now_ts, vix_series)
        return float(vix_series.iloc[-1])

    @staticmethod
    def _fetch_vix() -> Optional[pd.Series]:
        """
        Fetch ^VIX daily close prices from yfinance.
        Returns a pd.Series or None on failure.
        """
        try:
            import yfinance as yf
            vix = yf.download("^VIX", period="1y", progress=False, auto_adjust=True)
            if vix is None or vix.empty:
                return None
            close = vix["Close"] if "Close" in vix.columns else vix.iloc[:, 0]
            return close.dropna()
        except Exception as exc:
            log.warning("Failed to fetch ^VIX: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Mahalanobis distance / turbulence
    # ------------------------------------------------------------------

    def compute_mahalanobis(
        self,
        sector_returns: pd.DataFrame,
        lookback: int = _MIN_MAHAL_HISTORY,
    ) -> Optional[float]:
        """
        Compute the Mahalanobis distance of the most recent return vector
        from the historical distribution.

        Parameters
        ----------
        sector_returns:
            DataFrame of daily returns, columns = sector ETF tickers.
        lookback:
            Number of historical days to use for covariance estimation.

        Returns
        -------
        float | None
            Mahalanobis distance of today's return vector, or None if
            insufficient history or covariance is singular.
        """
        if sector_returns is None or sector_returns.empty:
            return None

        # Drop columns with too many NaNs
        sector_returns = sector_returns.dropna(axis=1, thresh=int(lookback * 0.7))
        if sector_returns.shape[1] < 2:
            return None

        # Use the last ``lookback`` rows for estimation
        hist = sector_returns.dropna().iloc[-lookback:]
        if len(hist) < 30:
            return None

        mu = hist.mean().values
        cov = hist.cov().values

        # Today's return vector
        today_ret = sector_returns.iloc[-1].values

        if np.any(np.isnan(today_ret)):
            return None

        # Regularise covariance to avoid singularity
        n_assets = cov.shape[0]
        shrinkage = 1e-4 * np.trace(cov) / n_assets
        cov_reg = cov + shrinkage * np.eye(n_assets)

        try:
            inv_cov = np.linalg.inv(cov_reg)
        except np.linalg.LinAlgError:
            log.debug("%s: singular covariance matrix, skipping Mahalanobis", self.name)
            return None

        diff = today_ret - mu
        mahal = float(np.sqrt(diff @ inv_cov @ diff))
        return mahal

    def compute_mahalanobis_history(
        self,
        sector_returns: pd.DataFrame,
        lookback: int = _MIN_MAHAL_HISTORY,
    ) -> pd.Series:
        """
        Compute rolling Mahalanobis distance for the full history.

        Used to determine the turbulence threshold (95th percentile) from
        historical data.

        Parameters
        ----------
        sector_returns:
            DataFrame of daily returns.
        lookback:
            Rolling window for covariance estimation.

        Returns
        -------
        pd.Series
            Series of Mahalanobis distances (NaN where insufficient history).
        """
        if sector_returns.empty:
            return pd.Series(dtype=float)

        n = len(sector_returns)
        distances = pd.Series(np.nan, index=sector_returns.index)

        sector_returns_clean = sector_returns.dropna(axis=1, thresh=int(lookback * 0.7))
        if sector_returns_clean.shape[1] < 2:
            return distances

        for i in range(lookback, n):
            hist = sector_returns_clean.iloc[i - lookback: i].dropna()
            if len(hist) < 30:
                continue
            mu = hist.mean().values
            cov = hist.cov().values
            today = sector_returns_clean.iloc[i].values
            if np.any(np.isnan(today)):
                continue
            n_assets = cov.shape[0]
            shrinkage = 1e-4 * np.trace(cov) / n_assets
            cov_reg = cov + shrinkage * np.eye(n_assets)
            try:
                inv_cov = np.linalg.inv(cov_reg)
            except np.linalg.LinAlgError:
                continue
            diff = today - mu
            distances.iloc[i] = float(np.sqrt(diff @ inv_cov @ diff))

        return distances

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_regime_state(self, data: dict[str, pd.DataFrame]) -> None:
        """
        Update cached regime state from available data.

        Uses sector ETF returns from ``data`` (if available) for Mahalanobis.
        Fetches VIX or reads it from data if ^VIX is in the data dict.
        """
        # ---- VIX from data or yfinance ----
        vix_series = self._extract_vix_from_data(data)
        if vix_series is not None and not vix_series.empty:
            self._current_vix = _last_numeric_value(vix_series)
        else:
            self._current_vix = self.get_current_vix()

        self._current_regime = self.get_regime(self._current_vix)

        # ---- Sector returns for Mahalanobis ----
        sector_returns = self._extract_sector_returns(data)
        if sector_returns is not None and len(sector_returns) >= _MIN_MAHAL_HISTORY:
            self._current_mahal = self.compute_mahalanobis(sector_returns)

            # Compute historical threshold lazily on first call
            if self._mahal_threshold is None and len(sector_returns) >= _MIN_MAHAL_HISTORY:
                history = self.compute_mahalanobis_history(sector_returns)
                valid = history.dropna()
                if len(valid) >= 20:
                    self._mahal_threshold = float(
                        np.percentile(valid, self.turbulence_percentile)
                    )

            if (
                self._current_mahal is not None
                and self._mahal_threshold is not None
                and self._current_mahal > self._mahal_threshold
            ):
                self._is_turbulent = True
            else:
                self._is_turbulent = False
        else:
            self._is_turbulent = False

        log.debug(
            "%s: regime=%s, VIX=%.1f, turbulent=%s, Mahal=%.2f (threshold=%.2f)",
            self.name,
            self._current_regime,
            self._current_vix or 0.0,
            self._is_turbulent,
            self._current_mahal or 0.0,
            self._mahal_threshold or 0.0,
        )

    def _extract_vix_from_data(
        self, data: dict[str, pd.DataFrame]
    ) -> Optional[pd.Series]:
        """
        Attempt to extract VIX close series from data dict.
        Looks for key '^VIX' or 'VIX'.
        """
        for key in ("^VIX", "VIX"):
            df = data.get(key)
            if df is not None and not df.empty and "close" in df.columns:
                return _series_from_last_column(df["close"])
        return None

    def _extract_sector_returns(
        self, data: dict[str, pd.DataFrame]
    ) -> Optional[pd.DataFrame]:
        """
        Build a DataFrame of daily returns for all sector ETFs present in data.
        """
        series_dict: dict[str, pd.Series] = {}
        for etf in _SECTOR_ETFS:
            df = data.get(etf)
            if df is None or df.empty or "return_1d" not in df.columns:
                continue
            series_dict[etf] = df["return_1d"]

        if len(series_dict) < 2:
            return None

        sector_df = pd.DataFrame(series_dict).dropna(how="all")
        return sector_df

    def _compute_factor(self, regime: str, is_turbulent: bool) -> float:
        """
        Compute the combined signal scaling factor.

        Scale hierarchy:
          1. Regime-based base factor
          2. Turbulence reduction (multiplicative)
          3. Clamp to [0, 1.5]
        """
        if regime == "high":
            base = self.high_vol_scale
        elif regime == "low":
            base = self.low_vol_boost
        else:
            base = 1.0

        if is_turbulent:
            base *= self.turbulence_scale

        return float(np.clip(base, 0.0, 1.5))

    def _check_turbulence(
        self, sector_returns: Optional[pd.DataFrame]
    ) -> bool:
        """
        Check whether current sector returns indicate turbulent conditions.
        """
        if sector_returns is None:
            return self._is_turbulent  # use cached state

        if len(sector_returns) < _MIN_MAHAL_HISTORY:
            return False

        mahal = self.compute_mahalanobis(sector_returns)
        if mahal is None:
            return False

        self._current_mahal = mahal

        if self._mahal_threshold is None:
            history = self.compute_mahalanobis_history(sector_returns)
            valid = history.dropna()
            if len(valid) >= 20:
                self._mahal_threshold = float(
                    np.percentile(valid, self.turbulence_percentile)
                )
            else:
                return False

        return mahal > self._mahal_threshold

    def _resolve_vix(
        self, vix_data: Optional[pd.Series]
    ) -> Optional[float]:
        """
        Determine the current VIX level from provided data or cache.
        """
        if vix_data is not None and not vix_data.empty:
            val = _last_numeric_value(vix_data)
            return val if val is not None and not np.isnan(val) else None
        if self._current_vix is not None:
            return self._current_vix
        return self.get_current_vix()

    # ------------------------------------------------------------------
    # Status / diagnostics
    # ------------------------------------------------------------------

    @property
    def current_regime(self) -> str:
        """The most recently computed regime label."""
        return self._current_regime

    @property
    def current_vix(self) -> Optional[float]:
        """The most recently cached VIX level."""
        return self._current_vix

    @property
    def is_turbulent(self) -> bool:
        """True if the current Mahalanobis distance exceeds the threshold."""
        return self._is_turbulent

    def regime_summary(self) -> dict:
        """
        Return a dict summarising the current regime state.
        Useful for logging and monitoring dashboards.
        """
        return {
            "regime": self._current_regime,
            "vix": round(self._current_vix, 2) if self._current_vix is not None else None,
            "is_turbulent": self._is_turbulent,
            "mahalanobis_distance": (
                round(self._current_mahal, 4)
                if self._current_mahal is not None
                else None
            ),
            "mahalanobis_threshold": (
                round(self._mahal_threshold, 4)
                if self._mahal_threshold is not None
                else None
            ),
            "adjustment_factor": round(self.get_adjustment_factor(), 4),
        }


__all__ = ["VolatilityRegimeStrategy"]


def _series_from_last_column(value: pd.Series | pd.DataFrame) -> pd.Series:
    """Return a 1D series from a close column even if pandas produced a frame."""
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return pd.Series(dtype=float)
        value = value.iloc[:, -1]
    return pd.Series(value).dropna()


def _last_numeric_value(value: pd.Series | pd.DataFrame) -> Optional[float]:
    """Safely coerce the last numeric value from a Series or single-column frame."""
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return None
        value = value.iloc[:, -1]
    series = pd.Series(value).dropna()
    if series.empty:
        return None
    last = series.iloc[-1]
    if isinstance(last, pd.Series):
        last = last.iloc[-1]
    try:
        return float(last)
    except (TypeError, ValueError):
        return None
