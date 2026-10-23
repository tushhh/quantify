# Regression: trend-screen picks carry predicted_return_pct=0.0, so Telegram /top showed
# "Return: +0.00%" for every pick. Rows must show the picks' 6m/12m returns instead.
from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.prediction_bot import _signal_row, _signal_row_named  # noqa: E402
from api.schemas import PredictionItem  # noqa: E402


def trend_pick() -> PredictionItem:
    return PredictionItem(symbol="AMD", name="Advanced Micro Devices", side="long", strength=0.98,
                          predicted_return_pct=4.1, return_6m_pct=200.7, return_12m_pct=279.1,
                          pct_above_ma200=65.1, forecast_beat_spy_pct=54.5, forecast_low_pct=-12.5,
                          forecast_high_pct=22.6)


def test_trend_rows_show_trailing_returns_not_a_zero_prediction() -> None:
    for row in (_signal_row(trend_pick(), 1), _signal_row_named(trend_pick(), 1)):
        assert "+0.00%" not in row
        assert "past 6m +200.7%" in row and "past 12m +279.1%" in row
        assert "next month +4.1% expected, 54.5% chance to beat SPY" in row


def test_ml_rows_are_unchanged() -> None:
    ml = PredictionItem(symbol="MU", name="Micron", side="long", strength=0.5, predicted_return_pct=1.25)
    assert "+1.25%" in _signal_row_named(ml, 1)
