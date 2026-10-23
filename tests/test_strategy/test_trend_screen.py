"""Tests for the trend screen, the stock picker behind /predict.

The screen was chosen on a walk-forward backtest (2021-2026, point-in-time liquid universe,
monthly rebalance, after costs). These tests pin down the properties that backtest assumed,
so the production picker can't drift away from what was tested.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from api.schemas import PredictionResponse
from quantify.trend_screen import monthly_anchor, run_trend_screen, score_trend, select_picks

DAYS = pd.bdate_range("2024-01-02", periods=420)


def make_panel(drifts: dict[str, float], volumes: dict[str, float] | None = None, seed: int = 0):
    """Price paths with a given daily drift per symbol, small noise, constant volume."""
    rng = np.random.default_rng(seed)
    close = {}
    for sym, drift in drifts.items():
        steps = drift + rng.normal(0, 0.002, len(DAYS))
        close[sym] = 100 * np.exp(np.cumsum(steps))
    close = pd.DataFrame(close, index=DAYS)
    vols = volumes or {}
    volume = pd.DataFrame({s: vols.get(s, 1e6) for s in drifts}, index=DAYS)
    return close, volume


def test_picks_the_strongest_trends_and_skips_names_below_their_200_day_average() -> None:
    drifts = {f"UP{i}": 0.0005 + i * 0.0002 for i in range(6)}
    drifts.update({f"DN{i}": -0.0010 - i * 0.0002 for i in range(6)})
    close, volume = make_panel(drifts)

    table = score_trend(close, volume, as_of=DAYS[-1], liquid_top=100)
    picks = table.nlargest(3, "score").index.tolist()

    assert set(picks) == {"UP5", "UP4", "UP3"}
    assert (table.loc[[f"DN{i}" for i in range(6)], "above_ma200"] == False).all()  # noqa: E712
    assert table.loc["DN0", "score"] < table.loc["UP0", "score"]


def test_only_the_most_traded_names_are_eligible() -> None:
    drifts = {"BIG": 0.0006, "MID": 0.0007, "TINY": 0.0030}  # TINY has the best trend
    volumes = {"BIG": 5e7, "MID": 2e7, "TINY": 1e3}
    close, volume = make_panel(drifts, volumes)

    table = score_trend(close, volume, as_of=DAYS[-1], liquid_top=2)

    assert table.loc["TINY", "liquid"] == False  # noqa: E712
    assert np.isnan(table.loc["TINY", "score"])
    assert set(table["score"].dropna().index) == {"BIG", "MID"}


def test_one_pick_per_company_across_share_classes() -> None:
    scores = pd.Series({"GOOGL": 0.9, "GOOG": 0.89, "MU": 0.8})
    names = {"GOOGL": "Alphabet Inc. (Class A)", "GOOG": "Alphabet Inc. (Class C)", "MU": "Micron Technology"}

    assert select_picks(scores, {}, n=2, names=names) == ["GOOGL", "MU"]


def test_optional_sector_cap() -> None:
    """Off in production (the user chose uncapped in Oct 2026); kept so pick-backtest can compare."""
    scores = pd.Series({f"T{i}": 1.0 - i * 0.01 for i in range(10)} | {"E1": 0.5, "E2": 0.4, "H1": 0.3})
    sectors = {f"T{i}": "Information Technology" for i in range(10)} | {"E1": "Energy", "E2": "Energy", "H1": "Health Care"}

    picks = select_picks(scores, sectors, n=6, max_per_sector=3)

    assert picks == ["T0", "T1", "T2", "E1", "E2", "H1"]


def test_scores_use_no_future_data() -> None:
    close, volume = make_panel({f"S{i}": 0.0002 * i for i in range(8)})
    as_of = DAYS[350]

    full = score_trend(close, volume, as_of=as_of)
    truncated = score_trend(close.loc[:as_of], volume.loc[:as_of], as_of=as_of)

    pd.testing.assert_series_equal(full["score"], truncated["score"])


def test_list_is_fixed_for_the_month() -> None:
    """Picks come from the last close of the previous month, as in the monthly backtest."""
    dates = pd.bdate_range("2026-09-01", "2026-10-22")
    assert monthly_anchor(dates) == pd.Timestamp("2026-09-30")
    assert monthly_anchor(dates[dates <= "2026-10-01"]) == pd.Timestamp("2026-09-30")


def test_screen_output_matches_the_prediction_api_and_is_long_only() -> None:
    drifts = {f"S{i}": 0.0001 * i - 0.0003 for i in range(30)}
    close, volume = make_panel(drifts)
    sectors = {s: f"Sector {i % 5}" for i, s in enumerate(drifts)}
    names = {s: f"{s} Corp" for s in drifts}

    result = run_trend_screen(close, volume, sectors=sectors, names=names, n_picks=5, liquid_top=100)

    response = PredictionResponse(**result)  # the API's own schema must accept it
    assert response.method == "trend"
    assert len(response.signals) == 5
    assert {s.side for s in response.signals} == {"long"}
    top = response.signals[0]
    assert top.symbol == "S29" and top.name == "S29 Corp"
    assert top.return_6m_pct is not None and top.return_6m_pct > 0
    assert top.pct_above_ma200 is not None and top.pct_above_ma200 > 0
    assert response.as_of == str(monthly_anchor(close.index).date())
    assert response.backtest is not None and "excess_cagr_pct" in response.backtest


def test_screen_needs_a_year_of_history() -> None:
    close, volume = make_panel({"A": 0.001, "B": 0.0005})
    with pytest.raises(ValueError, match="history"):
        run_trend_screen(close.iloc[-100:], volume.iloc[-100:], sectors={}, names={})
