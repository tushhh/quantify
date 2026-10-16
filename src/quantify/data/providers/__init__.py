"""Data provider implementations and provider factory for Quantify."""

from quantify.data.providers.base import DataProvider
from quantify.data.providers.yfinance_provider import YFinanceProvider


def create_provider(name: str = "yfinance", **kwargs) -> DataProvider:
    provider = name.strip().lower()
    if provider in {"yfinance", "yf", "yahoo"}:
        return YFinanceProvider(**kwargs)
    raise ValueError(f"Unsupported data provider: {name}")


__all__ = ["DataProvider", "YFinanceProvider", "create_provider"]
