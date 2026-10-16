"""
Provider boundary for market data.

:func:`fetch_market_data` wraps a :class:`DataProvider` so callers get the
usable frames *and* a record of which symbols were skipped and why, instead
of symbols silently disappearing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from quantify.data.models import TimeFrame
from quantify.data.providers.base import DataProvider

log = logging.getLogger(__name__)


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
    """Fetch *symbols* through *provider*, recording every symbol that is skipped.

    Symbols the provider omits are reported as failed, not re-requested:
    providers already retry internally (``YFinanceProvider.get_multiple``
    falls back to per-symbol downloads), and a second pass only doubles
    traffic when the provider is rate-limited.
    """
    requested_symbols = list(dict.fromkeys(s.upper() for s in symbols))
    failed_symbols: dict[str, str] = {}

    try:
        raw = provider.get_multiple(requested_symbols, start, end, timeframe=timeframe)
    except Exception as exc:
        # The bulk call failed outright (YFinanceProvider raises when the only
        # uncached symbol errors). Fetch individually so cached or healthy
        # symbols still come through.
        log.warning("Bulk fetch failed (%s); fetching %d symbols individually.",
                    exc, len(requested_symbols))
        raw = {}
        for sym in requested_symbols:
            try:
                raw[sym] = provider.get_bars(sym, start, end, timeframe=timeframe)
            except Exception as sym_exc:
                failed_symbols[sym] = str(sym_exc)

    filtered: dict[str, pd.DataFrame] = {}
    for sym in requested_symbols:
        df = raw.get(sym)
        if df is None or df.empty:
            failed_symbols.setdefault(sym, "no data returned")
            continue
        if min_bars > 0 and len(df) < min_bars:
            failed_symbols[sym] = f"insufficient bars ({len(df)} < {min_bars})"
            continue
        filtered[sym] = df

    result = ProviderFetchResult(
        provider_name=type(provider).__name__,
        data=filtered,
        requested_symbols=requested_symbols,
        returned_symbols=sorted(filtered),
        failed_symbols=failed_symbols,
        min_bars=min_bars,
    )

    if failed_symbols:
        log.warning("Skipped %d of %d symbols: %s",
                    len(failed_symbols), len(requested_symbols), failed_symbols)

    if not filtered:
        raise ProviderBoundaryError(
            "No valid market data was retrieved for any symbols.",
            metadata=result.to_metadata(),
        )

    return result
