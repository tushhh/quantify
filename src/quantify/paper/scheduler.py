"""
quantify.paper.scheduler
~~~~~~~~~~~~~~~~~~~~~~~~~
Trading schedule management for the paper-trading system.

The :class:`TradingScheduler` wraps APScheduler's ``BackgroundScheduler``
and wires up the four trading-day jobs required by :class:`PaperTrader`:

1. **pre_market**  — 9:00 AM ET: fetch data, compute features, log status.
2. **trading**     — 9:35 AM ET: generate signals, apply risk, submit orders.
3. **monitor**     — Every 5 minutes from 9:30 AM to 4:00 PM ET: check stops,
                     update P&L.
4. **eod**         — 3:55 PM ET: reconcile positions, log daily summary.

All jobs are automatically skipped on weekends and US market holidays via
:meth:`is_trading_day`.

Dependencies
------------
``apscheduler >= 3.10`` — install with ``pip install "apscheduler>=3,<4"``
``pandas_market_calendars`` (optional but recommended) — provides a full
holiday calendar.  Falls back to a simple weekend-only check if unavailable.

Usage
-----
::

    scheduler = TradingScheduler()
    scheduler.add_trading_jobs(
        pre_market_fn=trader.pre_market,
        trading_fn=trader.generate_and_execute,
        monitor_fn=trader.monitor,
        eod_fn=trader.end_of_day,
    )
    scheduler.start()
    # ... blocks until scheduler.stop() is called externally
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _APSCHEDULER_AVAILABLE = True
except ImportError:
    _APSCHEDULER_AVAILABLE = False
    log.error(
        "APScheduler is not installed.  Install with: pip install 'apscheduler>=3,<4'"
    )

try:
    import pandas_market_calendars as mcal  # type: ignore[import]
    _MCal_AVAILABLE = True
except ImportError:
    _MCal_AVAILABLE = False
    log.warning(
        "pandas_market_calendars not found — holiday detection will use weekend-only fallback. "
        "Install with: pip install pandas-market-calendars"
    )


# ---------------------------------------------------------------------------
# Holiday calendar (static fallback set for common US holidays)
# ---------------------------------------------------------------------------

# Static US market holidays for the current and next few years (fallback only).
# Format: (month, day) tuples for holidays that always fall on the same date.
_FIXED_US_HOLIDAYS: frozenset[tuple[int, int]] = frozenset({
    (1, 1),    # New Year's Day
    (7, 4),    # Independence Day
    (12, 25),  # Christmas Day
})

# ---------------------------------------------------------------------------
# TradingScheduler
# ---------------------------------------------------------------------------


class TradingScheduler:
    """
    Manages the trading-day job schedule using APScheduler.

    All times are expressed in US/Eastern timezone to align with NYSE/NASDAQ
    market hours.

    Parameters
    ----------
    timezone:
        Timezone string for the scheduler (default: ``"America/New_York"``).
    """

    _ET_TZ = "America/New_York"

    def __init__(self, timezone: str = "America/New_York") -> None:
        if not _APSCHEDULER_AVAILABLE:
            raise ImportError(
                "APScheduler is required for TradingScheduler. "
                "Install with: pip install 'apscheduler>=3,<4'"
            )
        self._tz = timezone
        self._scheduler = BackgroundScheduler(timezone=self._tz)
        self._running = False
        log.info("TradingScheduler created (tz=%s)", self._tz)

    # ------------------------------------------------------------------
    # Job registration
    # ------------------------------------------------------------------

    def add_trading_jobs(
        self,
        pre_market_fn: Callable[[], None],
        trading_fn: Callable[[], None],
        monitor_fn: Callable[[], None],
        eod_fn: Callable[[], None],
    ) -> None:
        """
        Register the four standard trading-day jobs.

        All callbacks are wrapped with a trading-day guard that silently
        skips execution on weekends and US market holidays.

        Parameters
        ----------
        pre_market_fn:
            Runs at 9:00 AM ET — fetch data, update features, log status.
        trading_fn:
            Runs at 9:35 AM ET — generate signals and submit orders.
        monitor_fn:
            Runs every 5 minutes from 9:30 AM – 4:00 PM ET — check stops,
            update P&L.
        eod_fn:
            Runs at 3:55 PM ET — reconcile positions, log daily summary.
        """
        def _guard(fn: Callable[[], None], label: str) -> Callable[[], None]:
            """Wrap *fn* so it only executes on trading days."""
            def _wrapper() -> None:
                today = date.today()
                if not self.is_trading_day(today):
                    log.debug("TradingScheduler: skipping '%s' — not a trading day (%s)", label, today)
                    return
                try:
                    log.info("TradingScheduler: running '%s'", label)
                    fn()
                except Exception:
                    log.exception("TradingScheduler: '%s' raised an unhandled exception", label)
            _wrapper.__name__ = label
            return _wrapper

        # Pre-market: 9:00 AM ET daily
        self._scheduler.add_job(
            _guard(pre_market_fn, "pre_market"),
            trigger=CronTrigger(hour=9, minute=0, timezone=self._tz),
            id="pre_market",
            replace_existing=True,
            name="Pre-market data fetch",
            misfire_grace_time=300,  # 5-minute grace window
        )

        # Trading: 9:35 AM ET daily (after initial open volatility settles)
        self._scheduler.add_job(
            _guard(trading_fn, "trading"),
            trigger=CronTrigger(hour=9, minute=35, timezone=self._tz),
            id="trading",
            replace_existing=True,
            name="Signal generation and order submission",
            misfire_grace_time=120,
        )

        # Monitor: every 5 minutes during market hours (9:30 AM – 4:00 PM ET)
        self._scheduler.add_job(
            _guard(self._make_monitor_guard(monitor_fn), "monitor"),
            trigger=CronTrigger(
                hour="9-15",
                minute="*/5",
                day_of_week="mon-fri",
                timezone=self._tz,
            ),
            id="monitor",
            replace_existing=True,
            name="Intraday position monitoring",
            misfire_grace_time=60,
        )

        # End-of-day: 3:55 PM ET
        self._scheduler.add_job(
            _guard(eod_fn, "end_of_day"),
            trigger=CronTrigger(hour=15, minute=55, timezone=self._tz),
            id="end_of_day",
            replace_existing=True,
            name="End-of-day reconciliation",
            misfire_grace_time=300,
        )

        log.info(
            "TradingScheduler: registered 4 jobs — "
            "pre_market(9:00), trading(9:35), monitor(5-min), eod(15:55) ET"
        )

    def _make_monitor_guard(self, monitor_fn: Callable[[], None]) -> Callable[[], None]:
        """
        Create a monitor wrapper that additionally checks market hours
        (9:30 AM – 4:00 PM ET) before executing.
        """
        def _wrapper() -> None:
            from datetime import datetime as _dt
            import pytz  # APScheduler already requires pytz
            try:
                et_tz = pytz.timezone(self._tz)
            except Exception:
                et_tz = None

            if et_tz is not None:
                now_et = _dt.now(et_tz)
                market_open  = now_et.replace(hour=9,  minute=30, second=0, microsecond=0)
                market_close = now_et.replace(hour=16, minute=0,  second=0, microsecond=0)
                if not (market_open <= now_et <= market_close):
                    log.debug("TradingScheduler: monitor skipped — outside market hours")
                    return

            monitor_fn()

        return _wrapper

    # ------------------------------------------------------------------
    # Trading day check
    # ------------------------------------------------------------------

    def is_trading_day(self, check_date: date) -> bool:
        """
        Return ``True`` if *check_date* is a NYSE trading day.

        Uses ``pandas_market_calendars`` when available for a complete holiday
        calendar (including observed holidays, early closes, etc.).  Falls back
        to a weekend + fixed-holiday check when the library is not installed.

        Parameters
        ----------
        check_date:
            The calendar date to check.

        Returns
        -------
        bool
        """
        # Skip weekends first (fast path, always applies)
        if check_date.weekday() >= 5:
            return False

        if _MCal_AVAILABLE:
            return self._is_trading_day_mcal(check_date)
        return self._is_trading_day_fallback(check_date)

    @staticmethod
    def _is_trading_day_mcal(check_date: date) -> bool:
        """Check against the full NYSE market calendar."""
        try:
            nyse = mcal.get_calendar("NYSE")
            schedule = nyse.schedule(
                start_date=str(check_date),
                end_date=str(check_date),
            )
            return not schedule.empty
        except Exception as exc:
            log.warning(
                "TradingScheduler._is_trading_day_mcal: error checking %s: %s — "
                "falling back to weekend check",
                check_date, exc,
            )
            return True  # Err on the side of trading

    @staticmethod
    def _is_trading_day_fallback(check_date: date) -> bool:
        """
        Simplified holiday check (weekend already excluded by caller).

        Handles:
        * Fixed-date holidays (New Year, Independence Day, Christmas)
        * Observed holiday rule: if holiday falls on Saturday, observed Friday;
          if Sunday, observed Monday.
        """
        # Build set of observed holiday dates for this year
        year = check_date.year
        observed: set[date] = set()
        for month, day in _FIXED_US_HOLIDAYS:
            try:
                actual = date(year, month, day)
            except ValueError:
                continue
            wd = actual.weekday()
            if wd == 5:    # Saturday → observe Friday
                observed.add(date(year, month, day - 1) if day > 1 else date(year, month - 1, 30))
            elif wd == 6:  # Sunday → observe Monday
                observed.add(date(year, month, min(day + 1, 31)) if day < 28
                             else date(year, month + 1 if month < 12 else 1, 1))
            else:
                observed.add(actual)

        return check_date not in observed

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the scheduler in the background.

        This call is non-blocking.  The scheduler runs in a daemon thread
        and fires jobs according to their cron triggers.
        """
        if self._running:
            log.warning("TradingScheduler.start: already running")
            return
        self._scheduler.start()
        self._running = True
        log.info("TradingScheduler started")

    def stop(self, wait: bool = True) -> None:
        """
        Shut down the scheduler gracefully.

        Parameters
        ----------
        wait:
            If ``True`` (default), wait for any currently-running jobs to
            complete before returning.
        """
        if not self._running:
            return
        self._scheduler.shutdown(wait=wait)
        self._running = False
        log.info("TradingScheduler stopped (wait=%s)", wait)

    @property
    def is_running(self) -> bool:
        """``True`` if the scheduler is currently active."""
        return self._running

    def get_next_run_times(self) -> dict[str, Optional[datetime]]:
        """
        Return the next scheduled fire time for each registered job.

        Returns
        -------
        dict[str, datetime | None]
            Mapping of job ID to next fire time (UTC-aware), or ``None`` if
            the job has no future runs scheduled.
        """
        result: dict[str, Optional[datetime]] = {}
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            result[job.id] = next_run
        return result

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return f"TradingScheduler(tz={self._tz!r}, status={status})"


__all__ = ["TradingScheduler"]
