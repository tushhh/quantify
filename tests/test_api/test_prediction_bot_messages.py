# Regression: the Telegram full scan announced trend picks as a "Full 500-Stock Scan" of
# "100 stocks", with an empty "Top Shorts" section and no list date.
from __future__ import annotations

import os

os.environ.setdefault("JWT_SECRET", "test-secret")

from api.prediction_bot import _scan_text  # noqa: E402
from api.schemas import PredictionItem, PredictionResponse  # noqa: E402
from quantify.trend_screen import BACKTEST  # noqa: E402


def trend_result() -> PredictionResponse:
    picks = [PredictionItem(symbol=s, name=s, side="long", strength=1.0, return_6m_pct=100.0, return_12m_pct=200.0)
             for s in ("MU", "SNDK", "AMD")]
    return PredictionResponse(method="trend", date="2026-10-23", as_of="2026-09-30", next_refresh="2026-11-01",
                              universe_size=100, signals=picks, backtest=BACKTEST)


def test_trend_scan_message_is_long_only_and_dated() -> None:
    text = _scan_text(trend_result(), n=8, title="Full 500-Stock Scan Complete")

    assert "500-Stock" not in text and "Short" not in text
    assert "2026-09-30" in text and "2026-11-01" in text
    assert "100 most-traded" in text
    assert text.index("MU") < text.index("SNDK") < text.index("AMD")


def test_ml_scan_message_keeps_both_sides() -> None:
    ml = PredictionResponse(date="2026-10-20", universe_size=500, signals=[
        PredictionItem(symbol="AAA", side="long", strength=0.5, predicted_return_pct=1.0),
        PredictionItem(symbol="BBB", side="short", strength=-0.5, predicted_return_pct=-1.0),
    ])

    text = _scan_text(ml, n=8, title="Full 500-Stock Scan Complete")

    assert "Full 500-Stock Scan Complete" in text and "Top Shorts" in text and "BBB" in text
