"""
Quantify data layer.

Public re-exports for convenience:

    from quantify.data import Bar, TimeFrame, ParquetCache, Universe
    from quantify.data import bars_to_dataframe, get_sp500, get_sector_map
    from quantify.data import FeatureEngine, register_feature
    from quantify.data.providers import DataProvider
"""

from quantify.data.cache import ParquetCache
from quantify.data.features import FeatureEngine, list_features, register_feature
from quantify.data.models import Bar, TimeFrame, bars_to_dataframe, dataframe_to_bars
from quantify.data.providers.base import (
    AuthenticationError,
    DataProvider,
    DataProviderError,
    RateLimitError,
    SymbolNotFoundError,
)
from quantify.data.universe import Universe, get_sector_map, get_sp500

__all__ = [
    # Models
    "Bar",
    "TimeFrame",
    "bars_to_dataframe",
    "dataframe_to_bars",
    # Cache
    "ParquetCache",
    # Provider base + exceptions
    "DataProvider",
    "DataProviderError",
    "RateLimitError",
    "SymbolNotFoundError",
    "AuthenticationError",
    # Universe
    "Universe",
    "get_sp500",
    "get_sector_map",
    # Features
    "FeatureEngine",
    "register_feature",
    "list_features",
]
