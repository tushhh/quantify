"""
quantify.persistence.database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Thread-safe SQLite database management for the Quantify trading system.

The :class:`Database` class provides connection pooling, table initialization,
and a clean query API.  All public methods are safe to call from multiple
threads — each thread gets its own SQLite connection from the pool.

Schema
------
* ``trades``             — filled order records (audit trail)
* ``portfolio_snapshots``— periodic equity/P&L snapshots
* ``strategy_state``     — JSON-serialised per-strategy state (upserted)
* ``signals_log``        — all signals emitted by strategies

Default path
------------
``data/quantify.db`` relative to the repository root (created if absent).
"""

from __future__ import annotations

import logging
import queue
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[3]  # src/quantify/persistence -> repo root
_DEFAULT_DB_PATH: Path = _REPO_ROOT / "data" / "quantify.db"

# DDL statements
_SCHEMA_SQL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS trades (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy    TEXT    NOT NULL,
        symbol      TEXT    NOT NULL,
        side        TEXT    NOT NULL,
        quantity    REAL    NOT NULL,
        price       REAL    NOT NULL,
        commission  REAL    NOT NULL DEFAULT 0.0,
        timestamp   TEXT    NOT NULL,
        order_id    TEXT,
        fill_id     TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp       TEXT    NOT NULL,
        total_value     REAL    NOT NULL,
        cash            REAL    NOT NULL,
        positions_json  TEXT    NOT NULL DEFAULT '[]',
        daily_pnl       REAL    NOT NULL DEFAULT 0.0,
        cumulative_pnl  REAL    NOT NULL DEFAULT 0.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_state (
        strategy_name   TEXT    PRIMARY KEY,
        state_json      TEXT    NOT NULL DEFAULT '{}',
        updated_at      TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp       TEXT    NOT NULL,
        strategy        TEXT    NOT NULL,
        symbol          TEXT    NOT NULL,
        direction       TEXT    NOT NULL,
        strength        REAL    NOT NULL,
        metadata_json   TEXT    NOT NULL DEFAULT '{}'
    )
    """,
    # Indexes for common query patterns
    "CREATE INDEX IF NOT EXISTS idx_trades_strategy   ON trades (strategy)",
    "CREATE INDEX IF NOT EXISTS idx_trades_symbol     ON trades (symbol)",
    "CREATE INDEX IF NOT EXISTS idx_trades_timestamp  ON trades (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_snapshots_ts      ON portfolio_snapshots (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_signals_strategy  ON signals_log (strategy)",
    "CREATE INDEX IF NOT EXISTS idx_signals_symbol    ON signals_log (symbol)",
]

_POOL_SIZE: int = 5


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------


class _ConnectionPool:
    """
    Simple thread-safe SQLite connection pool.

    SQLite connections must not be shared across threads, but creating a new
    connection for every operation is expensive.  This pool keeps a fixed
    number of pre-created connections in a queue and lends them out, returning
    them when the caller is done.

    Parameters
    ----------
    db_path:
        Absolute path to the SQLite database file.
    size:
        Maximum number of connections in the pool.
    """

    def __init__(self, db_path: Path, size: int = _POOL_SIZE) -> None:
        self._db_path = db_path
        self._pool: queue.Queue[sqlite3.Connection] = queue.Queue(maxsize=size)
        for _ in range(size):
            conn = self._make_connection()
            self._pool.put(conn)
        log.debug("Connection pool created: path=%s, size=%d", db_path, size)

    def _make_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # write-ahead log for concurrency
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def acquire(self) -> Iterator[sqlite3.Connection]:
        """
        Borrow a connection from the pool.

        The connection is returned to the pool when the ``with`` block exits,
        even on exceptions.  Raises :exc:`queue.Empty` if all connections are
        in use (timeout 5 s).
        """
        try:
            conn = self._pool.get(timeout=5)
        except queue.Empty:
            log.warning("Connection pool exhausted — creating ad-hoc connection")
            conn = self._make_connection()
            ad_hoc = True
        else:
            ad_hoc = False

        try:
            yield conn
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            if ad_hoc:
                conn.close()
            else:
                self._pool.put(conn)

    def close_all(self) -> None:
        """Close all pooled connections (call on shutdown)."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except queue.Empty:
                break
        log.debug("All pooled connections closed for %s", self._db_path)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


class Database:
    """
    Thread-safe SQLite database manager for Quantify persistence.

    Parameters
    ----------
    db_path:
        Path to the SQLite file.  Defaults to ``data/quantify.db`` in the
        repository root.  Parent directory is created automatically.

    Examples
    --------
    ::

        db = Database()
        db.initialize()

        with db:
            db.execute("INSERT INTO trades (...) VALUES (?)", (value,))

        rows = db.fetchall("SELECT * FROM trades WHERE strategy = ?", ("momentum",))
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path: Path = Path(db_path) if db_path is not None else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._pool: _ConnectionPool = _ConnectionPool(self._db_path)
        self._local = threading.local()  # for explicit transaction support
        log.info("Database initialised: %s", self._db_path)

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Create all required tables and indexes if they do not already exist.

        Safe to call multiple times (idempotent).
        """
        with self._pool.acquire() as conn:
            with conn:
                for stmt in _SCHEMA_SQL:
                    conn.execute(stmt)
        log.info("Database schema initialized: %s", self._db_path)

    # ------------------------------------------------------------------
    # DML helpers
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | list[Any] | None = None,
    ) -> sqlite3.Cursor:
        """
        Execute a single DML statement (INSERT / UPDATE / DELETE) and commit.

        Parameters
        ----------
        sql:
            Parameterised SQL statement.
        params:
            Bind parameters, passed to ``cursor.execute``.

        Returns
        -------
        sqlite3.Cursor
            Cursor after execution (``lastrowid`` and ``rowcount`` are available).
        """
        params = params or ()
        with self._pool.acquire() as conn:
            with conn:
                cursor = conn.execute(sql, params)
        return cursor

    def executemany(
        self,
        sql: str,
        params_seq: list[tuple[Any, ...]] | list[list[Any]],
    ) -> None:
        """
        Execute a batch DML statement for efficiency.

        Parameters
        ----------
        sql:
            Parameterised SQL statement.
        params_seq:
            Sequence of parameter tuples, one per row.
        """
        with self._pool.acquire() as conn:
            with conn:
                conn.executemany(sql, params_seq)

    def fetchall(
        self,
        sql: str,
        params: tuple[Any, ...] | list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a SELECT and return all rows as a list of dicts.

        Parameters
        ----------
        sql:
            SELECT statement.
        params:
            Bind parameters.

        Returns
        -------
        list[dict[str, Any]]
            Each row as a ``{column_name: value}`` dictionary.
        """
        params = params or ()
        with self._pool.acquire() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def fetchone(
        self,
        sql: str,
        params: tuple[Any, ...] | list[Any] | None = None,
    ) -> Optional[dict[str, Any]]:
        """
        Execute a SELECT and return the first row as a dict, or ``None``.

        Parameters
        ----------
        sql:
            SELECT statement.
        params:
            Bind parameters.

        Returns
        -------
        dict[str, Any] or None
        """
        params = params or ()
        with self._pool.acquire() as conn:
            cursor = conn.execute(sql, params)
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Database.execute() auto-commits, so nothing needed here.
        # The context manager exists for ``with db:`` idiom compatibility.
        pass

    def close(self) -> None:
        """Release all pooled connections.  Call on application shutdown."""
        self._pool.close_all()
        log.info("Database closed: %s", self._db_path)

    def __repr__(self) -> str:
        return f"Database(path={self._db_path})"


__all__ = ["Database"]
