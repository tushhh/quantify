from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from quantify.data.models import TimeFrame
from quantify.data.providers.base import DataProvider, DataProviderError


class ProviderBoundaryError(RuntimeError):
    """Raised when no usable data can be fetched through the provider boundary."""

    def __init__(self, message: str, metadata: dict[str, Any] | None = None):
        super().__init__(message)
        self.metadata = metadata or {}


@dataclass
class ProviderFetchResult:
    provider_name: str
    data: dict[str, pd.DataFrame]
    requested_symbols: list[str]
    returned_symbols: list[str]
    failed_symbols: dict[str, str] = field(default_factory=dict)
    min_bars: int = 0

    def to_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "requested_symbols": self.requested_symbols,
            "returned_symbols": self.returned_symbols,
            "failed_symbols": self.failed_symbols,
            "min_bars": self.min_bars,
        }


def fetch_market_data(
    provider: DataProvider,
    symbols: list[str],
    start: datetime,
    end: datetime,
    timeframe: TimeFrame = TimeFrame.DAILY,
    min_bars: int = 1,
) -> ProviderFetchResult:
    requested_symbols = [s.upper() for s in symbols]
    failed_symbols: dict[str, str] = {}

    try:
        raw = provider.get_multiple(requested_symbols, start, end, timeframe=timeframe)
    except DataProviderError as exc:
        raw = {}
        failed_symbols["__bulk__"] = str(exc)
    except Exception as exc:  # pragma: no cover - safety net
        raw = {}
        failed_symbols["__bulk__"] = f"unexpected provider error: {exc}"

    # If bulk fetch failed or omitted symbols, try symbol-level calls so callers
    # get useful failure metadata instead of a silent drop.
    for sym in requested_symbols:
        if sym in raw:
            continue
        try:
            single = provider.get_bars(sym, start, end, timeframe=timeframe)
            raw[sym] = single
        except Exception as exc:
            failed_symbols[sym] = str(exc)

    filtered: dict[str, pd.DataFrame] = {}
    for sym in requested_symbols:
        df = raw.get(sym)
        if df is None or df.empty:
            failed_symbols.setdefault(sym, "no data returned")
            continue
        if min_bars > 0 and len(df) < min_bars:
            failed_symbols.setdefault(sym, f"insufficient bars ({len(df)} < {min_bars})")
            continue
        filtered[sym] = df

    result = ProviderFetchResult(
        provider_name=type(provider).__name__,
        data=filtered,
        requested_symbols=requested_symbols,
        returned_symbols=sorted(filtered.keys()),
        failed_symbols=failed_symbols,
        min_bars=min_bars,
    )

    if not filtered:
        raise ProviderBoundaryError(
            "No valid market data was retrieved for any symbols.",
            metadata=result.to_metadata(),
        )

    return result
