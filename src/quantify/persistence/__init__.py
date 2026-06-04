"""
quantify.persistence
~~~~~~~~~~~~~~~~~~~~~
Persistence layer for the Quantify trading system.

Provides SQLite-backed storage for:
- Trade and fill records (audit trail)
- Portfolio snapshots (equity curve reconstruction)
- Strategy state (warm restart after process restarts)
- Signal logs (research and debugging)

Quick start
-----------
::

    from quantify.persistence import Database, TradeLogger, StateManager

    db = Database()          # defaults to data/quantify.db
    db.initialize()          # create tables if not exist

    trade_logger = TradeLogger(db)
    state_mgr    = StateManager(db)
"""

from quantify.persistence.database import Database
from quantify.persistence.trade_log import TradeLogger
from quantify.persistence.state import StateManager

__all__ = [
    "Database",
    "TradeLogger",
    "StateManager",
]
