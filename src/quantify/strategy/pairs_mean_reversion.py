"""
quantify.strategy.pairs_mean_reversion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Statistical Arbitrage via Pairs Trading (Gatev-Goetzmann-Rouwenhorst).

Academic basis
--------------
Gatev, E., Goetzmann, W. N., & Rouwenhorst, K. G. (2006). "Pairs trading:
Performance of a relative-value arbitrage rule." Review of Financial Studies,
19(3), 797–827.

The strategy identifies pairs of stocks whose prices are cointegrated — i.e.,
they share a long-run equilibrium relationship despite short-term divergence.
When the spread between a pair deviates beyond a threshold, a mean-reversion
trade is entered, betting the spread will converge back.

Engle, R. F., & Granger, C. W. J. (1987). "Co-integration and error correction:
Representation, estimation, and testing." Econometrica, 55(2), 251–276.

Implementation details
----------------------
Formation (offline / on_start)
  - Candidate pairs drawn from sector-matched stocks (reduces factor risk)
  - Cointegration tested with Engle-Granger (``statsmodels.tsa.stattools.coint``)
  - Only pairs with p-value < 0.05 are retained
  - Hedge ratio estimated via OLS regression: log(P_B) ~ beta * log(P_A) + alpha
  - Spread: log(P_A) − beta * log(P_B)

Signal generation (daily)
  - Spread z-score: (spread − mu) / sigma, where mu/sigma estimated in-sample
  - Entry long spread  : z-score < −2.0  (A cheap relative to B)
  - Entry short spread : z-score > +2.0  (A expensive relative to B)
  - Exit              : |z-score| < 0.5
  - Stop loss          : |z-score| > 4.0  (relationship may have broken down)
  - Maximum 5 active pairs (capacity constraint)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ENTRY_ZSCORE: float = 2.0
_EXIT_ZSCORE: float = 0.5
_STOP_ZSCORE: float = 4.0
_MAX_ACTIVE_PAIRS: int = 5
_MIN_BARS_FORMATION: int = 252
_COINT_PVALUE_THRESHOLD: float = 0.05

# Default candidate pairs — sector-matched to reduce common factor exposure
# Pairs are (stock_A, stock_B); same GICS sub-industry where possible
_DEFAULT_CANDIDATES: list[tuple[str, str]] = [
    # Mega-cap tech
    ("MSFT", "AAPL"),
    ("GOOGL", "META"),
    ("NVDA", "AMD"),
    ("ORCL", "CRM"),
    ("INTC", "QCOM"),
    # Financials
    ("JPM", "BAC"),
    ("V", "MA"),
    ("GS", "MS"),
    ("SPGI", "MCO"),
    ("PGR", "CB"),
    # Consumer Discretionary
    ("HD", "LOW"),
    ("MCD", "SBUX"),
    ("MAR", "HLT"),
    ("UBER", "LYFT"),
    # Health Care
    ("JNJ", "ABT"),
    ("MRK", "ABBV"),
    ("TMO", "DHR"),
    ("AMGN", "GILD"),
    # Industrials
    ("CAT", "DE"),
    ("UPS", "FDX"),
    # Energy
    ("XOM", "CVX"),
    ("MPC", "VLO"),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PairState:
    """Runtime state for a single cointegrated pair."""

    symbol_a: str
    symbol_b: str
    hedge_ratio: float        # beta in log(P_A) = beta * log(P_B) + alpha
    spread_mean: float        # in-sample mean of log spread
    spread_std: float         # in-sample std of log spread
    is_active: bool = False   # currently in a trade
    position: str = "none"    # "long_spread" | "short_spread" | "none"
    entry_zscore: float = 0.0
    coint_pvalue: float = 1.0

    @property
    def pair_key(self) -> str:
        return f"{self.symbol_a}_{self.symbol_b}"


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


class PairsMeanReversionStrategy(Strategy):
    """
    Statistical arbitrage via cointegration-based pairs trading.

    Identifies sector-matched cointegrated pairs during formation, then trades
    spread mean-reversion daily.  Up to five pairs may be active at once.

    Parameters
    ----------
    candidate_pairs:
        List of ``(symbol_a, symbol_b)`` tuples to test for cointegration.
        Defaults to ~22 sector-matched large-cap pairs.
    max_active_pairs:
        Maximum number of pairs to hold concurrently (default 5).
    entry_zscore:
        Spread z-score at which to enter a trade (default 2.0).
    exit_zscore:
        Spread z-score at which to exit a trade (default 0.5).
    stop_zscore:
        Spread z-score at which to stop-out (default 4.0).
    coint_pvalue:
        Maximum Engle-Granger p-value to accept a pair (default 0.05).
    """

    name: str = "pairs_mean_reversion"
    rebalance_frequency: str = "daily"
    lookback_days: int = 310

    def __init__(
        self,
        candidate_pairs: Optional[list[tuple[str, str]]] = None,
        max_active_pairs: int = _MAX_ACTIVE_PAIRS,
        entry_zscore: float = _ENTRY_ZSCORE,
        exit_zscore: float = _EXIT_ZSCORE,
        stop_zscore: float = _STOP_ZSCORE,
        coint_pvalue: float = _COINT_PVALUE_THRESHOLD,
    ) -> None:
        self._candidate_pairs = candidate_pairs or list(_DEFAULT_CANDIDATES)
        self.max_active_pairs = max_active_pairs
        self.entry_zscore = entry_zscore
        self.exit_zscore = exit_zscore
        self.stop_zscore = stop_zscore
        self.coint_pvalue_threshold = coint_pvalue

        # Derive universe from all unique tickers in candidate pairs
        seen: set[str] = set()
        ordered: list[str] = []
        for a, b in self._candidate_pairs:
            for sym in (a, b):
                if sym not in seen:
                    seen.add(sym)
                    ordered.append(sym)
        self.universe: list[str] = ordered

        # Strategy state
        self._pair_states: dict[str, PairState] = {}  # key = "A_B"
        self._formation_complete: bool = False
        self._last_formation_date: Optional[date] = None
        self._rerun_formation_interval: str = "monthly"  # "weekly", "monthly", or "never"

        log.info(
            "PairsMeanReversionStrategy initialised: %d candidate pairs, "
            "%d unique symbols",
            len(self._candidate_pairs),
            len(self.universe),
        )

    def get_required_features(self) -> list[str]:
        """
        No derived features needed — this strategy works directly with close
        prices to compute log spread z-scores.
        """
        return []

    def on_start(self) -> None:
        """Reset formation state at the start of each session."""
        self._pair_states = {}
        self._formation_complete = False
        self._last_formation_date = None
        log.info("%s: formation state reset on start", self.name)

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        Generate pairs trading signals.

        First call performs the formation step (cointegration tests).
        Subsequent calls compute z-scores and emit entry / exit signals.

        Parameters
        ----------
        data:
            ``{symbol: DataFrame}`` with at minimum a ``close`` column.

        Returns
        -------
        list[Signal]
        """
        if not data:
            log.warning("%s: empty data dict", self.name)
            return []

        timestamp = self._latest_timestamp(data)

        # ---- Formation: find cointegrated pairs (run once, then re-run periodically) ----
        should_rerun_formation = False
        if not self._formation_complete:
            should_rerun_formation = True
        elif self._last_formation_date is not None:
            # Check if we should re-run formation based on the interval
            current_date = timestamp.date()
            if self._rerun_formation_interval == "weekly":
                should_rerun_formation = (
                    current_date.isocalendar()[1] != self._last_formation_date.isocalendar()[1]
                )
            elif self._rerun_formation_interval == "monthly":
                should_rerun_formation = (
                    current_date.month != self._last_formation_date.month
                    or current_date.year != self._last_formation_date.year
                )
            # else "never" or unknown interval: don't re-run
        
        if should_rerun_formation:
            self._run_formation(data)
            self._last_formation_date = timestamp.date()

        if not self._pair_states:
            log.warning("%s: no cointegrated pairs found after formation", self.name)
            return []

        signals: list[Signal] = []
        active_count = sum(1 for ps in self._pair_states.values() if ps.is_active)

        for pair_key, ps in self._pair_states.items():
            try:
                pair_signals = self._process_pair(ps, data, timestamp, active_count)
                signals.extend(pair_signals)
                # Update active count after each pair decision
                active_count = sum(
                    1 for p in self._pair_states.values() if p.is_active
                )
            except Exception as exc:
                log.exception(
                    "%s: error processing pair %s: %s", self.name, pair_key, exc
                )

        log.debug(
            "%s: %d signals at %s (active pairs: %d/%d)",
            self.name,
            len(signals),
            timestamp.date(),
            sum(1 for ps in self._pair_states.values() if ps.is_active),
            self.max_active_pairs,
        )
        return signals

    def on_fill(self, fill) -> None:
        """Update pair state when a fill is received."""
        log.debug(
            "%s: fill — %s %s × %.4f @ %.4f",
            self.name,
            fill.side.value,
            fill.symbol,
            fill.quantity,
            fill.price,
        )

    # ------------------------------------------------------------------
    # Formation
    # ------------------------------------------------------------------

    def _run_formation(self, data: dict[str, pd.DataFrame]) -> None:
        """
        Test each candidate pair for cointegration.

        Pairs with Engle-Granger p-value < threshold are kept.  For each
        retained pair we estimate the hedge ratio and spread statistics using
        the full history available in ``data``.
        """
        try:
            from statsmodels.tsa.stattools import coint
        except ImportError:
            log.error(
                "%s: statsmodels is not installed.  "
                "Install with: pip install statsmodels",
                self.name,
            )
            self._formation_complete = True
            return

        log.info("%s: starting formation — testing %d candidate pairs",
                 self.name, len(self._candidate_pairs))

        accepted: list[PairState] = []

        for sym_a, sym_b in self._candidate_pairs:
            df_a = data.get(sym_a)
            df_b = data.get(sym_b)

            if df_a is None or df_b is None:
                log.debug("%s: pair (%s,%s) skipped — data missing",
                          self.name, sym_a, sym_b)
                continue

            # Align on common dates
            common_idx = df_a.index.intersection(df_b.index)
            if len(common_idx) < _MIN_BARS_FORMATION:
                log.debug(
                    "%s: pair (%s,%s) has only %d common bars (need %d)",
                    self.name, sym_a, sym_b, len(common_idx), _MIN_BARS_FORMATION,
                )
                continue

            log_a = np.log(df_a.loc[common_idx, "close"].values)
            log_b = np.log(df_b.loc[common_idx, "close"].values)

            # Guard against invalid prices
            if np.any(np.isnan(log_a)) or np.any(np.isnan(log_b)):
                continue

            try:
                score, pvalue, _ = coint(log_a, log_b)
            except Exception as exc:
                log.debug("%s: coint test failed for (%s,%s): %s",
                          self.name, sym_a, sym_b, exc)
                continue

            if pvalue > self.coint_pvalue_threshold:
                log.debug(
                    "%s: pair (%s,%s) rejected, p=%.4f",
                    self.name, sym_a, sym_b, pvalue,
                )
                continue

            # ---- OLS hedge ratio ----
            # log(P_A) = beta * log(P_B) + alpha + epsilon
            beta, alpha = np.polyfit(log_b, log_a, 1)

            # ---- Spread statistics ----
            spread = log_a - beta * log_b
            spread_mean = float(spread.mean())
            spread_std = float(spread.std(ddof=1))

            if spread_std < 1e-8:
                log.debug("%s: pair (%s,%s) has near-zero spread std, skipping",
                          self.name, sym_a, sym_b)
                continue

            ps = PairState(
                symbol_a=sym_a,
                symbol_b=sym_b,
                hedge_ratio=float(beta),
                spread_mean=spread_mean,
                spread_std=spread_std,
                coint_pvalue=float(pvalue),
            )
            accepted.append(ps)
            log.info(
                "%s: accepted pair (%s,%s) p=%.4f, beta=%.4f",
                self.name, sym_a, sym_b, pvalue, beta,
            )

        # Sort by cointegration strength (lowest p-value first)
        accepted.sort(key=lambda ps: ps.coint_pvalue)
        self._pair_states = {ps.pair_key: ps for ps in accepted}

        log.info(
            "%s: formation complete — %d cointegrated pairs accepted",
            self.name, len(self._pair_states),
        )
        self._formation_complete = True

    # ------------------------------------------------------------------
    # Signal generation per pair
    # ------------------------------------------------------------------

    def _process_pair(
        self,
        ps: PairState,
        data: dict[str, pd.DataFrame],
        timestamp: datetime,
        active_count: int,
    ) -> list[Signal]:
        """
        Compute the current spread z-score and decide on entry/exit/stop.

        Returns a list of 0, 1, or 2 signals (one per leg of the pair).
        """
        df_a = data.get(ps.symbol_a)
        df_b = data.get(ps.symbol_b)

        if df_a is None or df_a.empty or df_b is None or df_b.empty:
            return []

        price_a = df_a["close"].iloc[-1]
        price_b = df_b["close"].iloc[-1]

        if pd.isna(price_a) or pd.isna(price_b) or price_a <= 0 or price_b <= 0:
            return []

        log_a = np.log(price_a)
        log_b = np.log(price_b)
        spread = log_a - ps.hedge_ratio * log_b
        zscore = (spread - ps.spread_mean) / ps.spread_std

        signals: list[Signal] = []

        # ---- Stop-loss: spread has diverged too far ----
        if ps.is_active and abs(zscore) >= self.stop_zscore:
            log.warning(
                "%s: stop-loss for pair (%s,%s), z=%.2f",
                self.name, ps.symbol_a, ps.symbol_b, zscore,
            )
            signals.extend(self._exit_signals(ps, timestamp, zscore, reason="stop"))
            ps.is_active = False
            ps.position = "none"
            return signals

        # ---- Exit: spread has reverted ----
        if ps.is_active and abs(zscore) < self.exit_zscore:
            log.info(
                "%s: exiting pair (%s,%s), z=%.2f (reverted)",
                self.name, ps.symbol_a, ps.symbol_b, zscore,
            )
            signals.extend(self._exit_signals(ps, timestamp, zscore, reason="revert"))
            ps.is_active = False
            ps.position = "none"
            return signals

        # ---- Entry: spread has diverged ----
        if not ps.is_active:
            if active_count >= self.max_active_pairs:
                log.debug(
                    "%s: capacity reached (%d/%d), skipping (%s,%s)",
                    self.name, active_count, self.max_active_pairs,
                    ps.symbol_a, ps.symbol_b,
                )
                return []

            if zscore > self.entry_zscore:
                # A is too expensive relative to B — short the spread
                # short A (overvalued), long B (undervalued)
                position = "short_spread"
                entry_signals = self._entry_signals(
                    ps, timestamp, zscore, position
                )
                if entry_signals:
                    signals.extend(entry_signals)
                    ps.is_active = True
                    ps.position = position
                    ps.entry_zscore = zscore

            elif zscore < -self.entry_zscore:
                # A is too cheap relative to B — long the spread
                # long A (undervalued), short B (overvalued)
                position = "long_spread"
                entry_signals = self._entry_signals(
                    ps, timestamp, zscore, position
                )
                if entry_signals:
                    signals.extend(entry_signals)
                    ps.is_active = True
                    ps.position = position
                    ps.entry_zscore = zscore

        return signals

    def _entry_signals(
        self,
        ps: PairState,
        timestamp: datetime,
        zscore: float,
        position: str,
    ) -> list[Signal]:
        """Generate entry signals for a new spread trade."""
        # Strength: z-score distance from entry threshold, normalised to [0, 1]
        excess = abs(zscore) - self.entry_zscore
        max_excess = self.stop_zscore - self.entry_zscore
        strength = float(np.clip(excess / max_excess, 0.0, 1.0))

        meta = {
            "zscore": round(zscore, 4),
            "position": position,
            "hedge_ratio": round(ps.hedge_ratio, 6),
            "spread_mean": round(ps.spread_mean, 6),
            "spread_std": round(ps.spread_std, 6),
            "coint_pvalue": round(ps.coint_pvalue, 6),
            "pair": ps.pair_key,
            "action": "entry",
        }

        if position == "long_spread":
            # Long A (undervalued), short B (overvalued)
            return [
                Signal(
                    strategy_name=self.name,
                    symbol=ps.symbol_a,
                    direction="long",
                    strength=strength,
                    timestamp=timestamp,
                    metadata=dict(meta, leg="long_A"),
                ),
                Signal(
                    strategy_name=self.name,
                    symbol=ps.symbol_b,
                    direction="short",
                    strength=-strength,
                    timestamp=timestamp,
                    metadata=dict(meta, leg="short_B"),
                ),
            ]
        else:
            # Short A (overvalued), long B (undervalued)
            return [
                Signal(
                    strategy_name=self.name,
                    symbol=ps.symbol_a,
                    direction="short",
                    strength=-strength,
                    timestamp=timestamp,
                    metadata=dict(meta, leg="short_A"),
                ),
                Signal(
                    strategy_name=self.name,
                    symbol=ps.symbol_b,
                    direction="long",
                    strength=strength,
                    timestamp=timestamp,
                    metadata=dict(meta, leg="long_B"),
                ),
            ]

    def _exit_signals(
        self,
        ps: PairState,
        timestamp: datetime,
        zscore: float,
        reason: str,
    ) -> list[Signal]:
        """Generate exit (close) signals for both legs of a spread trade."""
        meta = {
            "zscore": round(zscore, 4),
            "position": ps.position,
            "pair": ps.pair_key,
            "action": f"exit_{reason}",
        }
        return [
            Signal(
                strategy_name=self.name,
                symbol=ps.symbol_a,
                direction="close",
                strength=0.0,
                timestamp=timestamp,
                metadata=dict(meta, leg="close_A"),
            ),
            Signal(
                strategy_name=self.name,
                symbol=ps.symbol_b,
                direction="close",
                strength=0.0,
                timestamp=timestamp,
                metadata=dict(meta, leg="close_B"),
            ),
        ]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

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

    def get_pair_states(self) -> dict[str, PairState]:
        """Return a copy of the current pair state dictionary (for inspection)."""
        return dict(self._pair_states)


__all__ = ["PairsMeanReversionStrategy", "PairState"]
