"""
quantify.strategy.trend_following
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Time-Series Momentum (TSMOM) strategy.

Academic basis
--------------
Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). "Time series momentum."
Journal of Financial Economics, 104(2), 228–250.

The core insight is that each asset's own past 12-month return positively predicts
its next-month return (after skipping the most recent month to avoid microstructure
effects).  This "time-series" effect is distinct from cross-sectional momentum
(Jegadeesh & Titman) and has been documented across asset classes and geographies.

Implementation
--------------
Signal generation:
  1. Compute the trailing 12-month excess return (return_252d minus 1-month return,
     i.e. 11-1 skipping construction; approximated here as return_252d minus
     return_21d to exclude the most recent month).
  2. Check the 50/200-day SMA crossover as a trend-confirmation filter.
  3. Both signals must agree for an entry:
     - Long  : 12-month momentum positive  AND  SMA-50 > SMA-200
     - Short : 12-month momentum negative  AND  SMA-50 < SMA-200
  4. Signal strength is scaled by short-term (21-day) and medium-term (63-day)
     momentum alignment — conviction rises when multiple horizons agree.

Volatility targeting
--------------------
A target of 10% annualised volatility per position is suggested via the
``vol_target`` metadata key.  Upstream position sizers can use this hint to
compute notional size as ``(vol_target / realized_vol) * capital_per_slot``.

Position sizing hint:
    weight = vol_target / (realized_vol * sqrt(252)) if realized_vol > 0 else 0
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
import pandas as pd

from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default liquid large-cap universe
# ---------------------------------------------------------------------------
_DEFAULT_UNIVERSE: list[str] = [
    # US mega-caps across sectors — high liquidity, robust momentum signals
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B",
    "JPM", "V", "UNH", "XOM", "JNJ", "PG", "MA", "HD", "CVX", "ABBV",
    "MRK", "AVGO", "COST", "LLY", "PEP", "KO", "BAC", "TMO", "ORCL",
    "CRM", "ACN", "MCD", "NFLX", "AMD", "QCOM", "HON", "TXN", "GE",
    "NOW", "INTC", "IBM",
]

# Target annualised volatility per position (10%)
_VOL_TARGET: float = 0.10

# Minimum bars required before emitting signals
_MIN_BARS: int = 252  # ~1 trading year


class TrendFollowingStrategy(Strategy):
    """
    Time-Series Momentum (TSMOM) strategy.

    Long assets whose own trailing 12-month return is positive and whose
    50-day SMA has crossed above the 200-day SMA; short the reverse.
    Signal strength is boosted when short- and medium-term momentum horizons
    agree with the 12-month signal.

    Parameters
    ----------
    universe:
        List of tickers to trade.  Defaults to a curated list of 40 liquid
        large-caps drawn from major GICS sectors.
    vol_target:
        Annualised volatility target per position (default 0.10 = 10 %).
        Embedded in each signal's ``metadata["vol_target"]`` field for use
        by the position sizer.
    min_bars:
        Minimum number of daily bars required before a signal is emitted
        for a given symbol.  Defaults to 252.
    """

    name: str = "trend_following"
    rebalance_frequency: str = "daily"
    lookback_days: int = 280  # 252 trading days + buffer for weekends/holidays

    def __init__(
        self,
        universe: Optional[List[str]] = None,
        vol_target: float = _VOL_TARGET,
        min_bars: int = _MIN_BARS,
    ) -> None:
        self.universe: list[str] = universe if universe is not None else list(_DEFAULT_UNIVERSE)
        self.vol_target = vol_target
        self.min_bars = min_bars
        log.info(
            "TrendFollowingStrategy initialised: %d symbols, vol_target=%.1f%%",
            len(self.universe),
            vol_target * 100,
        )

    def get_required_features(self) -> list[str]:
        """
        Features consumed by this strategy:

        - ``return_252d``   : trailing 12-month (252-day) return
        - ``return_63d``    : trailing 3-month return (medium-term momentum)
        - ``return_21d``    : trailing 1-month return (short-term momentum)
        - ``sma_crossover`` : 1.0 when SMA-50 > SMA-200, else 0.0
        - ``volatility_20d``: 20-day realised volatility for position sizing
        """
        return [
            "return_252d",
            "return_63d",
            "return_21d",
            "sma_crossover",
            "volatility_20d",
        ]

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        Generate time-series momentum signals for the current bar.

        For each symbol with sufficient history:

        1. Compute the 12-1 momentum proxy: r_252d - r_21d (skips recent month).
        2. Check SMA crossover (50-day vs 200-day).
        3. Both must agree for entry; else emit ``"close"`` to exit.
        4. Compute strength from short/medium/long momentum alignment.
        5. Embed vol-targeting hint in metadata.

        Parameters
        ----------
        data:
            Mapping of ``{symbol: DataFrame}`` with OHLCV + feature columns.

        Returns
        -------
        list[Signal]
        """
        if not data:
            log.warning("%s: received empty data dict", self.name)
            return []

        signals: list[Signal] = []
        timestamp = self._latest_timestamp(data)

        for symbol, df in data.items():
            try:
                sig = self._process_symbol(symbol, df, timestamp)
            except Exception as exc:
                log.exception("%s: error processing %s: %s", self.name, symbol, exc)
                continue

            if sig is not None:
                signals.append(sig)

        log.debug(
            "%s: generated %d signals at %s",
            self.name,
            len(signals),
            timestamp.isoformat(timespec="seconds"),
        )
        return signals

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _process_symbol(
        self,
        symbol: str,
        df: pd.DataFrame,
        timestamp: datetime,
    ) -> Optional[Signal]:
        """
        Produce a signal (or None) for a single symbol.
        """
        if df.empty or len(df) < self.min_bars:
            log.debug(
                "%s: skipping %s — only %d bars (need %d)",
                self.name,
                symbol,
                len(df),
                self.min_bars,
            )
            return None

        # ---- Extract feature values from the most recent row ----
        row = df.iloc[-1]

        r252 = _safe_float(row, "return_252d")
        r63 = _safe_float(row, "return_63d")
        r21 = _safe_float(row, "return_21d")
        crossover = _safe_float(row, "sma_crossover")
        vol_20d = _safe_float(row, "volatility_20d")

        # Require all key features to be valid
        if any(v is None for v in [r252, r21, crossover]):
            log.debug("%s: %s has NaN features, skipping", self.name, symbol)
            return None

        # ---- 12-1 momentum: 12-month return minus 1-month return ----
        mom_12_1 = r252 - r21  # type: ignore[operator]

        # ---- SMA crossover check ----
        sma_bullish: bool = crossover == 1.0
        sma_bearish: bool = crossover == 0.0

        # ---- Signal direction decision ----
        mom_positive = mom_12_1 > 0
        mom_negative = mom_12_1 < 0

        if mom_positive and sma_bullish:
            direction = "long"
        elif mom_negative and sma_bearish:
            direction = "short"
        else:
            # Signals disagree — close or stay flat
            direction = "close"

        # ---- Compute conviction / strength ----
        strength = self._compute_strength(direction, mom_12_1, r63, r21)

        # ---- Vol-targeting position sizing hint ----
        vol_hint = self._vol_sizing_hint(vol_20d)

        metadata = {
            "mom_12_1": round(mom_12_1, 6),
            "return_252d": round(r252, 6),  # type: ignore[arg-type]
            "return_63d": round(r63, 6) if r63 is not None else None,
            "return_21d": round(r21, 6),    # type: ignore[arg-type]
            "sma_crossover": crossover,
            "vol_20d": round(vol_20d, 6) if vol_20d is not None else None,
            "vol_target": self.vol_target,
            "suggested_weight": vol_hint,
        }

        return Signal(
            strategy_name=self.name,
            symbol=symbol,
            direction=direction,  # type: ignore[arg-type]
            strength=strength,
            timestamp=timestamp,
            metadata=metadata,
        )

    def _compute_strength(
        self,
        direction: str,
        mom_12_1: float,
        r63: Optional[float],
        r21: Optional[float],
    ) -> float:
        """
        Compute signal strength in [-1, 1].

        Conviction is scaled by how many horizons agree:
        - Start with the sign of the 12-1 momentum, capped at ±1.
        - Boost by 20% if 3-month momentum agrees.
        - Boost by 10% if 1-month momentum agrees.
        - Scale by the absolute magnitude of the 12-1 return (capped at 50%).

        For ``"close"`` signals, return 0.
        """
        if direction == "close":
            return 0.0

        # Normalise the raw momentum signal — cap at 50% absolute return
        raw_strength = min(abs(mom_12_1) / 0.50, 1.0)

        # Alignment bonus: short-term + medium-term horizons
        sign = 1.0 if direction == "long" else -1.0
        alignment_bonus = 0.0
        if r63 is not None and np.sign(r63) == np.sign(sign):
            alignment_bonus += 0.20
        if r21 is not None and np.sign(r21) == np.sign(sign):
            alignment_bonus += 0.10

        conviction = raw_strength * (1.0 + alignment_bonus)
        strength = sign * min(conviction, 1.0)
        return float(np.clip(strength, -1.0, 1.0))

    def _vol_sizing_hint(self, vol_20d: Optional[float]) -> Optional[float]:
        """
        Return a suggested portfolio weight based on volatility targeting.

        weight = vol_target / realised_vol

        This is a *hint* — the actual sizing is determined by the position
        sizer module, but including it in metadata enables simple strategies
        to use it directly.
        """
        if vol_20d is None or vol_20d <= 0:
            return None
        weight = self.vol_target / vol_20d
        # Cap at 2x to avoid extreme leverage
        return float(min(weight, 2.0))

    @staticmethod
    def _latest_timestamp(data: dict[str, pd.DataFrame]) -> datetime:
        """Return the latest bar timestamp across all DataFrames."""
        latest = datetime.min.replace(tzinfo=timezone.utc)
        for df in data.values():
            if df.empty:
                continue
            ts = df.index[-1]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts > latest:
                latest = ts
        if latest == datetime.min.replace(tzinfo=timezone.utc):
            return datetime.now(timezone.utc)
        return latest


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _safe_float(row: pd.Series, col: str) -> Optional[float]:
    """Return float value for *col* from *row*, or None if missing/NaN."""
    val = row.get(col)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


__all__ = ["TrendFollowingStrategy"]
