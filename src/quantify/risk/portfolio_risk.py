"""
quantify.risk.portfolio_risk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Portfolio-level risk monitoring and circuit-breaker logic.

The :class:`PortfolioRiskManager` runs a suite of risk checks against the
current portfolio state and returns structured :class:`RiskCheck` results.
It also exposes :meth:`~PortfolioRiskManager.apply_risk_adjustments` which
filters or reduces a list of :class:`~quantify.strategy.signal.Signal` objects
to ensure the resulting portfolio would remain within all configured limits.

Risk checks
-----------
* ``check_drawdown``         — portfolio drawdown vs. high-water mark
* ``check_sector_exposure``  — any single GICS sector exceeding the cap
* ``check_correlation``      — highly correlated position pairs (> threshold)
* ``check_gross_leverage``   — sum(|position weights|) vs. max leverage
* ``check_daily_loss``       — intraday P&L vs. daily loss limit
* ``check_all``              — convenience: run every check in one call

Usage
-----
    from quantify.risk.portfolio_risk import PortfolioRiskManager

    mgr = PortfolioRiskManager()
    checks = mgr.check_all(portfolio, sector_map=sector_map, returns_data=returns)
    safe_signals = mgr.apply_risk_adjustments(signals, portfolio, sector_map=sector_map)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RiskCheck dataclass
# ---------------------------------------------------------------------------


@dataclass
class RiskCheck:
    """
    Result of a single risk check.

    Attributes
    ----------
    passed:
        ``True`` if the portfolio satisfies this constraint.
    check_name:
        Machine-readable identifier (e.g. ``"drawdown"``, ``"sector_exposure"``).
    message:
        Human-readable description of the finding.
    severity:
        ``"warning"`` — limit approached but not breached.
        ``"critical"`` — limit breached; trading should be halted or reduced.
    metadata:
        Optional extra context (e.g. the offending symbols or current values).
    """

    passed: bool
    check_name: str
    message: str
    severity: Literal["warning", "critical"] = "warning"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}][{self.severity.upper()}] {self.check_name}: {self.message}"


# ---------------------------------------------------------------------------
# Portfolio protocol (duck-typed to avoid hard coupling to execution layer)
# ---------------------------------------------------------------------------


class _PortfolioView:
    """
    Thin validation wrapper to extract portfolio values regardless of the
    concrete portfolio type used by the caller.

    Supports any object that exposes:
      .nav            → float
      .cash           → float
      .positions      → dict[str, position]  (position has .symbol, .market_value, .quantity)
      .high_water_mark→ float   (peak NAV; optional — falls back to nav if absent)
      .daily_pnl      → float   (today's P&L; optional — defaults to 0.0)
      .start_of_day_nav → float (NAV at market open; optional)
    """

    def __init__(self, portfolio: Any) -> None:
        self._p = portfolio

    @property
    def nav(self) -> float:
        return float(self._p.nav)

    @property
    def cash(self) -> float:
        return float(self._p.cash)

    @property
    def high_water_mark(self) -> float:
        return float(getattr(self._p, "high_water_mark", self.nav))

    @property
    def start_of_day_nav(self) -> float:
        return float(getattr(self._p, "start_of_day_nav", self.nav))

    @property
    def daily_pnl(self) -> float:
        return float(getattr(self._p, "daily_pnl", self.nav - self.start_of_day_nav))

    @property
    def positions(self) -> dict[str, Any]:
        return dict(self._p.positions)

    def gross_leverage(self) -> float:
        """Sum of absolute position market values divided by NAV."""
        total_exposure = sum(abs(p.market_value) for p in self.positions.values())
        nav = self.nav
        return total_exposure / nav if nav > 0 else 0.0

    def position_weights(self) -> dict[str, float]:
        """Returns {symbol: market_value / nav} for all open positions."""
        nav = self.nav
        if nav <= 0:
            return {}
        return {sym: p.market_value / nav for sym, p in self.positions.items()}


# ---------------------------------------------------------------------------
# PortfolioRiskManager
# ---------------------------------------------------------------------------


class PortfolioRiskManager:
    """
    Portfolio-level risk monitoring.

    Parameters
    ----------
    max_drawdown:
        Maximum allowable drawdown from high-water mark (default: -0.15 = -15 %).
    max_sector_exposure:
        Maximum allowable fractional exposure to any one sector (default: 0.30).
    max_correlation:
        Flag pairs whose rolling return correlation exceeds this threshold
        (default: 0.70).
    max_gross_leverage:
        Maximum sum(|weight|) for the portfolio (default: 1.5).
    max_daily_loss:
        Maximum allowable intraday loss as a fraction of start-of-day NAV
        (default: -0.03 = -3 %).
    warning_buffer:
        When a metric is within this fraction of its limit, emit a
        ``"warning"`` even if the check technically passes (default: 0.20,
        meaning warn when within 20 % of the breach level).
    """

    def __init__(
        self,
        max_drawdown: float = 0.15,
        max_sector_exposure: float = 0.30,
        max_correlation: float = 0.70,
        max_gross_leverage: float = 1.50,
        max_daily_loss: float = 0.03,
        warning_buffer: float = 0.20,
    ) -> None:
        self.max_drawdown = abs(max_drawdown)
        self.max_sector_exposure = max_sector_exposure
        self.max_correlation = max_correlation
        self.max_gross_leverage = max_gross_leverage
        self.max_daily_loss = abs(max_daily_loss)
        self.warning_buffer = warning_buffer

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_drawdown(self, portfolio: Any) -> RiskCheck:
        """
        Check whether the portfolio's drawdown from its high-water mark
        exceeds ``max_drawdown``.

        Parameters
        ----------
        portfolio:
            Current portfolio state.

        Returns
        -------
        RiskCheck
        """
        pv = _PortfolioView(portfolio)
        hwm = pv.high_water_mark
        nav = pv.nav

        if hwm <= 0:
            return RiskCheck(
                passed=True,
                check_name="drawdown",
                message="High-water mark is zero or negative — skipping drawdown check.",
                severity="warning",
                metadata={"hwm": hwm, "nav": nav},
            )

        drawdown = (nav - hwm) / hwm  # negative when underwater
        drawdown_pct = abs(min(drawdown, 0.0))

        if drawdown_pct >= self.max_drawdown:
            return RiskCheck(
                passed=False,
                check_name="drawdown",
                message=(
                    f"Drawdown {drawdown_pct:.2%} exceeds maximum {self.max_drawdown:.2%}. "
                    f"NAV={nav:,.2f}, HWM={hwm:,.2f}."
                ),
                severity="critical",
                metadata={"drawdown": drawdown, "hwm": hwm, "nav": nav},
            )

        # Warning zone: within warning_buffer of the limit
        warn_threshold = self.max_drawdown * (1.0 - self.warning_buffer)
        severity = "warning" if drawdown_pct >= warn_threshold else "warning"
        passed = True
        msg = (
            f"Drawdown {drawdown_pct:.2%} within limit {self.max_drawdown:.2%}. "
            f"NAV={nav:,.2f}, HWM={hwm:,.2f}."
        )
        if drawdown_pct >= warn_threshold:
            msg = (
                f"[APPROACHING LIMIT] Drawdown {drawdown_pct:.2%} nearing "
                f"maximum {self.max_drawdown:.2%}."
            )

        log.debug("check_drawdown: drawdown=%.4f limit=%.4f passed=%s", drawdown_pct, self.max_drawdown, passed)
        return RiskCheck(
            passed=passed,
            check_name="drawdown",
            message=msg,
            severity=severity,
            metadata={"drawdown": drawdown, "hwm": hwm, "nav": nav},
        )

    def check_sector_exposure(
        self,
        portfolio: Any,
        sector_map: dict[str, str],
    ) -> RiskCheck:
        """
        Check whether any GICS sector exceeds ``max_sector_exposure``.

        Parameters
        ----------
        portfolio:
            Current portfolio state.
        sector_map:
            Mapping from symbol to sector name (e.g. ``{"AAPL": "Technology"}``).

        Returns
        -------
        RiskCheck
        """
        pv = _PortfolioView(portfolio)
        weights = pv.position_weights()

        sector_weights: dict[str, float] = {}
        for sym, weight in weights.items():
            sector = sector_map.get(sym, "Unknown")
            sector_weights[sector] = sector_weights.get(sector, 0.0) + abs(weight)

        if not sector_weights:
            return RiskCheck(
                passed=True,
                check_name="sector_exposure",
                message="No open positions — sector exposure check skipped.",
                severity="warning",
            )

        max_sector = max(sector_weights, key=lambda s: sector_weights[s])
        max_weight = sector_weights[max_sector]

        if max_weight > self.max_sector_exposure:
            return RiskCheck(
                passed=False,
                check_name="sector_exposure",
                message=(
                    f"Sector '{max_sector}' exposure {max_weight:.2%} exceeds "
                    f"maximum {self.max_sector_exposure:.2%}."
                ),
                severity="critical",
                metadata={
                    "offending_sector": max_sector,
                    "offending_weight": max_weight,
                    "sector_weights": sector_weights,
                },
            )

        warn_threshold = self.max_sector_exposure * (1.0 - self.warning_buffer)
        severity = "warning"
        msg = (
            f"All sector exposures within limit. "
            f"Largest: '{max_sector}' at {max_weight:.2%} (limit {self.max_sector_exposure:.2%})."
        )
        if max_weight >= warn_threshold:
            msg = (
                f"[APPROACHING LIMIT] Sector '{max_sector}' at {max_weight:.2%} "
                f"nearing limit {self.max_sector_exposure:.2%}."
            )

        log.debug(
            "check_sector_exposure: max_sector=%s weight=%.4f limit=%.4f",
            max_sector, max_weight, self.max_sector_exposure,
        )
        return RiskCheck(
            passed=True,
            check_name="sector_exposure",
            message=msg,
            severity=severity,
            metadata={"sector_weights": sector_weights},
        )

    def check_correlation(
        self,
        portfolio: Any,
        returns_data: pd.DataFrame,
        *,
        min_periods: int = 20,
    ) -> RiskCheck:
        """
        Flag position pairs whose rolling return correlation exceeds
        ``max_correlation``.

        Parameters
        ----------
        portfolio:
            Current portfolio state.
        returns_data:
            DataFrame of daily returns with columns = symbol names and
            DatetimeIndex ordered oldest → newest.
        min_periods:
            Minimum observations required to compute a valid correlation.

        Returns
        -------
        RiskCheck
        """
        pv = _PortfolioView(portfolio)
        symbols = list(pv.positions.keys())

        if len(symbols) < 2:
            return RiskCheck(
                passed=True,
                check_name="correlation",
                message="Fewer than 2 positions — correlation check skipped.",
                severity="warning",
            )

        available = [s for s in symbols if s in returns_data.columns]
        if len(available) < 2:
            return RiskCheck(
                passed=True,
                check_name="correlation",
                message=(
                    f"Insufficient return data for correlation check "
                    f"(symbols available: {available})."
                ),
                severity="warning",
            )

        sub = returns_data[available].dropna(how="all")
        if len(sub) < min_periods:
            return RiskCheck(
                passed=True,
                check_name="correlation",
                message=(
                    f"Only {len(sub)} rows of return data — "
                    f"need at least {min_periods} for reliable correlation."
                ),
                severity="warning",
            )

        corr_matrix = sub.corr()
        flagged_pairs: list[tuple[str, str, float]] = []

        for i, sym_a in enumerate(available):
            for sym_b in available[i + 1:]:
                corr_val = corr_matrix.loc[sym_a, sym_b]
                if pd.isna(corr_val):
                    continue
                if abs(corr_val) > self.max_correlation:
                    flagged_pairs.append((sym_a, sym_b, float(corr_val)))

        if flagged_pairs:
            pair_strs = ", ".join(
                f"{a}/{b} ({c:.2f})" for a, b, c in flagged_pairs
            )
            return RiskCheck(
                passed=False,
                check_name="correlation",
                message=(
                    f"{len(flagged_pairs)} highly-correlated pair(s) detected "
                    f"(threshold {self.max_correlation:.2f}): {pair_strs}."
                ),
                severity="warning",  # correlation alone is informational
                metadata={"flagged_pairs": flagged_pairs},
            )

        log.debug(
            "check_correlation: %d symbols checked, no pairs above %.2f",
            len(available), self.max_correlation,
        )
        return RiskCheck(
            passed=True,
            check_name="correlation",
            message=(
                f"No highly-correlated pairs found among {len(available)} positions "
                f"(threshold {self.max_correlation:.2f})."
            ),
            severity="warning",
        )

    def check_gross_leverage(self, portfolio: Any) -> RiskCheck:
        """
        Check whether gross leverage (sum of |position weights|) exceeds
        ``max_gross_leverage``.

        Parameters
        ----------
        portfolio:
            Current portfolio state.

        Returns
        -------
        RiskCheck
        """
        pv = _PortfolioView(portfolio)
        leverage = pv.gross_leverage()

        if leverage > self.max_gross_leverage:
            return RiskCheck(
                passed=False,
                check_name="gross_leverage",
                message=(
                    f"Gross leverage {leverage:.3f}x exceeds maximum "
                    f"{self.max_gross_leverage:.3f}x."
                ),
                severity="critical",
                metadata={"gross_leverage": leverage},
            )

        warn_threshold = self.max_gross_leverage * (1.0 - self.warning_buffer)
        msg = (
            f"Gross leverage {leverage:.3f}x within limit {self.max_gross_leverage:.3f}x."
        )
        if leverage >= warn_threshold:
            msg = (
                f"[APPROACHING LIMIT] Gross leverage {leverage:.3f}x nearing "
                f"limit {self.max_gross_leverage:.3f}x."
            )

        log.debug(
            "check_gross_leverage: leverage=%.4f limit=%.4f",
            leverage, self.max_gross_leverage,
        )
        return RiskCheck(
            passed=True,
            check_name="gross_leverage",
            message=msg,
            severity="warning",
            metadata={"gross_leverage": leverage},
        )

    def check_daily_loss(self, portfolio: Any) -> RiskCheck:
        """
        Check whether today's P&L exceeds the daily loss limit.

        Parameters
        ----------
        portfolio:
            Must expose ``daily_pnl`` (float) and ``start_of_day_nav`` (float),
            or these will be approximated from ``nav`` and ``high_water_mark``.

        Returns
        -------
        RiskCheck
        """
        pv = _PortfolioView(portfolio)
        daily_pnl = pv.daily_pnl
        start_nav = pv.start_of_day_nav

        if start_nav <= 0:
            return RiskCheck(
                passed=True,
                check_name="daily_loss",
                message="Start-of-day NAV is zero — daily loss check skipped.",
                severity="warning",
            )

        daily_loss_pct = daily_pnl / start_nav  # negative when losing

        if daily_loss_pct <= -self.max_daily_loss:
            return RiskCheck(
                passed=False,
                check_name="daily_loss",
                message=(
                    f"Daily loss {daily_loss_pct:.2%} exceeds limit "
                    f"-{self.max_daily_loss:.2%}. "
                    f"PnL={daily_pnl:,.2f}, start NAV={start_nav:,.2f}."
                ),
                severity="critical",
                metadata={
                    "daily_pnl": daily_pnl,
                    "daily_loss_pct": daily_loss_pct,
                    "start_of_day_nav": start_nav,
                },
            )

        warn_threshold = -self.max_daily_loss * (1.0 - self.warning_buffer)
        msg = (
            f"Daily P&L {daily_loss_pct:.2%} within limit -{self.max_daily_loss:.2%}."
        )
        if daily_loss_pct <= warn_threshold:
            msg = (
                f"[APPROACHING LIMIT] Daily P&L {daily_loss_pct:.2%} nearing "
                f"limit -{self.max_daily_loss:.2%}."
            )

        log.debug(
            "check_daily_loss: pnl_pct=%.4f limit=%.4f", daily_loss_pct, -self.max_daily_loss
        )
        return RiskCheck(
            passed=True,
            check_name="daily_loss",
            message=msg,
            severity="warning",
            metadata={
                "daily_pnl": daily_pnl,
                "daily_loss_pct": daily_loss_pct,
                "start_of_day_nav": start_nav,
            },
        )

    # ------------------------------------------------------------------
    # Aggregate check
    # ------------------------------------------------------------------

    def check_all(
        self,
        portfolio: Any,
        *,
        sector_map: dict[str, str] | None = None,
        returns_data: pd.DataFrame | None = None,
    ) -> list[RiskCheck]:
        """
        Run all applicable risk checks and return the full list of results.

        Parameters
        ----------
        portfolio:
            Current portfolio state.
        sector_map:
            Required for the sector-exposure check.  If ``None`` the check
            is skipped.
        returns_data:
            Required for the correlation check.  If ``None`` the check is
            skipped.

        Returns
        -------
        list[RiskCheck]
            All results, including both passing and failing checks.
        """
        results: list[RiskCheck] = []

        results.append(self.check_drawdown(portfolio))
        results.append(self.check_gross_leverage(portfolio))
        results.append(self.check_daily_loss(portfolio))

        if sector_map is not None:
            results.append(self.check_sector_exposure(portfolio, sector_map))
        else:
            log.debug("check_all: sector_map not provided — skipping sector_exposure check")

        if returns_data is not None:
            results.append(self.check_correlation(portfolio, returns_data))
        else:
            log.debug("check_all: returns_data not provided — skipping correlation check")

        failed = [r for r in results if not r.passed]
        critical = [r for r in failed if r.severity == "critical"]
        log.info(
            "check_all: %d checks run, %d failed (%d critical)",
            len(results), len(failed), len(critical),
        )
        return results

    # ------------------------------------------------------------------
    # Signal filtering
    # ------------------------------------------------------------------

    def apply_risk_adjustments(
        self,
        signals: list[Signal],
        portfolio: Any,
        *,
        sector_map: dict[str, str] | None = None,
        returns_data: pd.DataFrame | None = None,
    ) -> list[Signal]:
        """
        Filter or reduce signals to prevent risk limit violations.

        Rules applied (in order):
        1. If the portfolio has a **critical** daily-loss or drawdown breach,
           suppress ALL entry signals (only close/exit signals pass through).
        2. If a new entry signal would cause a **sector** breach, it is dropped.
        3. If the portfolio is already at or above max gross leverage,
           entry signals are dropped.
        4. If a new entry signal is for a symbol that is already
           highly correlated (> ``max_correlation``) with an existing
           position, it is flagged in metadata and passed through with a
           reduced strength (×0.5) so the downstream sizer shrinks the size.

        Parameters
        ----------
        signals:
            Raw signals from the strategy layer.
        portfolio:
            Current portfolio state.
        sector_map:
            Required to apply sector limits.  If ``None`` sector filtering
            is skipped.
        returns_data:
            Required for correlation reduction.

        Returns
        -------
        list[Signal]
            Filtered/adjusted signals safe to pass to the order layer.
        """
        checks = self.check_all(
            portfolio,
            sector_map=sector_map,
            returns_data=returns_data,
        )

        critical_names = {
            c.check_name for c in checks
            if not c.passed and c.severity == "critical"
        }

        pv = _PortfolioView(portfolio)
        adjusted: list[Signal] = []

        # Build sector totals including current positions
        current_sector_weights: dict[str, float] = {}
        if sector_map is not None:
            for sym, weight in pv.position_weights().items():
                sec = sector_map.get(sym, "Unknown")
                current_sector_weights[sec] = current_sector_weights.get(sec, 0.0) + abs(weight)

        # Build correlation set for flagging
        correlated_with_existing: set[str] = set()
        if returns_data is not None and len(pv.positions) > 0:
            existing_symbols = [
                s for s in pv.positions
                if s in returns_data.columns
            ]
            new_symbols = [
                sig.symbol for sig in signals
                if sig.symbol not in pv.positions and sig.symbol in returns_data.columns
            ]
            for new_sym in new_symbols:
                for ex_sym in existing_symbols:
                    sub = returns_data[[new_sym, ex_sym]].dropna()
                    if len(sub) >= 20:
                        corr_val = float(sub.corr().iloc[0, 1])
                        if abs(corr_val) > self.max_correlation:
                            correlated_with_existing.add(new_sym)
                            break

        for sig in signals:
            # Pass close signals through always
            if sig.direction == "close":
                adjusted.append(sig)
                continue

            # Rule 1: critical drawdown or daily loss → block all entries
            if "drawdown" in critical_names or "daily_loss" in critical_names:
                log.warning(
                    "apply_risk_adjustments: suppressing entry signal %s — "
                    "critical risk breach (%s)",
                    sig, critical_names,
                )
                continue

            # Rule 2: gross leverage critical → block entries
            if "gross_leverage" in critical_names:
                log.warning(
                    "apply_risk_adjustments: suppressing entry signal %s — "
                    "gross leverage breached",
                    sig,
                )
                continue

            # Rule 3: sector exposure
            if sector_map is not None:
                sig_sector = sector_map.get(sig.symbol, "Unknown")
                # Estimate weight this new position would add (use max_position_pct as proxy)
                projected_sector_weight = (
                    current_sector_weights.get(sig_sector, 0.0)
                    + 0.10  # conservative estimate: one max-size position
                )
                if projected_sector_weight > self.max_sector_exposure:
                    log.warning(
                        "apply_risk_adjustments: suppressing %s — would breach "
                        "sector '%s' limit (projected %.2f%% > limit %.2f%%)",
                        sig.symbol, sig_sector,
                        projected_sector_weight * 100, self.max_sector_exposure * 100,
                    )
                    continue

            # Rule 4: correlation → halve strength
            if sig.symbol in correlated_with_existing:
                new_strength = sig.strength * 0.5
                log.info(
                    "apply_risk_adjustments: reducing strength for %s "
                    "from %.3f to %.3f (high correlation with existing position)",
                    sig.symbol, sig.strength, new_strength,
                )
                # Signal is frozen; rebuild with updated metadata and strength
                sig = Signal(
                    strategy_name=sig.strategy_name,
                    symbol=sig.symbol,
                    direction=sig.direction,
                    strength=new_strength,
                    timestamp=sig.timestamp,
                    metadata={**sig.metadata, "risk_adjusted": True, "adjustment": "correlation_half"},
                )

            adjusted.append(sig)

        log.info(
            "apply_risk_adjustments: %d signals in → %d signals out",
            len(signals), len(adjusted),
        )
        return adjusted


__all__ = [
    "RiskCheck",
    "PortfolioRiskManager",
]
