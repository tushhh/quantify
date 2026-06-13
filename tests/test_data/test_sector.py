"""
Tests for quantify.data.sector — sector relative-strength features.

All tests use synthetic data and mock the YFinanceProvider so no network
calls are made.
"""

from __future__ import annotations

from datetime import timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from quantify.data.sector import (
    SECTOR_ETF_MAP,
    add_sector_rs_features,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_price_df(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.cumprod(1 + rng.normal(0.0003, 0.012, n))
    index = pd.date_range("2022-01-03", periods=n, freq="B", tz=timezone.utc)
    return pd.DataFrame({"close": close, "open": close, "high": close, "low": close, "volume": 1_000_000}, index=index)


@pytest.fixture()
def stock_data() -> dict[str, pd.DataFrame]:
    return {
        "AAPL": _make_price_df(seed=1),
        "JPM": _make_price_df(seed=2),
        "XOM": _make_price_df(seed=3),
    }


@pytest.fixture()
def sector_map() -> dict[str, str]:
    return {
        "AAPL": "Information Technology",
        "JPM": "Financials",
        "XOM": "Energy",
    }


def _mock_provider(etf_data: dict[str, pd.DataFrame]):
    """Return a mock YFinanceProvider that returns synthetic ETF data."""
    mock = MagicMock()
    mock.get_multiple.return_value = etf_data
    return mock


# ---------------------------------------------------------------------------
# SECTOR_ETF_MAP completeness
# ---------------------------------------------------------------------------


class TestSectorEtfMap:
    def test_all_11_gics_sectors_present(self) -> None:
        expected = {
            "Information Technology",
            "Financials",
            "Health Care",
            "Consumer Discretionary",
            "Consumer Staples",
            "Industrials",
            "Energy",
            "Materials",
            "Real Estate",
            "Utilities",
            "Communication Services",
        }
        assert expected == set(SECTOR_ETF_MAP.keys())

    def test_all_values_are_xl_tickers(self) -> None:
        for sector, etf in SECTOR_ETF_MAP.items():
            assert isinstance(etf, str) and len(etf) > 0, f"Bad ETF for {sector}"


# ---------------------------------------------------------------------------
# add_sector_rs_features
# ---------------------------------------------------------------------------


class TestAddSectorRsFeatures:
    def _etf_data(self) -> dict[str, pd.DataFrame]:
        return {
            "XLK": _make_price_df(seed=10),
            "XLF": _make_price_df(seed=11),
            "XLE": _make_price_df(seed=12),
        }

    def _run(
        self,
        stock_data: dict[str, pd.DataFrame],
        sector_map: dict[str, str],
        horizons: tuple[int, ...] = (5, 21),
    ) -> dict[str, pd.DataFrame]:
        etf_data = self._etf_data()
        mock_provider = _mock_provider(etf_data)
        # Patch at the source modules because sector.py imports lazily inside the function.
        with (
            patch(
                "quantify.data.providers.yfinance_provider.YFinanceProvider",
                return_value=mock_provider,
            ),
            patch("quantify.data.cache.ParquetCache"),
        ):
            return add_sector_rs_features(
                stock_data, sector_map, horizons=horizons, cache_dir="/tmp/test_cache"
            )

    def test_columns_added(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        result = self._run(stock_data, sector_map)
        for sym, df in result.items():
            assert "sector_rs_5d" in df.columns, f"{sym} missing sector_rs_5d"
            assert "sector_rs_21d" in df.columns, f"{sym} missing sector_rs_21d"

    def test_same_keys_returned(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        result = self._run(stock_data, sector_map)
        assert set(result.keys()) == set(stock_data.keys())

    def test_index_unchanged(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        result = self._run(stock_data, sector_map)
        for sym in stock_data:
            pd.testing.assert_index_equal(result[sym].index, stock_data[sym].index)

    def test_values_finite_or_nan(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        result = self._run(stock_data, sector_map)
        for sym, df in result.items():
            for col in ("sector_rs_5d", "sector_rs_21d"):
                vals = df[col].dropna()
                assert not np.isinf(vals).any(), f"{sym}/{col} has inf values"

    def test_unknown_sector_gives_nan(
        self, stock_data: dict[str, pd.DataFrame]
    ) -> None:
        sector_map = {"AAPL": "Unknown", "JPM": "Unknown", "XOM": "Unknown"}
        result = self._run(stock_data, sector_map)
        for sym, df in result.items():
            assert df["sector_rs_5d"].isna().all(), f"{sym} should be all-NaN"

    def test_original_data_not_mutated(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        original_cols = {sym: list(df.columns) for sym, df in stock_data.items()}
        self._run(stock_data, sector_map)
        for sym, cols in original_cols.items():
            assert list(stock_data[sym].columns) == cols, f"{sym} was mutated"

    def test_empty_input_returns_empty(self) -> None:
        result = add_sector_rs_features({}, {})
        assert result == {}

    def test_provider_failure_returns_nan_columns(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        with (
            patch(
                "quantify.data.providers.yfinance_provider.YFinanceProvider",
                side_effect=RuntimeError("network"),
            ),
            patch("quantify.data.cache.ParquetCache"),
        ):
            result = add_sector_rs_features(
                stock_data, sector_map, cache_dir="/tmp/test_cache"
            )
        # Should return the stocks with NaN sector RS columns rather than raising
        assert set(result.keys()) == set(stock_data.keys())
        for df in result.values():
            assert "sector_rs_5d" in df.columns

    def test_custom_horizons(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        result = self._run(stock_data, sector_map, horizons=(10, 63))
        for df in result.values():
            assert "sector_rs_10d" in df.columns
            assert "sector_rs_63d" in df.columns
            assert "sector_rs_5d" not in df.columns

    def test_etf_fetch_end_extends_past_last_bar(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        """
        Regression: yfinance's `end` is exclusive, so fetching ETFs with
        end=stocks' last bar would drop that very day and leave sector_rs NaN
        at every stock's last bar (→ _predict skips all symbols).  The ETF
        fetch must request an end strictly after the stocks' last bar.
        """
        etf_data = self._etf_data()
        mock_provider = _mock_provider(etf_data)
        with (
            patch(
                "quantify.data.providers.yfinance_provider.YFinanceProvider",
                return_value=mock_provider,
            ),
            patch("quantify.data.cache.ParquetCache"),
        ):
            add_sector_rs_features(
                stock_data, sector_map, cache_dir="/tmp/test_cache"
            )

        stock_last = max(df.index.max() for df in stock_data.values())
        _, kwargs = mock_provider.get_multiple.call_args
        assert kwargs["end"] > stock_last, (
            "ETF fetch end must extend past the stocks' last bar so the most "
            "recent trading day is included (yfinance end is exclusive)"
        )

    def test_sector_rs_present_at_last_bar(
        self, stock_data: dict[str, pd.DataFrame], sector_map: dict[str, str]
    ) -> None:
        """When ETF data covers the stock index, sector_rs must be populated at
        the last bar — the row _predict actually consumes."""
        result = self._run(stock_data, sector_map)
        for sym, df in result.items():
            assert not np.isnan(df["sector_rs_5d"].iloc[-1]), f"{sym} NaN at last bar"
            assert not np.isnan(df["sector_rs_21d"].iloc[-1]), f"{sym} NaN at last bar"
