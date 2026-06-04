"""
quantify.persistence.state
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Strategy state persistence backed by SQLite.

The :class:`StateManager` provides a key-value store for arbitrary strategy
state dictionaries.  State is JSON-serialised, with special handling for
Python :class:`datetime` objects so that strategies can store timestamps
without manual conversion.

The ``strategy_state`` table uses ``strategy_name`` as a primary key, so
calling :meth:`save_state` is always an upsert — subsequent saves overwrite
the previous state.

Typical usage
-------------
::

    db = Database()
    db.initialize()
    state_mgr = StateManager(db)

    # Save state at end of day
    state_mgr.save_state("pairs_mean_reversion", {
        "last_rebalance": datetime.now(UTC),
        "open_pairs": [("AAPL", "MSFT")],
        "zscore": 2.1,
    })

    # Restore on next startup
    state = state_mgr.load_state("pairs_mean_reversion")
    if state:
        last_rebalance = datetime.fromisoformat(state["last_rebalance"])
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from quantify.persistence.database import Database

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON codec with datetime support
# ---------------------------------------------------------------------------


class _DatetimeEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles :class:`datetime` and :class:`date`
    objects by converting them to ISO-8601 strings tagged with a type marker.

    Encoded datetimes: ``{"__datetime__": "2024-01-15T09:30:00+00:00"}``
    Encoded dates:     ``{"__date__": "2024-01-15"}``
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return {"__datetime__": obj.isoformat()}
        if isinstance(obj, date):
            return {"__date__": obj.isoformat()}
        # Let the base class raise TypeError for truly unsupported types
        return super().default(obj)


def _datetime_decoder(dct: dict[str, Any]) -> Any:
    """
    JSON object hook for decoding tagged datetime/date values produced by
    :class:`_DatetimeEncoder`.
    """
    if "__datetime__" in dct:
        return datetime.fromisoformat(dct["__datetime__"])
    if "__date__" in dct:
        return date.fromisoformat(dct["__date__"])
    return dct


def _serialize_state(state: dict[str, Any]) -> str:
    """
    Serialize a state dictionary to a JSON string with datetime support.

    Parameters
    ----------
    state:
        Arbitrary state dictionary.  Values must be JSON-serialisable or
        :class:`datetime`/:class:`date` instances.

    Returns
    -------
    str
        JSON string representation.

    Raises
    ------
    TypeError
        If any value cannot be serialised.
    """
    return json.dumps(state, cls=_DatetimeEncoder, ensure_ascii=False)


def _deserialize_state(json_str: str) -> dict[str, Any]:
    """
    Deserialize a JSON string back to a state dictionary, restoring
    datetime objects from their tagged representations.

    Parameters
    ----------
    json_str:
        JSON string produced by :func:`_serialize_state`.

    Returns
    -------
    dict[str, Any]
    """
    return json.loads(json_str, object_hook=_datetime_decoder)


# ---------------------------------------------------------------------------
# StateManager
# ---------------------------------------------------------------------------


class StateManager:
    """
    Strategy state persistence manager.

    Provides load/save/clear operations for per-strategy state dictionaries,
    backed by the ``strategy_state`` table in SQLite.

    Parameters
    ----------
    db:
        An initialised :class:`~quantify.persistence.database.Database`
        instance.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_state(self, strategy_name: str, state: dict[str, Any]) -> None:
        """
        Persist strategy state as a JSON blob (upsert).

        If a row for *strategy_name* already exists, it is replaced.
        Datetime and date values in *state* are serialised automatically.

        Parameters
        ----------
        strategy_name:
            Unique identifier for the strategy.
        state:
            Arbitrary JSON-serialisable dictionary.  May contain
            :class:`datetime` and :class:`date` objects.

        Raises
        ------
        TypeError
            If *state* contains values that cannot be serialised.
        """
        if not strategy_name:
            raise ValueError("strategy_name must not be empty")
        if not isinstance(state, dict):
            raise TypeError(f"state must be a dict, got {type(state).__name__}")

        try:
            state_json = _serialize_state(state)
        except (TypeError, ValueError) as exc:
            log.error("StateManager.save_state: serialisation failed for %s: %s", strategy_name, exc)
            raise

        now_iso = datetime.now(tz=timezone.utc).isoformat()
        sql = """
            INSERT INTO strategy_state (strategy_name, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(strategy_name) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
        """
        self._db.execute(sql, (strategy_name, state_json, now_iso))
        log.debug("StateManager.save_state: saved state for '%s' (%d bytes)", strategy_name, len(state_json))

    def load_state(self, strategy_name: str) -> Optional[dict[str, Any]]:
        """
        Load persisted state for a strategy.

        Parameters
        ----------
        strategy_name:
            Strategy identifier.

        Returns
        -------
        dict[str, Any] or None
            The deserialized state dictionary, or ``None`` if no state has
            been saved for this strategy.
        """
        row = self._db.fetchone(
            "SELECT state_json, updated_at FROM strategy_state WHERE strategy_name = ?",
            (strategy_name,),
        )
        if row is None:
            log.debug("StateManager.load_state: no state found for '%s'", strategy_name)
            return None

        try:
            state = _deserialize_state(row["state_json"])
        except (json.JSONDecodeError, ValueError) as exc:
            log.error(
                "StateManager.load_state: deserialisation failed for '%s': %s",
                strategy_name, exc,
            )
            return None

        log.debug(
            "StateManager.load_state: loaded state for '%s' (updated_at=%s)",
            strategy_name, row["updated_at"],
        )
        return state

    def clear_state(self, strategy_name: str) -> bool:
        """
        Delete persisted state for a strategy.

        Parameters
        ----------
        strategy_name:
            Strategy identifier.

        Returns
        -------
        bool
            ``True`` if a row was deleted, ``False`` if no row existed.
        """
        cursor = self._db.execute(
            "DELETE FROM strategy_state WHERE strategy_name = ?",
            (strategy_name,),
        )
        deleted = cursor.rowcount > 0
        if deleted:
            log.info("StateManager.clear_state: cleared state for '%s'", strategy_name)
        else:
            log.debug("StateManager.clear_state: no state to clear for '%s'", strategy_name)
        return deleted

    def list_strategies(self) -> list[str]:
        """
        Return the names of all strategies that have saved state.

        Returns
        -------
        list[str]
            Strategy names in alphabetical order.
        """
        rows = self._db.fetchall(
            "SELECT strategy_name FROM strategy_state ORDER BY strategy_name ASC"
        )
        return [r["strategy_name"] for r in rows]

    def get_state_metadata(self, strategy_name: str) -> Optional[dict[str, Any]]:
        """
        Return metadata (strategy name, updated_at) without deserializing state.

        Parameters
        ----------
        strategy_name:
            Strategy identifier.

        Returns
        -------
        dict[str, Any] or None
            Keys: ``strategy_name``, ``updated_at``, ``state_size_bytes``.
        """
        row = self._db.fetchone(
            "SELECT strategy_name, updated_at, LENGTH(state_json) AS size "
            "FROM strategy_state WHERE strategy_name = ?",
            (strategy_name,),
        )
        if row is None:
            return None
        return {
            "strategy_name": row["strategy_name"],
            "updated_at": row["updated_at"],
            "state_size_bytes": row["size"],
        }

    def clear_all(self) -> int:
        """
        Delete all strategy state rows.

        Returns
        -------
        int
            Number of rows deleted.
        """
        cursor = self._db.execute("DELETE FROM strategy_state")
        count = cursor.rowcount
        log.warning("StateManager.clear_all: deleted %d state rows", count)
        return count

    def __repr__(self) -> str:
        return f"StateManager(db={self._db!r})"


__all__ = ["StateManager"]
