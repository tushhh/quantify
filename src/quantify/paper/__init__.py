"""
quantify.paper
~~~~~~~~~~~~~~
Paper-trading orchestration for the Quantify trading system.

The paper-trading module provides:

* :class:`~quantify.paper.trader.PaperTrader` — top-level orchestrator that
  wires strategies, risk management, execution, and persistence together and
  drives them through a scheduled daily trading cycle.

* :class:`~quantify.paper.scheduler.TradingScheduler` — APScheduler-backed
  cron scheduler with US market holiday awareness.

* :class:`~quantify.paper.monitor.TradingMonitor` — real-time position and
  P&L monitoring with configurable alerts and dashboard data export.

Quick start
-----------
::

    from quantify.config import load_settings
    from quantify.execution.broker.alpaca_broker import AlpacaBroker
    from quantify.paper import PaperTrader

    config = load_settings()
    broker = AlpacaBroker(config.alpaca)
    # strategies = [...]

    trader = PaperTrader(strategies=strategies, broker=broker, config=config)
    trader.run()   # blocks until Ctrl-C or trader.stop()

Note
----
Imports are deferred to avoid pulling heavy optional dependencies
(``yfinance``, ``apscheduler``) at package import time.  Import the
classes directly if you need fine-grained control:

    from quantify.paper.monitor import TradingMonitor
    from quantify.paper.scheduler import TradingScheduler
    from quantify.paper.trader import PaperTrader
"""


def __getattr__(name: str):  # noqa: ANN001
    """
    Lazy attribute loader so that ``from quantify.paper import X`` only
    imports the relevant submodule rather than all heavy dependencies.
    """
    if name == "PaperTrader":
        from quantify.paper.trader import PaperTrader
        return PaperTrader
    if name == "TradingScheduler":
        from quantify.paper.scheduler import TradingScheduler
        return TradingScheduler
    if name == "TradingMonitor":
        from quantify.paper.monitor import TradingMonitor
        return TradingMonitor
    raise AttributeError(f"module 'quantify.paper' has no attribute {name!r}")


__all__ = [
    "PaperTrader",
    "TradingScheduler",
    "TradingMonitor",
]
