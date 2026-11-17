"""YFinanceProvider: symbols the bulk download drops are retried one by one. No network."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from quantify.data.providers import yfinance_provider as yp


def _bars(n: int = 10) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02", periods=n, freq="B")
    close = np.linspace(100.0, 110.0, n)
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1_000_000},
        index=idx,
    )


def test_symbols_dropped_by_the_bulk_download_are_retried(monkeypatch) -> None:
    # Regression: yfinance's bulk download sometimes drops a symbol ("database is
    # locked" in its own cache); KO and V vanished from cloud backtests that way.
    def fake_download(tickers, **kwargs):
        frames = {t: _bars() for t in tickers if t != "KO"}
        return pd.concat(frames, axis=1)

    class FakeTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, **kwargs):
            return _bars()

    monkeypatch.setattr(yp.yf, "download", fake_download)
    monkeypatch.setattr(yp.yf, "Ticker", FakeTicker)

    provider = yp.YFinanceProvider(cache=None, rate_limit_pause=0.0)
    result = provider.get_multiple(["AAPL", "KO", "MSFT"], datetime(2024, 1, 1), datetime(2024, 2, 1))

    assert set(result) == {"AAPL", "KO", "MSFT"}
    assert not result["KO"].empty
