from __future__ import annotations

import pandas as pd

from quantify.strategy.volatility_regime import VolatilityRegimeStrategy


def test_resolve_vix_from_series_returns_last_scalar() -> None:
    strat = VolatilityRegimeStrategy()
    vix = pd.Series([12.5, 13.2, 14.8], index=pd.date_range("2025-01-01", periods=3))

    assert strat._resolve_vix(vix) == 14.8


def test_update_regime_state_handles_single_column_vix_frame() -> None:
    strat = VolatilityRegimeStrategy()
    dates = pd.date_range("2025-01-01", periods=5, freq="B")
    vix_frame = pd.DataFrame({"close": [11.0, 12.0, 13.0, 14.0, 14.5]}, index=dates)
    data = {"^VIX": vix_frame}

    strat.generate_signals(data)

    assert strat.current_vix == 14.5
    assert strat.current_regime == "low"