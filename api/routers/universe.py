"""
/api/universe  — Stock universe and sector information.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from api.schemas import TickerInfo, UniverseResponse

router = APIRouter(prefix="/universe", tags=["universe"])

# ---------------------------------------------------------------------------
# Static universe (mirrors config/settings.yaml + extra tickers with metadata)
# ---------------------------------------------------------------------------
_UNIVERSE: list[TickerInfo] = [
    # Technology
    TickerInfo(symbol="AAPL",  sector="Technology",        name="Apple Inc."),
    TickerInfo(symbol="MSFT",  sector="Technology",        name="Microsoft Corp."),
    TickerInfo(symbol="GOOGL", sector="Technology",        name="Alphabet Inc."),
    TickerInfo(symbol="META",  sector="Technology",        name="Meta Platforms"),
    TickerInfo(symbol="NVDA",  sector="Technology",        name="NVIDIA Corp."),
    TickerInfo(symbol="AVGO",  sector="Technology",        name="Broadcom Inc."),
    TickerInfo(symbol="ORCL",  sector="Technology",        name="Oracle Corp."),
    TickerInfo(symbol="CRM",   sector="Technology",        name="Salesforce Inc."),
    TickerInfo(symbol="AMD",   sector="Technology",        name="Advanced Micro Devices"),
    TickerInfo(symbol="INTC",  sector="Technology",        name="Intel Corp."),

    # Consumer Discretionary
    TickerInfo(symbol="AMZN",  sector="Consumer Discretionary", name="Amazon.com Inc."),
    TickerInfo(symbol="TSLA",  sector="Consumer Discretionary", name="Tesla Inc."),
    TickerInfo(symbol="HD",    sector="Consumer Discretionary", name="Home Depot Inc."),
    TickerInfo(symbol="MCD",   sector="Consumer Discretionary", name="McDonald's Corp."),
    TickerInfo(symbol="NKE",   sector="Consumer Discretionary", name="Nike Inc."),

    # Financials
    TickerInfo(symbol="JPM",   sector="Financials",        name="JPMorgan Chase"),
    TickerInfo(symbol="BAC",   sector="Financials",        name="Bank of America"),
    TickerInfo(symbol="GS",    sector="Financials",        name="Goldman Sachs"),
    TickerInfo(symbol="V",     sector="Financials",        name="Visa Inc."),
    TickerInfo(symbol="MA",    sector="Financials",        name="Mastercard Inc."),
    TickerInfo(symbol="BRK-B", sector="Financials",        name="Berkshire Hathaway"),
    TickerInfo(symbol="AXP",   sector="Financials",        name="American Express"),

    # Healthcare
    TickerInfo(symbol="UNH",   sector="Healthcare",        name="UnitedHealth Group"),
    TickerInfo(symbol="JNJ",   sector="Healthcare",        name="Johnson & Johnson"),
    TickerInfo(symbol="PFE",   sector="Healthcare",        name="Pfizer Inc."),
    TickerInfo(symbol="ABBV",  sector="Healthcare",        name="AbbVie Inc."),
    TickerInfo(symbol="LLY",   sector="Healthcare",        name="Eli Lilly"),
    TickerInfo(symbol="MRK",   sector="Healthcare",        name="Merck & Co."),

    # Energy
    TickerInfo(symbol="XOM",   sector="Energy",            name="Exxon Mobil"),
    TickerInfo(symbol="CVX",   sector="Energy",            name="Chevron Corp."),
    TickerInfo(symbol="COP",   sector="Energy",            name="ConocoPhillips"),
    TickerInfo(symbol="SLB",   sector="Energy",            name="Schlumberger"),

    # Consumer Staples
    TickerInfo(symbol="WMT",   sector="Consumer Staples",  name="Walmart Inc."),
    TickerInfo(symbol="PG",    sector="Consumer Staples",  name="Procter & Gamble"),
    TickerInfo(symbol="KO",    sector="Consumer Staples",  name="Coca-Cola Co."),
    TickerInfo(symbol="COST",  sector="Consumer Staples",  name="Costco Wholesale"),
    TickerInfo(symbol="PEP",   sector="Consumer Staples",  name="PepsiCo Inc."),

    # Industrials
    TickerInfo(symbol="CAT",   sector="Industrials",       name="Caterpillar Inc."),
    TickerInfo(symbol="BA",    sector="Industrials",       name="Boeing Co."),
    TickerInfo(symbol="HON",   sector="Industrials",       name="Honeywell Int'l"),
    TickerInfo(symbol="UPS",   sector="Industrials",       name="United Parcel Service"),

    # Communication Services
    TickerInfo(symbol="NFLX",  sector="Communication Services", name="Netflix Inc."),
    TickerInfo(symbol="DIS",   sector="Communication Services", name="Walt Disney Co."),
    TickerInfo(symbol="T",     sector="Communication Services", name="AT&T Inc."),
    TickerInfo(symbol="VZ",    sector="Communication Services", name="Verizon Communications"),

    # ETFs / Benchmarks
    TickerInfo(symbol="SPY",   sector="ETF",               name="S&P 500 ETF (SPDR)"),
    TickerInfo(symbol="QQQ",   sector="ETF",               name="Nasdaq-100 ETF (Invesco)"),
    TickerInfo(symbol="IWM",   sector="ETF",               name="Russell 2000 ETF (iShares)"),
    TickerInfo(symbol="GLD",   sector="ETF",               name="Gold ETF (SPDR)"),
]

_SECTORS = sorted({t.sector for t in _UNIVERSE})


@router.get("", response_model=UniverseResponse)
async def get_universe(sector: Optional[str] = Query(None, description="Filter by GICS sector")) -> UniverseResponse:
    """Return the full stock universe, optionally filtered by sector."""
    tickers = _UNIVERSE
    if sector:
        tickers = [t for t in tickers if t.sector.lower() == sector.lower()]
    return UniverseResponse(tickers=tickers, sectors=_SECTORS)


@router.get("/sectors", response_model=list[str])
async def list_sectors() -> list[str]:
    """Return the list of unique sectors in the universe."""
    return _SECTORS
