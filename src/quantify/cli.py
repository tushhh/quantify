"""
quantify.cli
~~~~~~~~~~~~
Click-based command-line interface for the Quantify trading system.

Commands
--------
    quantify backtest   — run a historical backtest
    quantify paper-trade — start paper trading
    quantify report     — generate a performance tearsheet
    quantify universe   — display the trading universe

Usage examples
--------------
    quantify backtest --strategy trend_following --start 2022-01-01 --end 2023-01-01
    quantify backtest --strategy momentum --strategy quality_value --capital 200000
    quantify paper-trade --strategy trend_following --dry-run
    quantify report --start 2023-01-01 --end 2024-01-01
    quantify universe --list
    quantify universe --sector "Information Technology"
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from typing import Optional

import click


def _sanitize_argv(argv: list[str]) -> list[str]:
    """Remove stray shell continuation tokens that sometimes get pasted into Windows terminals."""
    cleaned: list[str] = []
    for arg in argv:
        stripped = arg.strip()
        if not stripped:
            continue
        if stripped in {"`", "^"}:
            continue
        cleaned.append(arg)
    return cleaned


if len(sys.argv) > 1:
    sys.argv[:] = [sys.argv[0], *_sanitize_argv(sys.argv[1:])]

# ---------------------------------------------------------------------------
# Strategy name → class mapping
# ---------------------------------------------------------------------------

_STRATEGY_MAP = {
    "trend_following": "quantify.strategy.trend_following:TrendFollowingStrategy",
    "momentum": "quantify.strategy.cross_sectional_momentum:CrossSectionalMomentumStrategy",
    "pairs": "quantify.strategy.pairs_mean_reversion:PairsMeanReversionStrategy",
    "quality_value": "quantify.strategy.quality_value:QualityValueStrategy",
    "ml": "quantify.strategy.ml_return_predictor:MLReturnPredictorStrategy",
    "vol_regime": "quantify.strategy.volatility_regime:VolatilityRegimeStrategy",
}


def _load_strategy_class(name: str):
    """Dynamically import and return a strategy class by short name."""
    if name not in _STRATEGY_MAP:
        available = ", ".join(sorted(_STRATEGY_MAP))
        raise click.BadParameter(
            f"Unknown strategy '{name}'. Available: {available}",
            param_hint="--strategy",
        )
    module_path, class_name = _STRATEGY_MAP[name].split(":")
    try:
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise click.ClickException(
            f"Failed to load strategy '{name}' from '{module_path}': {exc}"
        )


def _parse_date(value: str, param_name: str) -> date:
    """Parse a date string (YYYY-MM-DD) and return a date object."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise click.BadParameter(
            f"Invalid date '{value}'. Use YYYY-MM-DD format.",
            param_hint=f"--{param_name}",
        )


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="quantify", prog_name="quantify")
def cli() -> None:
    """Quantify — quantitative trading system for US equities."""


# ---------------------------------------------------------------------------
# backtest command
# ---------------------------------------------------------------------------


@cli.command("backtest")
@click.option(
    "--strategy",
    "strategies",
    multiple=True,
    required=True,
    metavar="NAME",
    help=(
        "Strategy to run. Can be specified multiple times. "
        "Choices: " + ", ".join(sorted(_STRATEGY_MAP))
    ),
)
@click.option("--start", required=True, help="Start date (YYYY-MM-DD).")
@click.option("--end", required=True, help="End date (YYYY-MM-DD).")
@click.option(
    "--capital",
    default=100_000.0,
    show_default=True,
    type=float,
    help="Initial capital in USD.",
)
@click.option(
    "--sizer",
    "sizer_name",
    default="equal_weight",
    show_default=True,
    help="Position sizer. Choices: equal_weight, volatility_target, risk_parity, half_kelly.",
)
@click.option(
    "--output-dir",
    default=None,
    help="Directory to save backtest reports and charts (optional).",
)
def backtest(
    strategies: tuple[str, ...],
    start: str,
    end: str,
    capital: float,
    sizer_name: str,
    output_dir: Optional[str],
) -> None:
    """Run a historical backtest for one or more strategies."""
    start_date = _parse_date(start, "start")
    end_date = _parse_date(end, "end")

    if end_date <= start_date:
        raise click.BadParameter(
            "End date must be after start date.", param_hint="--end"
        )

    click.echo(f"Loading configuration...")
    try:
        from quantify.config import load_settings
        settings = load_settings(configure_log=False)
    except Exception as exc:
        raise click.ClickException(f"Failed to load configuration: {exc}")

    # Load strategy instances
    click.echo(f"Loading strategies: {', '.join(strategies)}")
    strategy_instances = []
    for strat_name in strategies:
        cls = _load_strategy_class(strat_name)
        try:
            instance = cls()
            strategy_instances.append(instance)
            click.echo(f"  + {strat_name} ({cls.__name__})")
        except Exception as exc:
            raise click.ClickException(
                f"Failed to instantiate strategy '{strat_name}': {exc}"
            )

    # Build position sizer
    click.echo(f"Using position sizer: {sizer_name}")
    try:
        from quantify.risk.position_sizer import get_sizer
        sizer = get_sizer(sizer_name)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    # Determine the universe of symbols needed
    universe: list[str] = []
    for inst in strategy_instances:
        if hasattr(inst, "universe"):
            universe.extend(inst.universe)
    if not universe:
        from quantify.data.universe import get_sp500
        universe = get_sp500()
    universe = sorted(set(universe))

    click.echo(
        f"Fetching data for {len(universe)} symbols "
        f"({start_date} to {end_date})..."
    )
    try:
        from quantify.data.providers.yfinance_provider import YFinanceProvider
        provider = YFinanceProvider()
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        data = {}
        with click.progressbar(universe, label="Downloading") as bar:
            for symbol in bar:
                try:
                    df = provider.get_bars(symbol, start=start_dt, end=end_dt)
                    if df is not None and not df.empty:
                        data[symbol] = df
                except Exception:
                    pass  # silently skip symbols with no data
    except Exception as exc:
        raise click.ClickException(f"Data download failed: {exc}")

    if not data:
        raise click.ClickException(
            "No data was retrieved for any symbol. "
            "Check your date range and internet connection."
        )

    click.echo(f"Downloaded data for {len(data)} symbols.")

    # Build cost model
    try:
        from quantify.backtest.costs import CostModel
        cost_model = CostModel(
            commission_per_share=settings.backtest.commission_per_share,
            spread_bps=settings.backtest.spread_bps,
            slippage_pct=settings.backtest.slippage_pct,
        )
    except Exception:
        from quantify.backtest.costs import CostModel
        cost_model = CostModel()

    # Run backtest
    click.echo(f"Running backtest ({start_date} to {end_date}, capital=${capital:,.0f})...")
    try:
        from quantify.backtest.engine import BacktestEngine
        engine = BacktestEngine(
            strategies=strategy_instances,
            initial_capital=capital,
            cost_model=cost_model,
            position_sizer=sizer,
            start_date=start_date,
            end_date=end_date,
        )
        result = engine.run(data=data)
    except Exception as exc:
        raise click.ClickException(f"Backtest failed: {exc}")

    # Print report
    try:
        from quantify.backtest.report import BacktestReport
        report = BacktestReport(result)
        report.print_summary()
    except Exception as exc:
        click.echo(f"Warning: could not print report: {exc}", err=True)
        click.echo(repr(result))

    # Optionally save
    if output_dir:
        click.echo(f"Saving report to {output_dir}...")
        try:
            from quantify.backtest.report import BacktestReport
            report = BacktestReport(result)
            saved_path = report.save(output_dir)
            click.echo(f"Report saved to {saved_path}")
        except Exception as exc:
            click.echo(f"Warning: could not save report: {exc}", err=True)


# ---------------------------------------------------------------------------
# paper-trade command
# ---------------------------------------------------------------------------


@cli.command("paper-trade")
@click.option(
    "--strategy",
    "strategies",
    multiple=True,
    metavar="NAME",
    help="Strategy to run (can be specified multiple times). Defaults to all enabled strategies.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generate signals but do not submit orders.",
)
def paper_trade(strategies: tuple[str, ...], dry_run: bool) -> None:
    """Start the paper trading engine."""
    click.echo("Loading configuration...")
    try:
        from quantify.config import load_settings
        settings = load_settings(configure_log=False)
    except Exception as exc:
        raise click.ClickException(f"Failed to load configuration: {exc}")

    # Determine which strategies to use
    if strategies:
        click.echo(f"Loading strategies: {', '.join(strategies)}")
        strategy_instances = []
        for strat_name in strategies:
            cls = _load_strategy_class(strat_name)
            try:
                instance = cls()
                strategy_instances.append(instance)
                click.echo(f"  + {strat_name} ({cls.__name__})")
            except Exception as exc:
                raise click.ClickException(
                    f"Failed to instantiate strategy '{strat_name}': {exc}"
                )
    else:
        # Load all enabled strategies from config
        click.echo("Loading all enabled strategies from config...")
        strategy_instances = []
        for strat_key, strat_cfg in settings.strategies.items():
            if not strat_cfg.enabled:
                continue
            if strat_key in _STRATEGY_MAP:
                cls = _load_strategy_class(strat_key)
                try:
                    instance = cls()
                    strategy_instances.append(instance)
                    click.echo(f"  + {strat_key} ({cls.__name__})")
                except Exception as exc:
                    click.echo(
                        f"  ! Failed to load {strat_key}: {exc}", err=True
                    )

    if not strategy_instances:
        raise click.ClickException(
            "No strategies loaded. Use --strategy to specify strategies explicitly."
        )

    if dry_run:
        click.echo(
            click.style("DRY RUN mode — signals will be generated but no orders submitted.", fg="yellow")
        )
        _run_dry_run(strategy_instances, settings)
        return

    # Live paper trading
    click.echo("Connecting to Alpaca paper trading account...")
    try:
        from quantify.execution.broker.alpaca_broker import AlpacaBroker
        broker = AlpacaBroker(settings.alpaca)
    except Exception as exc:
        raise click.ClickException(
            f"Failed to connect to Alpaca broker: {exc}. "
            "Ensure ALPACA_API_KEY and ALPACA_SECRET_KEY are set."
        )

    click.echo("Starting paper trader...")
    try:
        from quantify.paper.trader import PaperTrader
        trader = PaperTrader(
            strategies=strategy_instances,
            broker=broker,
            config=settings,
        )
        click.echo(click.style("Paper trader running. Press Ctrl+C to stop.", fg="green"))
        trader.run()
    except KeyboardInterrupt:
        click.echo("\nShutting down paper trader...")
    except Exception as exc:
        raise click.ClickException(f"Paper trader failed: {exc}")


def _run_dry_run(strategy_instances, settings) -> None:
    """Run strategies in dry-run mode — generate signals without submitting orders."""
    from datetime import timezone

    click.echo("Fetching recent market data for signal generation...")
    try:
        from quantify.data.providers.yfinance_provider import YFinanceProvider
        from quantify.data.features import FeatureEngine
        from quantify.data.universe import get_sp500

        provider = YFinanceProvider()
        end_dt = datetime.now(timezone.utc)
        from datetime import timedelta
        # Fetch 5 years to ensure enough history for ML training (504 bars)
        # after technical indicators (252 bars) are computed.
        start_dt = end_dt - timedelta(days=1825)

        universe: list[str] = []
        for inst in strategy_instances:
            if hasattr(inst, "universe"):
                universe.extend(inst.universe)
        if not universe:
            universe = get_sp500()
        # Keep the full universe so cross-sectional strategies have enough symbols
        # for meaningful ranking. Cap at 150 to avoid overly long downloads.
        universe = sorted(set(universe))[:150]

        data = {}
        with click.progressbar(universe, label="Fetching") as bar:
            for symbol in bar:
                try:
                    df = provider.get_bars(symbol, start=start_dt, end=end_dt)
                    if df is not None and not df.empty:
                        data[symbol] = df
                except Exception:
                    pass
    except Exception as exc:
        raise click.ClickException(f"Data fetch failed: {exc}")

    if not data:
        click.echo("No data available. Cannot generate signals.")
        return

    # Compute features required by all strategies and merge into OHLCV data
    required_features: set[str] = set()
    for inst in strategy_instances:
        try:
            required_features.update(inst.get_required_features())
        except Exception:
            pass

    if required_features:
        try:
            engine = FeatureEngine()
            features_only = engine.compute(data, required=list(required_features))
            enriched: dict = {}
            for sym, raw_df in data.items():
                feat_df = features_only.get(sym)
                if feat_df is not None:
                    enriched[sym] = raw_df.join(feat_df, how="left", rsuffix="_feat")
                else:
                    enriched[sym] = raw_df
            data = enriched
        except Exception as exc:
            click.echo(f"  Warning: feature computation failed ({exc}) — signals may be empty", err=True)

    click.echo(f"Generating signals from {len(data)} symbols...")
    for strat in strategy_instances:
        click.echo(f"\nStrategy: {strat.name}")
        try:
            signals = strat.generate_signals(data)
            latest_bar_date = _latest_data_date(data)
            long_sigs = [s for s in signals if s.direction == "long"]
            short_sigs = [s for s in signals if s.direction == "short"]
            close_sigs = [s for s in signals if s.direction == "close"]
            click.echo(
                f"  Signals: {len(signals)} total — "
                f"{len(long_sigs)} long, {len(short_sigs)} short, {len(close_sigs)} close"
            )
            if latest_bar_date is not None:
                click.echo(f"  Latest bar date: {latest_bar_date:%Y-%m-%d}")
            if any("mom_12_1" in getattr(s, "metadata", {}) for s in signals):
                ranked = sorted(
                    [s for s in signals if "mom_12_1" in getattr(s, "metadata", {})],
                    key=lambda s: s.metadata.get("mom_12_1", float("-inf")),
                    reverse=True,
                )
                click.echo("  Momentum ranking (top 3 longs / shorts):")
                top_longs = [sig for sig in ranked if sig.direction == "long"][:3]
                top_shorts = [sig for sig in reversed(ranked) if sig.direction == "short"][:3]
                for sig in top_longs:
                    click.echo(
                        f"    LONG  {sig.symbol:<8} mom_12_1={sig.metadata.get('mom_12_1', 0):+.6f} "
                        f"rank={sig.metadata.get('percentile_rank', 0):.4f}"
                    )
                for sig in top_shorts:
                    click.echo(
                        f"    SHORT {sig.symbol:<8} mom_12_1={sig.metadata.get('mom_12_1', 0):+.6f} "
                        f"rank={sig.metadata.get('percentile_rank', 0):.4f}"
                    )
            for sig in long_sigs[:5]:
                click.echo(f"    LONG  {sig.symbol:<8}  strength={sig.strength:+.3f}")
            for sig in short_sigs[:5]:
                click.echo(f"    SHORT {sig.symbol:<8}  strength={sig.strength:+.3f}")
        except Exception as exc:
            click.echo(f"  Error generating signals: {exc}", err=True)


def _latest_data_date(data: dict[str, object]) -> Optional[datetime]:
    """Return the latest timestamp across the fetched data frames."""
    latest: Optional[datetime] = None
    for df in data.values():
        if getattr(df, "empty", True):
            continue
        ts = df.index[-1]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if latest is None or ts > latest:
            latest = ts
    return latest


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


@cli.command("report")
@click.option("--start", default=None, help="Filter trades from this date (YYYY-MM-DD).")
@click.option("--end", default=None, help="Filter trades to this date (YYYY-MM-DD).")
@click.option(
    "--output-dir",
    default=None,
    help="Directory to save the tearsheet (optional).",
)
@click.option(
    "--db-path",
    default=None,
    help="Path to the SQLite trade database (optional, uses default if not set).",
)
def report(
    start: Optional[str],
    end: Optional[str],
    output_dir: Optional[str],
    db_path: Optional[str],
) -> None:
    """Generate a performance tearsheet from the trade log."""
    start_date = _parse_date(start, "start") if start else None
    end_date = _parse_date(end, "end") if end else None

    click.echo("Loading trade log from database...")
    try:
        from quantify.persistence.database import Database
        db = Database(db_path) if db_path else Database()
        db.initialize()

        # Build query with optional date filters
        conditions: list[str] = []
        params: list[str] = []
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(str(start_date))
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(str(end_date) + "T23:59:59")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM trades {where} ORDER BY timestamp ASC"
        trades = db.fetchall(sql, params if params else None)
    except Exception as exc:
        raise click.ClickException(f"Failed to read trade log: {exc}")

    if not trades:
        click.echo("No trades found for the specified date range.")
        return

    click.echo(f"Found {len(trades)} trade records.")

    # Build a returns series from fills for the tearsheet
    try:
        import pandas as pd
        import numpy as np

        trade_df = pd.DataFrame(trades)
        click.echo("\nTrade Log Summary")
        click.echo("=" * 50)
        click.echo(f"  Total fills:     {len(trade_df)}")
        if "strategy" in trade_df.columns:
            strats = trade_df["strategy"].unique().tolist()
            click.echo(f"  Strategies:      {', '.join(strats)}")
        if "symbol" in trade_df.columns:
            n_symbols = trade_df["symbol"].nunique()
            click.echo(f"  Symbols traded:  {n_symbols}")
        if "pnl" in trade_df.columns:
            total_pnl = trade_df["pnl"].sum()
            click.echo(f"  Total P&L:       ${total_pnl:,.2f}")

        # Generate tearsheet if output_dir specified
        if output_dir:
            try:
                from quantify.evaluation.tearsheet import Tearsheet
                ts = Tearsheet()
                click.echo(f"Saving tearsheet to {output_dir}...")
                # Pass trades data to tearsheet
                ts.save(trade_df, output_dir)
                click.echo(f"Tearsheet saved to {output_dir}")
            except Exception as exc:
                click.echo(f"Warning: tearsheet generation failed: {exc}", err=True)

    except Exception as exc:
        click.echo(f"Warning: could not summarise trades: {exc}", err=True)


# ---------------------------------------------------------------------------
# universe command
# ---------------------------------------------------------------------------


@cli.command("universe")
@click.option("--list", "list_all", is_flag=True, default=False, help="List all tickers.")
@click.option("--sector", default=None, help="Filter by GICS sector name.")
def universe(list_all: bool, sector: Optional[str]) -> None:
    """Display the available stock universe."""
    try:
        from quantify.data.universe import Universe, get_sector_map, GICS_SECTORS
    except ImportError as exc:
        raise click.ClickException(f"Could not import universe module: {exc}")

    uni = Universe.sp500()

    if sector:
        # Validate the sector name (case-insensitive partial match)
        matched = None
        for s in GICS_SECTORS:
            if sector.lower() in s.lower():
                matched = s
                break
        if matched is None:
            click.echo(f"Unknown sector '{sector}'. Available sectors:")
            for s in GICS_SECTORS:
                click.echo(f"  {s}")
            raise click.Abort()

        filtered = uni.filter_by_sector(matched)
        click.echo(f"Sector: {matched}  ({len(filtered)} tickers)")
        click.echo("-" * 50)
        for ticker in sorted(filtered.tickers):
            click.echo(f"  {ticker}")
        return

    if list_all:
        click.echo(f"Stock Universe  ({len(uni)} tickers)")
        click.echo("=" * 60)
        sector_counts = uni.sector_counts()
        for s, count in sorted(sector_counts.items()):
            click.echo(f"\n  {s}  ({count} tickers)")
            sector_tickers = uni.filter_by_sector(s).tickers
            # Print in columns of 8
            row = []
            for i, ticker in enumerate(sorted(sector_tickers)):
                row.append(f"{ticker:<10}")
                if (i + 1) % 8 == 0:
                    click.echo("    " + "".join(row))
                    row = []
            if row:
                click.echo("    " + "".join(row))
        click.echo(f"\nTotal: {len(uni)} tickers across {len(sector_counts)} sectors")
        return

    # Default: show summary
    click.echo(f"Stock Universe — {len(uni)} tickers")
    click.echo("=" * 50)
    sector_counts = uni.sector_counts()
    for s, count in sorted(sector_counts.items()):
        bar = "#" * min(count, 30)
        click.echo(f"  {s:<35} {count:3d}  {bar}")
    click.echo()
    click.echo("Use --list to see all tickers.")
    click.echo("Use --sector <name> to filter by sector.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
