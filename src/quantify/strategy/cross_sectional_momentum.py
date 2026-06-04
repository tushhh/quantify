"""
quantify.strategy.cross_sectional_momentum
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Cross-Sectional Momentum strategy (Jegadeesh-Titman).

Academic basis
--------------
Jegadeesh, N., & Titman, S. (1993). "Returns to buying winners and selling
losers: Implications for stock market efficiency." Journal of Finance, 48(1),
65–91.

The strategy ranks stocks by their past return over an intermediate horizon
(12 months minus the most recent month, the "12-1" or "11-month skipping"
return) and buys the top decile while shorting the bottom decile.  The skip-
month avoids short-term reversal contamination documented by Jegadeesh (1990).

Momentum Crash Protection
--------------------------
Daniel & Moskowitz (2016) show that momentum strategies crash badly when the
market recovers sharply from a bear market.  If the benchmark (SPY) 12-month
return is negative, we reduce all signal strengths by 50% to lower gross
exposure during elevated crash risk.

Implementation details
----------------------
- Ranking period : 12 months (252 trading days) minus 1 month (21 days)
- Formation       : return_252d − return_21d  (12-1 momentum)
- Long decile     : top 10% by 12-1 return
- Short decile    : bottom 10% by 12-1 return
- Strength        : linearly normalised rank score in [−1, 1]
- Rebalance       : monthly (≥ 21 trading days since last rebalance)
- Crash filter    : if SPY 12m return < 0, scale all strengths by 0.50
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from quantify.data.universe import get_sp500
from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# Minimum bars before we can compute 12-1 momentum
_MIN_BARS: int = 273  # 252 + 21 trading days

# SPY ticker used for crash-filter check
_BENCHMARK: str = "SPY"

# Decile cut-offs
_LONG_DECILE_THRESHOLD: float = 0.90   # top 10%
_SHORT_DECILE_THRESHOLD: float = 0.10  # bottom 10%

# Crash filter scale factor
_CRASH_SCALE: float = 0.50


class CrossSectionalMomentumStrategy(Strategy):
    """
    Cross-Sectional Momentum (Jegadeesh-Titman 1993).

    Ranks every symbol in the S&P 500 universe by its 12-1 month return
    and generates long / short signals for the top / bottom decile.

    Parameters
    ----------
    universe:
        List of tickers.  Defaults to the top-100 S&P 500 list from
        :func:`~quantify.data.universe.get_sp500`.
    long_threshold:
        Percentile cut-off for the long decile (default 0.90 → top 10%).
    short_threshold:
        Percentile cut-off for the short decile (default 0.10 → bottom 10%).
    crash_filter:
        Whether to apply the momentum crash filter (default True).
    rebalance_days:
        Minimum calendar trading days between rebalances (default 21).
    """

    name: str = "cross_sectional_momentum"
    rebalance_frequency: str = "monthly"
    lookback_days: int = 310  # 252 + 21 + calendar buffer

    def __init__(
        self,
        universe: Optional[list[str]] = None,
        long_threshold: float = _LONG_DECILE_THRESHOLD,
        short_threshold: float = _SHORT_DECILE_THRESHOLD,
        crash_filter: bool = True,
        rebalance_days: int = 21,
    ) -> None:
        sp500 = get_sp500()
        # Prepend SPY so the engine fetches its data for the crash filter
        tickers_with_spy = [_BENCHMARK] + [t for t in (universe or sp500) if t != _BENCHMARK]
        self.universe: list[str] = tickers_with_spy

        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.crash_filter = crash_filter
        self.rebalance_days = rebalance_days

        # State
        self._last_rebalance_date: Optional[datetime] = None
        self._signal_cache: list[Signal] = []

        log.info(
            "CrossSectionalMomentumStrategy initialised: %d symbols "
            "(incl. SPY benchmark), long_pct=%.0f%%, short_pct=%.0f%%",
            len(self.universe),
            long_threshold * 100,
            (1 - short_threshold) * 100,
        )

    def get_required_features(self) -> list[str]:
        """
        Features used:

        - ``return_252d`` : 12-month trailing return (for 12-1 numerator and
          SPY crash filter)
        - ``return_21d``  : 1-month trailing return (skip-month denominator)
        """
        return ["return_252d", "return_21d"]

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        Cross-sectionally rank all symbols and emit long/short signals for
        extreme deciles.

        Rebalance only occurs when at least ``rebalance_days`` trading days
        have elapsed since the last rebalance.  Between rebalances the cached
        signal list is returned.

        Parameters
        ----------
        data:
            Mapping of ``{symbol: DataFrame}`` with OHLCV + feature columns.

        Returns
        -------
        list[Signal]
        """
        if not data:
            log.warning("%s: empty data dict", self.name)
            return []

        timestamp = self._latest_timestamp(data)

        # ---- Rebalance frequency gate ----
        if not self._should_rebalance(timestamp):
            log.debug(
                "%s: skipping rebalance at %s (next in ≥%d days)",
                self.name,
                timestamp.date(),
                self.rebalance_days,
            )
            return list(self._signal_cache)

        log.info("%s: rebalancing at %s", self.name, timestamp.date())

        # ---- Compute 12-1 momentum for each symbol ----
        scores: dict[str, float] = {}

        for symbol, df in data.items():
            if symbol == _BENCHMARK:
                continue
            if df.empty or len(df) < _MIN_BARS:
                log.debug(
                    "%s: insufficient history for %s (%d bars)",
                    self.name, symbol, len(df),
                )
                continue

            row = df.iloc[-1]
            r252 = _safe_float(row, "return_252d")
            r21 = _safe_float(row, "return_21d")

            if r252 is None or r21 is None:
                log.debug("%s: %s has NaN momentum features", self.name, symbol)
                continue

            mom_12_1 = r252 - r21
            scores[symbol] = mom_12_1

        if len(scores) < 10:
            log.warning(
                "%s: only %d symbols with valid momentum scores — "
                "need ≥10 for meaningful decile construction",
                self.name, len(scores),
            )
            return []

        # ---- Crash filter: check SPY 12-month return ----
        crash_scale = self._compute_crash_scale(data)
        if crash_scale < 1.0:
            log.info(
                "%s: crash filter active (SPY 12m return negative) — "
                "signal strengths scaled by %.0f%%",
                self.name, crash_scale * 100,
            )

        # ---- Rank and select decile portfolios ----
        score_series = pd.Series(scores)
        percentile_ranks = score_series.rank(pct=True)

        signals: list[Signal] = []

        for symbol, pct_rank in percentile_ranks.items():
            raw_score = score_series[symbol]

            if pct_rank >= self.long_threshold:
                direction = "long"
                # Normalise: top decile gets strength [0, +1]
                strength_raw = (pct_rank - self.long_threshold) / (1.0 - self.long_threshold)
                strength = float(np.clip(strength_raw * crash_scale, 0.0, 1.0))

            elif pct_rank <= self.short_threshold:
                direction = "short"
                # Normalise: bottom decile gets strength [-1, 0]
                strength_raw = (self.short_threshold - pct_rank) / self.short_threshold
                strength = float(np.clip(-strength_raw * crash_scale, -1.0, 0.0))

            else:
                # Middle stocks — close / exit
                direction = "close"
                strength = 0.0

            signals.append(
                Signal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction=direction,  # type: ignore[arg-type]
                    strength=strength,
                    timestamp=timestamp,
                    metadata={
                        "mom_12_1": round(raw_score, 6),
                        "percentile_rank": round(pct_rank, 4),
                        "crash_scale": crash_scale,
                        "n_stocks_ranked": len(scores),
                    },
                )
            )

        # Cache for intra-rebalance calls
        self._signal_cache = signals
        self._last_rebalance_date = timestamp
        log.info(
            "%s: generated %d signals (%d long, %d short, %d close)",
            self.name,
            len(signals),
            sum(1 for s in signals if s.direction == "long"),
            sum(1 for s in signals if s.direction == "short"),
            sum(1 for s in signals if s.direction == "close"),
        )
        return signals

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _should_rebalance(self, timestamp: datetime) -> bool:
        """Return True if enough time has passed since the last rebalance."""
        if self._last_rebalance_date is None:
            return True
        delta = timestamp - self._last_rebalance_date
        return delta.days >= self.rebalance_days

    def _compute_crash_scale(self, data: dict[str, pd.DataFrame]) -> float:
        """
        Return crash filter multiplier (1.0 normal, 0.50 if SPY 12m < 0).
        """
        if not self.crash_filter:
            return 1.0

        spy_df = data.get(_BENCHMARK)
        if spy_df is None or spy_df.empty or len(spy_df) < _MIN_BARS:
            return 1.0

        row = spy_df.iloc[-1]
        spy_252 = _safe_float(row, "return_252d")
        if spy_252 is None:
            return 1.0

        return _CRASH_SCALE if spy_252 < 0 else 1.0

    @staticmethod
    def _latest_timestamp(data: dict[str, pd.DataFrame]) -> datetime:
        """Return the most recent bar timestamp across all DataFrames."""
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


__all__ = ["CrossSectionalMomentumStrategy"]
