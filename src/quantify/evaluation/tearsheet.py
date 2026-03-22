"""
quantify.evaluation.tearsheet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Performance tearsheet — console report and multi-panel matplotlib figure.

Usage
-----
    from quantify.evaluation.tearsheet import Tearsheet

    ts = Tearsheet(daily_returns, benchmark_returns=spy_returns, trade_returns=trade_rets)
    ts.print_report()
    ts.plot_full_tearsheet(save_path="tearsheet.png")
"""

from __future__ import annotations

import logging
import math
import warnings
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

try:
    import seaborn as sns
    _HAS_SEABORN = True
except ImportError:
    _HAS_SEABORN = False
    warnings.warn("seaborn not installed — tearsheet will use plain matplotlib styling", stacklevel=2)

from quantify.evaluation.metrics import (
    calculate_all,
    max_drawdown,
    sharpe_ratio,
    _clean,
    _TRADING_DAYS,
)

log = logging.getLogger(__name__)

# Colour palette
_STRATEGY_COLOUR = "#2196F3"
_BENCHMARK_COLOUR = "#FF9800"
_DRAWDOWN_COLOUR = "#F44336"
_NEUTRAL_COLOUR = "#90A4AE"


# ---------------------------------------------------------------------------
# Helper — monthly returns pivot table
# ---------------------------------------------------------------------------


def _monthly_returns_table(daily_returns: pd.Series) -> pd.DataFrame:
    """
    Resample daily returns into a month × year pivot table.

    Returns a DataFrame with years as columns and months (1-12) as rows.
    Each cell is the compounded return for that calendar month.
    """
    s = _clean(daily_returns)
    if s.empty or not hasattr(s.index, "to_period"):
        return pd.DataFrame()

    try:
        monthly = (1.0 + s).resample("ME").prod() - 1.0
        monthly.index = monthly.index.to_period("M")
        pivot = monthly.groupby([monthly.index.year, monthly.index.month]).first().unstack(level=0)
        pivot.index.name = "Month"
        pivot.columns.name = "Year"
        return pivot
    except Exception as exc:
        log.warning("Could not build monthly returns table: %s", exc)
        return pd.DataFrame()


def _rolling_sharpe(daily_returns: pd.Series, window: int = 126) -> pd.Series:
    """Rolling annualised Sharpe ratio over *window* trading days."""
    s = _clean(daily_returns)
    if len(s) < window:
        return pd.Series(dtype=float)

    def _window_sharpe(x: np.ndarray) -> float:
        std = x.std(ddof=1)
        if std == 0.0:
            return 0.0
        return float(x.mean() / std * math.sqrt(_TRADING_DAYS))

    return s.rolling(window).apply(_window_sharpe, raw=True)


def _rolling_volatility(daily_returns: pd.Series, window: int = 30) -> pd.Series:
    """Rolling annualised volatility over *window* trading days."""
    s = _clean(daily_returns)
    if len(s) < 2:
        return pd.Series(dtype=float)
    return s.rolling(window).std(ddof=1) * math.sqrt(_TRADING_DAYS)


def _cumulative_returns(daily_returns: pd.Series) -> pd.Series:
    """Convert daily returns to cumulative equity curve (starting at 1.0)."""
    s = _clean(daily_returns)
    if s.empty:
        return pd.Series(dtype=float)
    return (1.0 + s).cumprod()


def _drawdown_series(daily_returns: pd.Series) -> pd.Series:
    """Return time series of drawdown from peak (all values <= 0)."""
    cum = _cumulative_returns(daily_returns)
    if cum.empty:
        return pd.Series(dtype=float)
    running_max = cum.cummax()
    return cum / running_max - 1.0


# ---------------------------------------------------------------------------
# Tearsheet
# ---------------------------------------------------------------------------


class Tearsheet:
    """
    Comprehensive performance tearsheet for a trading strategy.

    Parameters
    ----------
    daily_returns:
        Series of daily returns with a DatetimeIndex.
    benchmark_returns:
        Optional benchmark daily return series aligned with *daily_returns*.
    trade_returns:
        Optional per-trade return series.
    risk_free_rate:
        Annual risk-free rate (decimal) used in risk-adjusted metrics.
    strategy_name:
        Display name for the strategy.
    benchmark_name:
        Display name for the benchmark.
    """

    def __init__(
        self,
        daily_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        trade_returns: Optional[pd.Series] = None,
        risk_free_rate: float = 0.0,
        strategy_name: str = "Strategy",
        benchmark_name: str = "Benchmark",
    ) -> None:
        self.daily_returns = daily_returns
        self.benchmark_returns = benchmark_returns
        self.trade_returns = trade_returns
        self.risk_free_rate = risk_free_rate
        self.strategy_name = strategy_name
        self.benchmark_name = benchmark_name
        self._metrics: Optional[dict] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(self) -> dict:
        """
        Compute all metrics and return them as a flat dictionary.

        Results are cached after the first call.
        """
        if self._metrics is None:
            self._metrics = calculate_all(
                self.daily_returns,
                benchmark_returns=self.benchmark_returns,
                trade_returns=self.trade_returns,
                risk_free_rate=self.risk_free_rate,
            )
        return self._metrics

    def print_report(self) -> None:
        """
        Print a nicely formatted console tearsheet.

        Sections: Returns, Risk, Risk-Adjusted, Trade Stats, Drawdown.
        """
        m = self.generate()

        _header = lambda title: print(f"\n{'-' * 50}\n  {title}\n{'-' * 50}")
        _row = lambda label, value, fmt=".4f": print(f"  {label:<35} {value:{fmt}}")
        _pct = lambda label, value: print(f"  {label:<35} {value * 100:.2f}%")

        print(f"\n{'=' * 50}")
        print(f"  PERFORMANCE TEARSHEET -- {self.strategy_name}")
        print(f"{'=' * 50}")

        # --- Returns ---
        _header("Returns")
        _pct("Total Return", m["total_return"])
        _pct("CAGR", m["cagr"])
        _pct("Annual Volatility", m["annual_volatility"])
        _pct("Daily Volatility", m["daily_volatility"])

        # --- Risk ---
        _header("Risk")
        _pct("Max Drawdown", m["max_drawdown"])
        _row("Max Drawdown Duration (days)", m["max_drawdown_duration_days"], "d")
        _pct("VaR 95%", m["var_95"])
        _pct("CVaR 95%", m["cvar_95"])
        _pct("VaR 99%", m["var_99"])
        _pct("CVaR 99%", m["cvar_99"])
        _row("Skewness", m["skewness"])
        _row("Kurtosis (excess)", m["kurtosis"])

        # --- Risk-Adjusted ---
        _header("Risk-Adjusted Performance")
        _row("Sharpe Ratio", m["sharpe_ratio"])
        _row("Sortino Ratio", m["sortino_ratio"])
        _row("Calmar Ratio", m["calmar_ratio"])

        if not math.isnan(m.get("beta", float("nan"))):
            _row("Beta", m["beta"])
            _pct("Alpha (Jensen's, annualised)", m["alpha"])
            _row("Information Ratio", m["information_ratio"])
            _row("Treynor Ratio", m["treynor_ratio"])

        # --- Trade Stats ---
        if not math.isnan(m.get("win_rate", float("nan"))):
            _header("Trade Statistics")
            _pct("Win Rate", m["win_rate"])
            _row("Profit Factor", m["profit_factor"])
            _row("Avg Win / Avg Loss", m["avg_win_loss_ratio"])
            _row("Number of Trades", m["n_trades"], "d")
            _pct("Avg Trade Return", m["avg_trade_return"])

        # --- Drawdown summary ---
        _header("Drawdown")
        _pct("Max Drawdown", m["max_drawdown"])
        _row("Longest Drawdown Duration (days)", m["max_drawdown_duration_days"], "d")

        print(f"\n{'=' * 50}\n")

    def plot_full_tearsheet(self, save_path: Optional[str] = None) -> plt.Figure:
        """
        Generate and display a six-panel performance tearsheet figure.

        Panels
        ------
        1. Cumulative returns vs benchmark
        2. Drawdown underwater chart
        3. Monthly returns heatmap
        4. Rolling 6-month (126-day) Sharpe ratio
        5. Daily returns distribution histogram
        6. Rolling 30-day volatility

        Parameters
        ----------
        save_path:
            If provided, save the figure to this path.  Supports any
            format recognised by matplotlib (e.g. "tearsheet.png").

        Returns
        -------
        matplotlib.figure.Figure
        """
        if _HAS_SEABORN:
            sns.set_theme(style="darkgrid", palette="muted", font_scale=0.85)
        else:
            matplotlib.rcParams.update({"axes.grid": True, "grid.alpha": 0.3})

        s = _clean(self.daily_returns)

        fig = plt.figure(figsize=(18, 20), constrained_layout=True)
        fig.suptitle(
            f"Performance Tearsheet — {self.strategy_name}",
            fontsize=16,
            fontweight="bold",
            y=0.995,
        )

        # Define grid: 3 rows × 2 cols with irregular heights
        gs = fig.add_gridspec(4, 2, height_ratios=[2, 1.2, 1.5, 1.5])

        ax_cum = fig.add_subplot(gs[0, :])   # Cumulative returns (full width)
        ax_dd = fig.add_subplot(gs[1, :])    # Drawdown (full width)
        ax_monthly = fig.add_subplot(gs[2, 0])  # Monthly heatmap
        ax_rolling_sharpe = fig.add_subplot(gs[2, 1])  # Rolling Sharpe
        ax_hist = fig.add_subplot(gs[3, 0])   # Return distribution
        ax_vol = fig.add_subplot(gs[3, 1])    # Rolling volatility

        # ------------------------------------------------------------------
        # Panel 1: Cumulative returns
        # ------------------------------------------------------------------
        cum_strat = _cumulative_returns(s)
        if not cum_strat.empty:
            ax_cum.plot(
                cum_strat.index,
                cum_strat.values,
                color=_STRATEGY_COLOUR,
                linewidth=1.5,
                label=self.strategy_name,
            )

        if self.benchmark_returns is not None:
            b = _clean(self.benchmark_returns)
            if not b.empty:
                cum_bench = _cumulative_returns(b)
                ax_cum.plot(
                    cum_bench.index,
                    cum_bench.values,
                    color=_BENCHMARK_COLOUR,
                    linewidth=1.2,
                    linestyle="--",
                    label=self.benchmark_name,
                    alpha=0.85,
                )

        ax_cum.set_title("Cumulative Returns", fontweight="bold")
        ax_cum.set_ylabel("Portfolio Value (base = 1.0)")
        ax_cum.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.2f}x"))
        ax_cum.legend(loc="upper left")
        ax_cum.axhline(1.0, color="grey", linewidth=0.7, linestyle=":")

        # ------------------------------------------------------------------
        # Panel 2: Drawdown underwater
        # ------------------------------------------------------------------
        dd_series = _drawdown_series(s)
        if not dd_series.empty:
            ax_dd.fill_between(
                dd_series.index,
                dd_series.values,
                0,
                color=_DRAWDOWN_COLOUR,
                alpha=0.7,
            )
            ax_dd.plot(dd_series.index, dd_series.values, color=_DRAWDOWN_COLOUR, linewidth=0.8)

        ax_dd.set_title("Drawdown", fontweight="bold")
        ax_dd.set_ylabel("Drawdown")
        ax_dd.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
        ax_dd.set_ylim(top=0.02)

        # ------------------------------------------------------------------
        # Panel 3: Monthly returns heatmap
        # ------------------------------------------------------------------
        monthly_pivot = _monthly_returns_table(s)

        if not monthly_pivot.empty and _HAS_SEABORN:
            # Convert to percentage for display
            display_pivot = monthly_pivot * 100
            month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            display_pivot.index = [
                month_labels[i - 1] if 1 <= i <= 12 else str(i)
                for i in display_pivot.index
            ]
            sns.heatmap(
                display_pivot,
                ax=ax_monthly,
                cmap="RdYlGn",
                center=0,
                fmt=".1f",
                annot=True,
                annot_kws={"size": 7},
                linewidths=0.3,
                cbar_kws={"label": "Return (%)"},
            )
            ax_monthly.set_title("Monthly Returns (%)", fontweight="bold")
            ax_monthly.set_xlabel("Year")
            ax_monthly.set_ylabel("Month")
        elif not monthly_pivot.empty:
            # Fallback: simple table-style plot
            display_pivot = monthly_pivot * 100
            im = ax_monthly.imshow(
                display_pivot.values,
                cmap="RdYlGn",
                aspect="auto",
            )
            ax_monthly.set_title("Monthly Returns (%)", fontweight="bold")
            ax_monthly.set_yticks(range(len(display_pivot.index)))
            ax_monthly.set_yticklabels(display_pivot.index)
            ax_monthly.set_xticks(range(len(display_pivot.columns)))
            ax_monthly.set_xticklabels(display_pivot.columns, rotation=45)
            plt.colorbar(im, ax=ax_monthly, label="Return (%)")
        else:
            ax_monthly.text(
                0.5, 0.5, "Insufficient data\nfor monthly heatmap",
                ha="center", va="center", transform=ax_monthly.transAxes,
                fontsize=11, color="grey",
            )
            ax_monthly.set_title("Monthly Returns (%)", fontweight="bold")

        # ------------------------------------------------------------------
        # Panel 4: Rolling 6-month Sharpe
        # ------------------------------------------------------------------
        rolling_sharpe = _rolling_sharpe(s, window=126)

        if not rolling_sharpe.empty and rolling_sharpe.dropna().shape[0] > 0:
            rs_clean = rolling_sharpe.dropna()
            ax_rolling_sharpe.plot(
                rs_clean.index,
                rs_clean.values,
                color=_STRATEGY_COLOUR,
                linewidth=1.3,
            )
            ax_rolling_sharpe.fill_between(
                rs_clean.index,
                rs_clean.values,
                0,
                where=rs_clean.values >= 0,
                alpha=0.25,
                color=_STRATEGY_COLOUR,
            )
            ax_rolling_sharpe.fill_between(
                rs_clean.index,
                rs_clean.values,
                0,
                where=rs_clean.values < 0,
                alpha=0.25,
                color=_DRAWDOWN_COLOUR,
            )
        else:
            ax_rolling_sharpe.text(
                0.5, 0.5, "Insufficient data\nfor rolling Sharpe",
                ha="center", va="center", transform=ax_rolling_sharpe.transAxes,
                fontsize=11, color="grey",
            )

        ax_rolling_sharpe.axhline(0, color="grey", linewidth=0.7, linestyle=":")
        ax_rolling_sharpe.set_title("Rolling 6-Month Sharpe Ratio", fontweight="bold")
        ax_rolling_sharpe.set_ylabel("Sharpe Ratio")

        # ------------------------------------------------------------------
        # Panel 5: Daily return distribution
        # ------------------------------------------------------------------
        if not s.empty:
            if _HAS_SEABORN:
                sns.histplot(
                    s.values * 100,
                    ax=ax_hist,
                    bins=50,
                    kde=True,
                    color=_STRATEGY_COLOUR,
                    edgecolor="white",
                    linewidth=0.4,
                    alpha=0.75,
                )
            else:
                ax_hist.hist(
                    s.values * 100,
                    bins=50,
                    color=_STRATEGY_COLOUR,
                    edgecolor="white",
                    linewidth=0.4,
                    alpha=0.75,
                    density=True,
                )
            ax_hist.axvline(0, color="grey", linewidth=0.8, linestyle=":")
            ax_hist.axvline(
                float(s.mean() * 100),
                color=_STRATEGY_COLOUR,
                linewidth=1.3,
                linestyle="--",
                alpha=0.8,
                label=f"Mean: {s.mean() * 100:.3f}%",
            )
            ax_hist.legend(fontsize=8)

        ax_hist.set_title("Daily Return Distribution", fontweight="bold")
        ax_hist.set_xlabel("Daily Return (%)")
        ax_hist.set_ylabel("Frequency")

        # ------------------------------------------------------------------
        # Panel 6: Rolling 30-day volatility
        # ------------------------------------------------------------------
        rolling_vol = _rolling_volatility(s, window=30)

        if not rolling_vol.empty and rolling_vol.dropna().shape[0] > 0:
            rv_clean = rolling_vol.dropna()
            ax_vol.plot(
                rv_clean.index,
                rv_clean.values * 100,
                color=_STRATEGY_COLOUR,
                linewidth=1.3,
            )
            ax_vol.fill_between(
                rv_clean.index,
                rv_clean.values * 100,
                0,
                alpha=0.2,
                color=_STRATEGY_COLOUR,
            )

            if self.benchmark_returns is not None:
                b = _clean(self.benchmark_returns)
                bench_vol = _rolling_volatility(b, window=30)
                if not bench_vol.empty and bench_vol.dropna().shape[0] > 0:
                    bv_clean = bench_vol.dropna()
                    ax_vol.plot(
                        bv_clean.index,
                        bv_clean.values * 100,
                        color=_BENCHMARK_COLOUR,
                        linewidth=1.0,
                        linestyle="--",
                        alpha=0.85,
                        label=self.benchmark_name,
                    )
                    ax_vol.legend(fontsize=8)
        else:
            ax_vol.text(
                0.5, 0.5, "Insufficient data\nfor rolling volatility",
                ha="center", va="center", transform=ax_vol.transAxes,
                fontsize=11, color="grey",
            )

        ax_vol.set_title("Rolling 30-Day Volatility (annualised)", fontweight="bold")
        ax_vol.set_ylabel("Volatility (%)")
        ax_vol.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))

        # ------------------------------------------------------------------
        # Save or show
        # ------------------------------------------------------------------
        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            log.info("Tearsheet saved to %s", save_path)
        else:
            plt.show()

        return fig


__all__ = ["Tearsheet"]
