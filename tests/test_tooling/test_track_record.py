"""Tests for scripts/track_record.py: the live record of every published monthly list.

The data branches are force-pushed as a single commit, so before this there was no way to check
whether past picks made money. These tests pin how lists are recorded and scored.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("track_record", SCRIPTS / "track_record.py")
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)


def trend_result(as_of: str, symbols: list[str]) -> dict:
    return {"method": "trend", "as_of": as_of, "signals": [{"symbol": s, "side": "long"} for s in symbols]}


def test_each_monthly_list_is_recorded_once(tmp_path) -> None:
    history = tmp_path / "picks.jsonl"

    assert tr.append(history, trend_result("2026-09-30", ["AMD", "MU"])) is True
    assert tr.append(history, trend_result("2026-09-30", ["AMD", "MU"])) is False  # every cron run, same list
    assert tr.append(history, trend_result("2026-10-30", ["AMD", "SNDK"])) is True

    lines = [json.loads(x) for x in history.read_text().splitlines()]
    assert [x["as_of"] for x in lines] == ["2026-09-30", "2026-10-30"]
    assert lines[1]["symbols"] == ["AMD", "SNDK"]


def test_ml_results_are_not_recorded(tmp_path) -> None:
    history = tmp_path / "picks.jsonl"
    assert tr.append(history, {"method": None, "signals": [{"symbol": "X", "side": "long"}]}) is False
    assert not history.exists()


def test_score_buys_the_close_after_the_list_date_and_compares_with_spy() -> None:
    dates = pd.bdate_range("2026-09-29", periods=30)
    close = pd.DataFrame({
        "AAA": [100.0] * 2 + [110.0] * 28,   # +10% from the first close after 09-30
        "BBB": [50.0] * 2 + [50.0] * 28,     # flat
        "SPY": [400.0] * 2 + [404.0] * 28,   # +1%
    }, index=dates)
    # 09-30 is the list date; 10-01 (dates[2]) is the buy close
    close.loc[dates[2], ["AAA", "BBB", "SPY"]] = [100.0, 50.0, 400.0]
    history = [{"as_of": "2026-09-30", "symbols": ["AAA", "BBB"]}]

    table = tr.score(history, close, cost_bps=0)

    row = table.iloc[0]
    assert row["bought"] == "2026-10-01"
    assert row["picks_return_pct"] == pytest.approx(5.0)   # equal weight: (+10% + 0%) / 2
    assert row["spy_return_pct"] == pytest.approx(1.0)
    assert row["excess_pct"] == pytest.approx(4.0)
    assert bool(row["open"]) is True                        # no later list yet: still being held


def test_a_closed_month_ends_at_the_next_list_purchase() -> None:
    dates = pd.bdate_range("2026-09-28", periods=50)
    close = pd.DataFrame({"AAA": range(100, 150), "SPY": [400.0] * 50}, index=dates, dtype=float)
    history = [{"as_of": "2026-09-30", "symbols": ["AAA"]}, {"as_of": "2026-10-30", "symbols": ["AAA"]}]

    table = tr.score(history, close, cost_bps=0)

    first = table.iloc[0]
    assert first["sold"] == "2026-11-02" and bool(first["open"]) is False
    start, end = close.at[pd.Timestamp("2026-10-01"), "AAA"], close.at[pd.Timestamp("2026-11-02"), "AAA"]
    assert first["picks_return_pct"] == pytest.approx((end / start - 1) * 100)
