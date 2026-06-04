from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger("quantify.api.market_data")


def fetch_latest_prices(symbols: List[str]) -> Dict[str, Optional[float]]:
    """Fetch latest close prices for a list of symbols via yfinance (sync)."""
    result: Dict[str, Optional[float]] = {s: None for s in symbols}
    if not symbols:
        return result
    try:
        import yfinance as yf
        import pandas as pd

        tickers = " ".join(symbols)
        raw = yf.download(
            tickers,
            period="5d",
            auto_adjust=True,
            progress=False,
            group_by="ticker" if len(symbols) > 1 else "column",
            threads=True,
        )
        if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
            return result

        def _get_close(df: pd.DataFrame) -> Optional[float]:
            """Extract the latest close price from a DataFrame, case-insensitively."""
            col_map = {c.lower(): c for c in df.columns}
            col = col_map.get("close")
            if col is None:
                return None
            series = df[col].dropna()
            return round(float(series.iloc[-1]), 4) if not series.empty else None

        if len(symbols) == 1:
            result[symbols[0]] = _get_close(raw)
        else:
            for sym in symbols:
                try:
                    result[sym] = _get_close(raw[sym])
                except Exception:
                    pass
    except Exception as exc:
        log.warning("Price fetch failed: %s", exc)
    return result
