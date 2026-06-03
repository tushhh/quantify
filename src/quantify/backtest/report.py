"""
quantify.backtest.report
~~~~~~~~~~~~~~~~~~~~~~~~
Backtest reporting: console summaries, matplotlib charts, and file export.

:class:`BacktestReport` wraps a :class:`~quantify.backtest.engine.BacktestResult`
and provides multiple views of the same data:

* :meth:`summary`          — dict of all key metrics for programmatic use.
* :meth:`print_summary`    — formatted console output.
* :meth:`plot_equity_curve`— equity vs benchmark chart.
* :meth:`plot_drawdown`    — underwater equity (drawdown) chart.
* :meth:`plot_monthly_returns` — monthly-return heatmap.
* :meth:`plot_trade_analysis`  — trade P&L distribution and win/loss stats.
* :meth:`save`             — write all charts + summary JSON to a directory.

Benchmark handling
------------------
If the BacktestResult's data dict contains the benchmark symbol (default
``"SPY"``) the equity-curve plot will overlay the benchmark.  Otherwise the
benchmark line is omitted silently.

Matplotlib availability
-----------------------
All plot methods gracefully degrade if matplotlib is not installed — they log
a warning and return ``None``.

Usage
-----
    from quantify.backtest.report import BacktestReport

    report = BacktestReport(result)
    report.print_summary()
    report.plot_equity_curve()
    report.save("/tmp/my_backtest")
"""

from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from quantify.backtest.engine import BacktestResult

log = logging.getLogger(__name__)

# Optional matplotlib import — fail gracefully
try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend for headless/server environments
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    from matplotlib.colors import LinearSegmentedColormap
    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False
    log.warning(
        "matplotlib is not installed.  Plotting methods will be disabled. "
        "Install with: pip install matplotlib"
    )

_TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# BacktestReport
# ---------------------------------------------------------------------------


class BacktestReport:
    """
    Reporting and visualisation wrapper for a completed backtest.

    Parameters
    ----------
    result:
        :class:`~quantify.backtest.engine.BacktestResult` produced by
        :class:`~quantify.backtest.engine.BacktestEngine`.
    benchmark_returns:
        Optional :class:`pandas.Series` of daily benchmark returns (aligned
        by date).  When provided, cumulative benchmark performance is overlaid
        on the equity curve plot.
    risk_free_rate:
        Annual risk-free rate used for Sharpe and Sortino calculation
        (default: 0.0).
    """

    def __init__(
        self,
        result: BacktestResult,
        benchmark_returns: Optional[pd.Series] = None,
        risk_free_rate: float = 0.0,
    ) -> None:
        self.result = result
        self.benchmark_returns = benchmark_returns
        self.risk_free_rate = risk_free_rate
        self._daily_rf = (1 + risk_free_rate) ** (1 / _TRADING_DAYS_PER_YEAR) - 1

    # ------------------------------------------------------------------
    # Core metrics
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """
        Return all key backtest metrics as a flat dictionary.

        Returns
        -------
        dict
            Metrics include: total_return, annualized_return, sharpe_ratio,
            sortino_ratio, calmar_ratio, max_drawdown, win_rate, profit_factor,
            avg_trade_pnl, avg_winning_trade, avg_losing_trade, n_trades,
            n_winning_trades, n_losing_trades, avg_holding_days, metadata.
        """
        r = self.result
        eq = r.equity_curve
        rets = r.daily_returns.dropna()
        trades = r.trades

        # Return metrics
        total_return = r.total_return
        annualized_return = r.annualized_return
        sharpe = self._calc_sharpe(rets)
        sortino = self._calc_sortino(rets)
        max_dd = r.max_drawdown
        calmar = annualized_return / max_dd if max_dd > 0 else float("inf")

        # Trade metrics
        n_trades = len(trades)
        winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
        losing_trades = [t for t in trades if t.get("pnl", 0) <= 0]
        n_winning = len(winning_trades)
        n_losing = len(losing_trades)
        win_rate = n_winning / n_trades if n_trades > 0 else 0.0
        avg_pnl = np.mean([t.get("pnl", 0) for t in trades]) if trades else 0.0
        avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0.0
        avg_loss = np.mean([t["pnl"] for t in losing_trades]) if losing_trades else 0.0
        gross_profit = sum(t["pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        avg_holding = np.mean([t.get("holding_days", 0) for t in trades]) if trades else 0.0

        # Volatility
        ann_vol = float(rets.std() * math.sqrt(_TRADING_DAYS_PER_YEAR)) if len(rets) > 1 else 0.0

        # Tail ratio: 95th pct return / abs(5th pct return)
        if len(rets) >= 20:
            p95 = float(np.percentile(rets, 95))
            p05 = float(np.percentile(rets, 5))
            tail_ratio = p95 / abs(p05) if abs(p05) > 1e-9 else float("inf")
        else:
            tail_ratio = float("nan")

        # Value at Risk (95%)
        var_95 = float(np.percentile(rets, 5)) if len(rets) >= 20 else float("nan")

        # Max consecutive wins/losses
        max_consec_wins, max_consec_losses = self._max_consecutive(trades)

        # Average MAE / MFE proxy from equity path
        recovery_factor = total_return / max_dd if max_dd > 0 else float("inf")

        metrics = {
            # Period
            "start_date": str(self.result.metadata.get("start", "")),
            "end_date": str(self.result.metadata.get("end", "")),
            "n_trading_days": self.result.metadata.get("n_trading_days", 0),
            "initial_capital": self.result.metadata.get("initial_capital", 0),
            "final_equity": float(eq.iloc[-1]) if len(eq) > 0 else 0.0,

            # Return
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "annualized_return": annualized_return,
            "annualized_return_pct": annualized_return * 100,
            "annualized_volatility": ann_vol,

            # Risk-adjusted
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "recovery_factor": recovery_factor,

            # Drawdown
            "max_drawdown": max_dd,
            "max_drawdown_pct": max_dd * 100,

            # Distribution
            "var_95_daily": var_95,
            "tail_ratio": tail_ratio,

            # Trade statistics
            "n_trades": n_trades,
            "n_winning_trades": n_winning,
            "n_losing_trades": n_losing,
            "win_rate": win_rate,
            "win_rate_pct": win_rate * 100,
            "profit_factor": profit_factor,
            "avg_trade_pnl": float(avg_pnl),
            "avg_winning_trade_pnl": float(avg_win),
            "avg_losing_trade_pnl": float(avg_loss),
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_profit": gross_profit - gross_loss,
            "avg_holding_days": float(avg_holding),
            "max_consecutive_wins": max_consec_wins,
            "max_consecutive_losses": max_consec_losses,

            # Metadata
            "strategies": self.result.metadata.get("strategies", []),
            "symbols": self.result.metadata.get("symbols", []),
        }

        return metrics

    def print_summary(self) -> None:
        """Print a formatted summary table to stdout."""
        m = self.summary()

        header = "=" * 60
        print(header)
        print(f"{'BACKTEST SUMMARY':^60}")
        print(header)

        sections = [
            ("Period", [
                ("Start Date", m["start_date"]),
                ("End Date", m["end_date"]),
                ("Trading Days", f"{m['n_trading_days']:,}"),
                ("Strategies", ", ".join(m["strategies"]) or "N/A"),
                ("Symbols", ", ".join(m["symbols"]) or "N/A"),
            ]),
            ("Capital", [
                ("Initial Capital", f"${m['initial_capital']:,.2f}"),
                ("Final Equity", f"${m['final_equity']:,.2f}"),
                ("Net Profit", f"${m['net_profit']:,.2f}"),
            ]),
            ("Returns", [
                ("Total Return", f"{m['total_return_pct']:.2f}%"),
                ("Annualized Return", f"{m['annualized_return_pct']:.2f}%"),
                ("Annualized Volatility", f"{m['annualized_volatility']*100:.2f}%"),
            ]),
            ("Risk-Adjusted", [
                ("Sharpe Ratio", f"{m['sharpe_ratio']:.3f}"),
                ("Sortino Ratio", f"{m['sortino_ratio']:.3f}"),
                ("Calmar Ratio", f"{m['calmar_ratio']:.3f}"),
                ("Recovery Factor", f"{m['recovery_factor']:.3f}"),
            ]),
            ("Drawdown", [
                ("Max Drawdown", f"{m['max_drawdown_pct']:.2f}%"),
                ("VaR 95% (daily)", f"{m['var_95_daily']*100:.2f}%" if not math.isnan(m["var_95_daily"]) else "N/A"),
            ]),
            ("Trades", [
                ("Total Trades", f"{m['n_trades']:,}"),
                ("Win Rate", f"{m['win_rate_pct']:.1f}%"),
                ("Profit Factor", f"{m['profit_factor']:.3f}" if m['profit_factor'] != float('inf') else "∞"),
                ("Avg Trade P&L", f"${m['avg_trade_pnl']:.2f}"),
                ("Avg Win", f"${m['avg_winning_trade_pnl']:.2f}"),
                ("Avg Loss", f"${m['avg_losing_trade_pnl']:.2f}"),
                ("Avg Holding Days", f"{m['avg_holding_days']:.1f}"),
                ("Max Consec. Wins", str(m["max_consecutive_wins"])),
                ("Max Consec. Losses", str(m["max_consecutive_losses"])),
            ]),
        ]

        for section_name, items in sections:
            print(f"\n  {'─'*56}")
            print(f"  {section_name.upper()}")
            print(f"  {'─'*56}")
            for label, value in items:
                print(f"  {label:<30}{value:>26}")

        print("\n" + header)

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------

    def plot_equity_curve(
        self,
        title: str = "Portfolio Equity Curve",
        figsize: tuple[int, int] = (14, 6),
        show: bool = False,
    ) -> Optional[Any]:
        """
        Plot the portfolio equity curve, optionally vs. a benchmark.

        Parameters
        ----------
        title:
            Chart title.
        figsize:
            Matplotlib figure size (width, height) in inches.
        show:
            If ``True``, call ``plt.show()`` (blocks on interactive backends).

        Returns
        -------
        matplotlib.figure.Figure or None
            The figure object, or ``None`` if matplotlib is unavailable.
        """
        if not _MPL_AVAILABLE:
            log.warning("plot_equity_curve: matplotlib not available")
            return None

        eq = self.result.equity_curve
        if eq.empty:
            log.warning("plot_equity_curve: equity curve is empty")
            return None

        fig, ax = plt.subplots(figsize=figsize)

        # Normalise to 100 at inception
        normalised = eq / eq.iloc[0] * 100

        ax.plot(normalised.index, normalised.values, color="#2196F3", linewidth=1.8,
                label="Strategy", zorder=3)

        # Benchmark overlay
        if self.benchmark_returns is not None and not self.benchmark_returns.empty:
            bm_aligned = self.benchmark_returns.reindex(eq.index, method="ffill").dropna()
            bm_cum = (1 + bm_aligned).cumprod() * 100
            ax.plot(bm_cum.index, bm_cum.values, color="#FF9800", linewidth=1.2,
                    linestyle="--", label="Benchmark", zorder=2, alpha=0.8)

        # Shade below the initial value
        ax.fill_between(normalised.index, 100, normalised.values,
                        where=(normalised.values >= 100), alpha=0.15, color="#2196F3",
                        label="_nolegend_")
        ax.fill_between(normalised.index, 100, normalised.values,
                        where=(normalised.values < 100), alpha=0.15, color="#F44336",
                        label="_nolegend_")

        ax.axhline(100, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)

        m = self.summary()
        subtitle = (
            f"Total Return: {m['total_return_pct']:.1f}%  |  "
            f"Ann. Return: {m['annualized_return_pct']:.1f}%  |  "
            f"Sharpe: {m['sharpe_ratio']:.2f}  |  "
            f"Max DD: {m['max_drawdown_pct']:.1f}%"
        )
        ax.set_title(f"{title}\n{subtitle}", fontsize=12, pad=10)
        ax.set_ylabel("Normalised Equity (Base 100)", fontsize=10)
        ax.set_xlabel("")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

        plt.tight_layout()
        if show:
            plt.show()
        return fig

    def plot_drawdown(
        self,
        title: str = "Portfolio Drawdown",
        figsize: tuple[int, int] = (14, 4),
        show: bool = False,
    ) -> Optional[Any]:
        """
        Plot the underwater equity (drawdown) chart.

        Parameters
        ----------
        title, figsize, show:
            Standard plotting parameters.

        Returns
        -------
        matplotlib.figure.Figure or None
        """
        if not _MPL_AVAILABLE:
            log.warning("plot_drawdown: matplotlib not available")
            return None

        eq = self.result.equity_curve
        if eq.empty:
            log.warning("plot_drawdown: equity curve is empty")
            return None

        rolling_max = eq.cummax()
        drawdown = ((eq - rolling_max) / rolling_max) * 100  # in percent

        fig, ax = plt.subplots(figsize=figsize)
        ax.fill_between(drawdown.index, drawdown.values, 0,
                        color="#F44336", alpha=0.6, label="Drawdown")
        ax.plot(drawdown.index, drawdown.values, color="#C62828", linewidth=0.8)

        max_dd = self.result.max_drawdown * 100
        ax.axhline(-max_dd, color="black", linewidth=1.0, linestyle=":", alpha=0.7,
                   label=f"Max DD: -{max_dd:.1f}%")

        ax.set_title(title, fontsize=12)
        ax.set_ylabel("Drawdown (%)", fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))

        plt.tight_layout()
        if show:
            plt.show()
        return fig

    def plot_monthly_returns(
        self,
        title: str = "Monthly Returns Heatmap",
        figsize: tuple[int, int] = (14, 6),
        show: bool = False,
    ) -> Optional[Any]:
        """
        Plot a calendar heatmap of monthly returns.

        Parameters
        ----------
        title, figsize, show:
            Standard plotting parameters.

        Returns
        -------
        matplotlib.figure.Figure or None
        """
        if not _MPL_AVAILABLE:
            log.warning("plot_monthly_returns: matplotlib not available")
            return None

        eq = self.result.equity_curve
        if len(eq) < 2:
            log.warning("plot_monthly_returns: insufficient data")
            return None

        # Compute monthly returns
        monthly = eq.resample("ME").last()
        monthly_rets = monthly.pct_change().dropna() * 100  # in percent

        if monthly_rets.empty:
            log.warning("plot_monthly_returns: no monthly data")
            return None

        # Build pivot table: rows=year, cols=month
        monthly_rets.index = pd.DatetimeIndex(monthly_rets.index)
        pivot = monthly_rets.groupby([
            monthly_rets.index.year,
            monthly_rets.index.month,
        ]).sum().unstack(fill_value=np.nan)
        pivot.columns = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ][:pivot.shape[1]]

        fig, ax = plt.subplots(figsize=figsize)

        # Custom red-white-green colormap
        cmap = LinearSegmentedColormap.from_list(
            "rwg", ["#C62828", "#FFFFFF", "#2E7D32"]
        )
        abs_max = max(abs(pivot.values[~np.isnan(pivot.values)].min()),
                      abs(pivot.values[~np.isnan(pivot.values)].max())) if pivot.size > 0 else 5

        im = ax.imshow(
            pivot.values,
            cmap=cmap,
            vmin=-abs_max,
            vmax=abs_max,
            aspect="auto",
        )

        # Axis labels
        ax.set_xticks(range(pivot.shape[1]))
        ax.set_xticklabels(pivot.columns, fontsize=9)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index, fontsize=9)

        # Cell text
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                val = pivot.values[i, j]
                if not np.isnan(val):
                    color = "black" if abs(val) < abs_max * 0.6 else "white"
                    ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                            fontsize=7, color=color)

        plt.colorbar(im, ax=ax, label="Monthly Return (%)", shrink=0.8)
        ax.set_title(title, fontsize=12, pad=10)

        plt.tight_layout()
        if show:
            plt.show()
        return fig

    def plot_trade_analysis(
        self,
        title: str = "Trade Analysis",
        figsize: tuple[int, int] = (14, 8),
        show: bool = False,
    ) -> Optional[Any]:
        """
        Plot trade P&L distribution and win/loss statistics.

        Shows four sub-plots:
        1. Histogram of trade P&Ls
        2. Win/loss ratio doughnut chart
        3. P&L scatter by trade index (sequence)
        4. Holding period distribution

        Parameters
        ----------
        title, figsize, show:
            Standard plotting parameters.

        Returns
        -------
        matplotlib.figure.Figure or None
        """
        if not _MPL_AVAILABLE:
            log.warning("plot_trade_analysis: matplotlib not available")
            return None

        trades = self.result.trades
        if not trades:
            log.warning("plot_trade_analysis: no completed trades")
            return None

        pnls = np.array([t.get("pnl", 0) for t in trades])
        holding_days = [t.get("holding_days", 0) or 0 for t in trades]
        wins = pnls[pnls > 0]
        losses = pnls[pnls <= 0]

        fig, axes = plt.subplots(2, 2, figsize=figsize)
        fig.suptitle(title, fontsize=13, y=1.01)

        # ---- 1. P&L histogram ----
        ax1 = axes[0, 0]
        n_bins = min(max(int(len(pnls) / 3), 10), 50)
        ax1.hist(pnls, bins=n_bins, color="#2196F3", edgecolor="white", alpha=0.8)
        ax1.axvline(0, color="black", linewidth=1.2, linestyle="--")
        ax1.axvline(float(np.mean(pnls)), color="#FF9800", linewidth=1.2,
                    linestyle="-", label=f"Mean: ${np.mean(pnls):.0f}")
        ax1.set_title("Trade P&L Distribution")
        ax1.set_xlabel("P&L ($)")
        ax1.set_ylabel("Count")
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # ---- 2. Win/loss doughnut ----
        ax2 = axes[0, 1]
        n_wins = len(wins)
        n_losses = len(losses)
        if n_wins + n_losses > 0:
            sizes = [n_wins, n_losses]
            labels = [f"Wins\n{n_wins} ({n_wins/(n_wins+n_losses)*100:.0f}%)",
                      f"Losses\n{n_losses} ({n_losses/(n_wins+n_losses)*100:.0f}%)"]
            colors_pie = ["#4CAF50", "#F44336"]
            wedges, texts = ax2.pie(
                sizes, labels=labels, colors=colors_pie,
                startangle=90, wedgeprops=dict(width=0.5),
            )
            ax2.set_title("Win / Loss Breakdown")
            # Annotate gross P&L
            net = pnls.sum()
            ax2.text(0, -1.3, f"Net P&L: ${net:,.0f}", ha="center", fontsize=9)

        # ---- 3. P&L by trade sequence ----
        ax3 = axes[1, 0]
        cumulative = np.cumsum(pnls)
        ax3.plot(range(len(cumulative)), cumulative, color="#9C27B0", linewidth=1.5)
        ax3.fill_between(range(len(cumulative)), 0, cumulative,
                         where=(cumulative >= 0), alpha=0.2, color="#4CAF50")
        ax3.fill_between(range(len(cumulative)), 0, cumulative,
                         where=(cumulative < 0), alpha=0.2, color="#F44336")
        ax3.axhline(0, color="black", linewidth=0.8, linestyle="--")
        ax3.set_title("Cumulative P&L by Trade Sequence")
        ax3.set_xlabel("Trade #")
        ax3.set_ylabel("Cumulative P&L ($)")
        ax3.grid(True, alpha=0.3)

        # ---- 4. Holding period distribution ----
        ax4 = axes[1, 1]
        if holding_days and max(holding_days) > 0:
            ax4.hist(holding_days, bins=min(20, len(set(holding_days))),
                     color="#FF9800", edgecolor="white", alpha=0.8)
            avg_hold = np.mean(holding_days)
            ax4.axvline(avg_hold, color="red", linewidth=1.2, linestyle="--",
                        label=f"Mean: {avg_hold:.1f}d")
            ax4.set_title("Holding Period Distribution")
            ax4.set_xlabel("Holding Days")
            ax4.set_ylabel("Count")
            ax4.legend(fontsize=8)
            ax4.grid(True, alpha=0.3)
        else:
            ax4.text(0.5, 0.5, "No holding day data", ha="center", va="center",
                     transform=ax4.transAxes, fontsize=11)
            ax4.set_title("Holding Period Distribution")

        plt.tight_layout()
        if show:
            plt.show()
        return fig

    def plot_returns_distribution(
        self,
        title: str = "Daily Returns Distribution",
        figsize: tuple[int, int] = (10, 5),
        show: bool = False,
    ) -> Optional[Any]:
        """
        Plot a histogram of daily returns overlaid with a normal distribution fit.

        Parameters
        ----------
        title, figsize, show:
            Standard plotting parameters.

        Returns
        -------
        matplotlib.figure.Figure or None
        """
        if not _MPL_AVAILABLE:
            log.warning("plot_returns_distribution: matplotlib not available")
            return None

        rets = self.result.daily_returns.dropna() * 100  # pct
        if len(rets) < 5:
            log.warning("plot_returns_distribution: insufficient data")
            return None

        fig, ax = plt.subplots(figsize=figsize)
        n_bins = min(max(int(len(rets) / 5), 20), 80)
        ax.hist(rets, bins=n_bins, density=True, color="#2196F3", alpha=0.7,
                edgecolor="white", label="Actual returns")

        # Normal fit overlay
        mu, sigma = float(rets.mean()), float(rets.std())
        x = np.linspace(rets.min(), rets.max(), 200)
        normal_pdf = (1 / (sigma * math.sqrt(2 * math.pi))) * np.exp(-0.5 * ((x - mu) / sigma) ** 2)
        ax.plot(x, normal_pdf, color="#FF5722", linewidth=2, label=f"Normal(μ={mu:.2f}%, σ={sigma:.2f}%)")

        ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
        ax.set_title(title, fontsize=12)
        ax.set_xlabel("Daily Return (%)")
        ax.set_ylabel("Probability Density")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        if show:
            plt.show()
        return fig

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, path: str) -> Path:
        """
        Save all available charts and a JSON summary to a directory.

        Parameters
        ----------
        path:
            Directory path (created if it does not exist).

        Returns
        -------
        pathlib.Path
            The directory path where files were saved.
        """
        save_dir = Path(path)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save summary JSON
        summary = self.summary()
        summary_path = save_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as fh:
            json.dump(
                {k: (v if isinstance(v, (int, float, str, list, bool, type(None))) else str(v))
                 for k, v in summary.items()},
                fh,
                indent=2,
                default=_json_serialiser,
            )
        log.info("Saved summary JSON: %s", summary_path)

        if not _MPL_AVAILABLE:
            log.warning("save: matplotlib not available — plots not saved")
            return save_dir

        # Save plots
        plots = {
            "equity_curve.png": self.plot_equity_curve,
            "drawdown.png": self.plot_drawdown,
            "monthly_returns.png": self.plot_monthly_returns,
            "trade_analysis.png": self.plot_trade_analysis,
            "returns_distribution.png": self.plot_returns_distribution,
        }

        for filename, plot_fn in plots.items():
            try:
                fig = plot_fn()
                if fig is not None:
                    fig_path = save_dir / filename
                    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
                    plt.close(fig)
                    log.info("Saved plot: %s", fig_path)
            except Exception as exc:
                log.warning("Failed to save %s: %s", filename, exc)

        log.info("BacktestReport.save: all outputs written to %s", save_dir)
        return save_dir

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calc_sharpe(self, rets: pd.Series) -> float:
        """Annualised Sharpe ratio with the configured risk-free rate."""
        if len(rets) < 2:
            return 0.0
        excess = rets - self._daily_rf
        std = excess.std()
        if std == 0:
            return 0.0
        return float((excess.mean() / std) * math.sqrt(_TRADING_DAYS_PER_YEAR))

    def _calc_sortino(self, rets: pd.Series) -> float:
        """
        Annualised Sortino ratio (downside deviation denominator).

        Only negative excess returns contribute to the downside deviation.
        """
        if len(rets) < 2:
            return 0.0
        excess = rets - self._daily_rf
        downside = excess[excess < 0]
        if len(downside) == 0:
            return float("inf")
        downside_std = math.sqrt((downside ** 2).mean())
        if downside_std == 0:
            return float("inf")
        return float((excess.mean() / downside_std) * math.sqrt(_TRADING_DAYS_PER_YEAR))

    @staticmethod
    def _max_consecutive(trades: list[dict]) -> tuple[int, int]:
        """Return (max_consecutive_wins, max_consecutive_losses)."""
        if not trades:
            return 0, 0

        max_wins = max_losses = cur_wins = cur_losses = 0
        for t in trades:
            pnl = t.get("pnl", 0)
            if pnl > 0:
                cur_wins += 1
                cur_losses = 0
            else:
                cur_losses += 1
                cur_wins = 0
            max_wins = max(max_wins, cur_wins)
            max_losses = max(max_losses, cur_losses)
        return max_wins, max_losses


# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------


def _json_serialiser(obj: Any) -> Any:
    """Custom JSON serialiser for non-standard types."""
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (date, datetime)):
        return str(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return str(obj)
    return str(obj)


__all__ = ["BacktestReport"]
