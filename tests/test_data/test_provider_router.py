from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from quantify.data.models import TimeFrame
from quantify.data.provider_router import ProviderBoundaryError, fetch_market_data
from quantify.data.providers.base import DataProvider, DataProviderError


class _StubProvider(DataProvider):
    def __init__(
        self,
        frames: dict[str, pd.DataFrame],
        fail_symbols: set[str] | None = None,
        bulk_error: Exception | None = None,
    ):
        self.frames = frames
        self.fail_symbols = fail_symbols or set()
        self.bulk_error = bulk_error
        self.bars_calls: list[str] = []

    def get_bars(self, symbol, start, end, timeframe=TimeFrame.DAILY):
        self.bars_calls.append(symbol)
        return self._bars(symbol)

    def get_multiple(self, symbols, start, end, timeframe=TimeFrame.DAILY):
        if self.bulk_error is not None:
            raise self.bulk_error
        # Like YFinanceProvider: symbols that fail or return nothing are omitted.
        return {s: self._bars(s) for s in symbols if s not in self.fail_symbols}

    def _bars(self, symbol):
        if symbol in self.fail_symbols:
            raise DataProviderError(f"failed {symbol}")
        return self.frames.get(symbol, pd.DataFrame())


_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
_END = datetime(2024, 2, 1, tzinfo=timezone.utc)


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


def test_fetch_market_data_does_not_refetch_symbols_the_provider_omitted() -> None:
    # Regression: re-requesting omitted symbols doubled traffic while Yahoo
    # was rate-limiting, because YFinanceProvider already retries them.
    provider = _StubProvider({"AAPL": _frame(10)}, fail_symbols={"BADX"})
    result = fetch_market_data(provider, ["AAPL", "BADX", "NODATA"], _START, _END)

    assert provider.bars_calls == []
    assert set(result.data) == {"AAPL"}
    assert result.failed_symbols == {"BADX": "no data returned", "NODATA": "no data returned"}


def test_fetch_market_data_falls_back_per_symbol_when_bulk_call_raises() -> None:
    provider = _StubProvider(
        {"AAPL": _frame(10)},
        fail_symbols={"BADX"},
        bulk_error=DataProviderError("bulk down"),
    )
    result = fetch_market_data(provider, ["aapl", "BADX"], _START, _END)

    assert provider.bars_calls == ["AAPL", "BADX"]
    assert set(result.data) == {"AAPL"}
    assert result.failed_symbols == {"BADX": "failed BADX"}
