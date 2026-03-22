"""
quantify.strategy.quality_value
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Multi-Factor Quality + Value strategy.

Academic basis
--------------
Fama, E. F., & French, K. R. (2015). "A five-factor asset pricing model."
Journal of Financial Economics, 116(1), 1–22.
  - HML (High-Minus-Low): book-to-market value factor
  - RMW (Robust-Minus-Weak): profitability (quality) factor
  - CMA (Conservative-Minus-Aggressive): investment factor

Novy-Marx, R. (2013). "The other side of value: The gross profitability premium."
Journal of Financial Economics, 108(1), 1–28.
  - Gross profitability (GP/A) as a quality measure

The quality-value combination is documented by Asness, Frazzini & Pedersen
(2019) "Quality Minus Junk" — high-quality, cheap stocks consistently
outperform.

Implementation
--------------
Value factors (from yfinance .info):
  1. Earnings yield     = trailingEPS / price
  2. Book/market        = bookValue per share / price
  3. FCF yield          = freeCashflow / market cap

Quality factors (from yfinance .info):
  4. Gross profitability = grossProfits / totalAssets
  5. Return on equity    = returnOnEquity

For each factor:
  - Z-score cross-sectionally: (x − mean) / std
  - NaN values are handled by computing mean/std over non-NaN observations

Composite score:
  - Simple average of all factor z-scores (using np.nanmean per stock)
  - Long top quintile (top 20%), strength proportional to composite score

Caching:
  - Fundamental data is fetched via yfinance and cached for 30 days
  - Cache key is the symbol; cache stores (fetch_timestamp, info_dict)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

from quantify.data.universe import get_sp500
from quantify.strategy.base import Strategy
from quantify.strategy.signal import Signal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_CACHE_TTL_DAYS: int = 30
_MIN_STOCKS_FOR_ZSCORE: int = 10
_LONG_QUINTILE: float = 0.80   # top 20%
_SHORT_QUINTILE: float = 0.20  # bottom 20% (optional — disabled by default)
_REBALANCE_DAYS: int = 21

# yfinance field → our factor name mapping
_VALUE_FIELDS: dict[str, str] = {
    "trailingEPS": "earnings_yield_raw",    # will be divided by price
    "bookValue": "book_market_raw",          # book value per share → B/M ratio
    "freeCashflow": "fcf_yield_raw",         # fcf / market cap
}
_QUALITY_FIELDS: dict[str, str] = {
    "grossProfits": "gross_profitability_raw",  # needs totalAssets
    "totalAssets": "total_assets_raw",
    "returnOnEquity": "roe",
}
_MARKET_FIELDS: dict[str, str] = {
    "marketCap": "market_cap",
    "currentPrice": "current_price",
}


class QualityValueStrategy(Strategy):
    """
    Multi-Factor Quality + Value strategy.

    Fetches fundamental data from yfinance, z-scores each factor cross-
    sectionally, averages z-scores into a composite, and goes long stocks
    in the top quintile.

    Parameters
    ----------
    universe:
        List of ticker symbols.  Defaults to the top-100 S&P 500 list.
    long_quintile:
        Percentile cut-off for longs (default 0.80 → top 20%).
    short_quintile:
        Percentile cut-off for shorts (default 0.20 → bottom 20%).
        Set to None to disable shorting.
    cache_ttl_days:
        How many days before fundamental data is re-fetched (default 30).
    rebalance_days:
        Minimum trading days between rebalances (default 21).
    enable_short:
        Whether to short the bottom quintile (default False).
    """

    name: str = "quality_value"
    rebalance_frequency: str = "monthly"
    lookback_days: int = 30  # Only needs recent data; fundamentals from yfinance

    def __init__(
        self,
        universe: Optional[list[str]] = None,
        long_quintile: float = _LONG_QUINTILE,
        short_quintile: float = _SHORT_QUINTILE,
        cache_ttl_days: int = _CACHE_TTL_DAYS,
        rebalance_days: int = _REBALANCE_DAYS,
        enable_short: bool = False,
    ) -> None:
        self.universe: list[str] = universe if universe is not None else get_sp500()
        self.long_quintile = long_quintile
        self.short_quintile = short_quintile
        self.cache_ttl_days = cache_ttl_days
        self.rebalance_days = rebalance_days
        self.enable_short = enable_short

        # Fundamental data cache: {symbol: (unix_timestamp, info_dict)}
        self._fund_cache: dict[str, tuple[float, dict[str, Any]]] = {}

        # Rebalance state
        self._last_rebalance: Optional[datetime] = None
        self._signal_cache: list[Signal] = []

        log.info(
            "QualityValueStrategy initialised: %d symbols, "
            "long_quintile=%.0f%%, enable_short=%s",
            len(self.universe),
            long_quintile * 100,
            enable_short,
        )

    def get_required_features(self) -> list[str]:
        """
        No price-based features required — fundamental data is fetched
        directly from yfinance.
        """
        return []

    def generate_signals(self, data: dict[str, pd.DataFrame]) -> list[Signal]:
        """
        Compute composite quality-value scores and emit long signals for
        the top quintile.

        Parameters
        ----------
        data:
            ``{symbol: DataFrame}`` with OHLCV data.  Close prices are used
            to compute value ratios (earnings yield, B/M, FCF yield) against
            the most recent price.

        Returns
        -------
        list[Signal]
        """
        if not data:
            log.warning("%s: empty data dict", self.name)
            return []

        timestamp = self._latest_timestamp(data)

        # ---- Rebalance gate ----
        if not self._should_rebalance(timestamp):
            log.debug(
                "%s: no rebalance at %s", self.name, timestamp.date()
            )
            return list(self._signal_cache)

        log.info("%s: rebalancing at %s", self.name, timestamp.date())

        # ---- Get current prices from price data ----
        current_prices = self._extract_prices(data)

        if not current_prices:
            log.warning("%s: no valid prices available", self.name)
            return []

        # ---- Fetch fundamental data (with caching) ----
        fundamentals = self._fetch_all_fundamentals(list(current_prices.keys()))

        if len(fundamentals) < _MIN_STOCKS_FOR_ZSCORE:
            log.warning(
                "%s: only %d stocks with fundamental data (need %d)",
                self.name, len(fundamentals), _MIN_STOCKS_FOR_ZSCORE,
            )
            return []

        # ---- Compute factor scores ----
        factor_df = self._compute_factors(fundamentals, current_prices)

        if factor_df.empty:
            log.warning("%s: factor DataFrame is empty after computation", self.name)
            return []

        # ---- Z-score each factor cross-sectionally ----
        z_df = self._zscore_factors(factor_df)

        # ---- Composite score = mean of z-scores ----
        z_df["composite"] = z_df.apply(
            lambda row: float(np.nanmean(row.values)), axis=1
        )

        # ---- Rank and generate signals ----
        signals = self._rank_and_signal(z_df, timestamp)

        self._signal_cache = signals
        self._last_rebalance = timestamp

        log.info(
            "%s: generated %d signals (%d long, %d short, %d close)",
            self.name,
            len(signals),
            sum(1 for s in signals if s.direction == "long"),
            sum(1 for s in signals if s.direction == "short"),
            sum(1 for s in signals if s.direction == "close"),
        )
        return signals

    # ------------------------------------------------------------------
    # Fundamental data fetching
    # ------------------------------------------------------------------

    def _fetch_all_fundamentals(
        self, symbols: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Fetch fundamental data for all symbols, using cache when valid.
        """
        result: dict[str, dict[str, Any]] = {}
        now_ts = time.time()
        ttl_seconds = self.cache_ttl_days * 86_400

        for symbol in symbols:
            cached = self._fund_cache.get(symbol)
            if cached is not None:
                cached_ts, cached_info = cached
                if (now_ts - cached_ts) < ttl_seconds:
                    result[symbol] = cached_info
                    continue

            info = self._fetch_yfinance_info(symbol)
            if info:
                self._fund_cache[symbol] = (now_ts, info)
                result[symbol] = info
            else:
                log.debug("%s: no fundamental data for %s", self.name, symbol)

        log.debug(
            "%s: fetched fundamentals for %d/%d symbols",
            self.name, len(result), len(symbols),
        )
        return result

    @staticmethod
    def _fetch_yfinance_info(symbol: str) -> Optional[dict[str, Any]]:
        """
        Fetch .info dict from yfinance for a single symbol.
        Returns None on failure.
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if not info or info.get("regularMarketPrice") is None:
                return None
            return info
        except Exception as exc:
            log.debug("yfinance fetch failed for %s: %s", symbol, exc)
            return None

    # ------------------------------------------------------------------
    # Factor computation
    # ------------------------------------------------------------------

    def _compute_factors(
        self,
        fundamentals: dict[str, dict[str, Any]],
        prices: dict[str, float],
    ) -> pd.DataFrame:
        """
        Compute raw factor values for each symbol.

        Returns a DataFrame with columns:
            earnings_yield, book_market, fcf_yield,
            gross_profitability, roe
        """
        rows: list[dict[str, Any]] = []

        for symbol, info in fundamentals.items():
            price = prices.get(symbol)
            if price is None or price <= 0:
                # Use info price as fallback
                price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price is None or price <= 0:
                continue

            market_cap = info.get("marketCap")
            row: dict[str, Any] = {"symbol": symbol}

            # ---- Value Factors ----
            # 1. Earnings yield = EPS / Price
            eps = info.get("trailingEps") or info.get("trailingEPS")
            row["earnings_yield"] = float(eps) / price if eps is not None else np.nan

            # 2. Book/market = book value per share / price
            book_val = info.get("bookValue")
            row["book_market"] = float(book_val) / price if book_val is not None else np.nan

            # 3. FCF yield = free cash flow / market cap
            fcf = info.get("freeCashflow")
            if fcf is not None and market_cap and market_cap > 0:
                row["fcf_yield"] = float(fcf) / float(market_cap)
            else:
                row["fcf_yield"] = np.nan

            # ---- Quality Factors ----
            # 4. Gross profitability = gross profits / total assets (Novy-Marx)
            gross_profits = info.get("grossProfits")
            total_assets = info.get("totalAssets")
            if gross_profits is not None and total_assets and total_assets > 0:
                row["gross_profitability"] = float(gross_profits) / float(total_assets)
            else:
                row["gross_profitability"] = np.nan

            # 5. Return on equity
            roe = info.get("returnOnEquity")
            row["roe"] = float(roe) if roe is not None else np.nan

            rows.append(row)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).set_index("symbol")
        factor_cols = ["earnings_yield", "book_market", "fcf_yield",
                       "gross_profitability", "roe"]
        return df[factor_cols]

    @staticmethod
    def _zscore_factors(factor_df: pd.DataFrame) -> pd.DataFrame:
        """
        Z-score each factor column cross-sectionally.

        Uses only non-NaN values for mean/std to avoid bias from missing data.
        Returns a DataFrame of z-scores with the same index and columns.
        """
        z_df = pd.DataFrame(index=factor_df.index)
        for col in factor_df.columns:
            series = factor_df[col]
            valid = series.dropna()
            if len(valid) < 3:
                z_df[col] = np.nan
                continue
            mu = valid.mean()
            sigma = valid.std(ddof=1)
            if sigma < 1e-10:
                z_df[col] = 0.0
            else:
                z_df[col] = (series - mu) / sigma
        return z_df

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------

    def _rank_and_signal(
        self,
        z_df: pd.DataFrame,
        timestamp: datetime,
    ) -> list[Signal]:
        """
        Rank stocks by composite z-score and emit signals.
        """
        composite = z_df["composite"].dropna()
        if composite.empty:
            return []

        pct_ranks = composite.rank(pct=True)
        signals: list[Signal] = []

        # Min/max composite for normalising strength
        c_min = composite.min()
        c_max = composite.max()
        c_range = c_max - c_min if c_max > c_min else 1.0

        for symbol, pct_rank in pct_ranks.items():
            comp_score = composite[symbol]

            if pct_rank >= self.long_quintile:
                direction = "long"
                # Normalise composite to [0, 1]
                strength = float(np.clip((comp_score - c_min) / c_range, 0.0, 1.0))

            elif self.enable_short and pct_rank <= self.short_quintile:
                direction = "short"
                strength = float(np.clip(-((c_max - comp_score) / c_range), -1.0, 0.0))

            else:
                direction = "close"
                strength = 0.0

            # Build factor metadata
            meta: dict[str, Any] = {
                "composite_zscore": round(float(comp_score), 4),
                "percentile_rank": round(float(pct_rank), 4),
            }
            for col in z_df.columns:
                if col != "composite" and symbol in z_df.index:
                    val = z_df.loc[symbol, col]
                    meta[f"z_{col}"] = round(float(val), 4) if not np.isnan(val) else None

            signals.append(
                Signal(
                    strategy_name=self.name,
                    symbol=symbol,
                    direction=direction,  # type: ignore[arg-type]
                    strength=strength,
                    timestamp=timestamp,
                    metadata=meta,
                )
            )

        return signals

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _should_rebalance(self, timestamp: datetime) -> bool:
        if self._last_rebalance is None:
            return True
        delta = timestamp - self._last_rebalance
        return delta.days >= self.rebalance_days

    @staticmethod
    def _extract_prices(data: dict[str, pd.DataFrame]) -> dict[str, float]:
        """Extract the most recent close price for each symbol."""
        prices: dict[str, float] = {}
        for symbol, df in data.items():
            if df.empty or "close" not in df.columns:
                continue
            price = df["close"].iloc[-1]
            if pd.notna(price) and price > 0:
                prices[symbol] = float(price)
        return prices

    @staticmethod
    def _latest_timestamp(data: dict[str, pd.DataFrame]) -> datetime:
        """Return the most recent bar timestamp."""
        latest = datetime.min.replace(tzinfo=timezone.utc)
        for df in data.values():
            if df.empty:
                continue
            ts = df.index[-1]
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts > latest:
                latest = ts
        if latest == datetime.min.replace(tzinfo=timezone.utc):
            return datetime.now(timezone.utc)
        return latest

    def clear_cache(self) -> None:
        """Flush the fundamental data cache (forces re-fetch on next rebalance)."""
        self._fund_cache.clear()
        log.info("%s: fundamental data cache cleared", self.name)


__all__ = ["QualityValueStrategy"]
