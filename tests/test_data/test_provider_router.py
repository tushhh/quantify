from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from quantify.data.models import TimeFrame
from quantify.data.provider_router import ProviderBoundaryError, fetch_market_data
from quantify.data.providers.base import DataProvider, DataProviderError


class _StubProvider(DataProvider):
    def __init__(self, frames: dict[str, pd.DataFrame], fail_symbols: set[str] | None = None):
        self.frames = frames
        self.fail_symbols = fail_symbols or set()

    def get_bars(self, symbol, start, end, timeframe=TimeFrame.DAILY):
        if symbol in self.fail_symbols:
            raise DataProviderError(f"failed {symbol}")
        return self.frames.get(symbol, pd.DataFrame())

    def get_multiple(self, symbols, start, end, timeframe=TimeFrame.DAILY):
        return {s: self.get_bars(s, start, end, timeframe) for s in symbols if s not in self.fail_symbols}


def _frame(rows: int) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [1.0] * rows,
            "high": [1.0] * rows,
            "low": [1.0] * rows,
            "close": [1.0] * rows,
            "volume": [100] * rows,
        },
        index=idx,
    )


def test_fetch_market_data_returns_metadata_and_filters_short_frames() -> None:
    provider = _StubProvider({"AAPL": _frame(10), "MSFT": _frame(3)})
    result = fetch_market_data(
        provider,
        ["AAPL", "MSFT"],
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 2, 1, tzinfo=timezone.utc),
        min_bars=5,
    )

    assert set(result.data) == {"AAPL"}
    assert "MSFT" in result.failed_symbols
    assert result.to_metadata()["provider"] == "_StubProvider"


def test_fetch_market_data_raises_with_failure_metadata_when_empty() -> None:
    provider = _StubProvider({}, fail_symbols={"AAPL"})
    with pytest.raises(ProviderBoundaryError) as exc_info:
        fetch_market_data(
            provider,
            ["AAPL"],
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 2, 1, tzinfo=timezone.utc),
            min_bars=1,
        )

    assert "AAPL" in exc_info.value.metadata["failed_symbols"]
