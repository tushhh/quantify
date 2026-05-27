"""
Universe management for the Quantify trading system.

Provides:
* ``get_sp500()``    — top ~100 most-liquid S&P 500 constituents (hardcoded).
* ``get_sector_map()`` — GICS sector for each ticker.
* ``Universe``       — filterable container supporting sector, market-cap,
                       and liquidity cuts.

Note on the hardcoded list
--------------------------
The canonical S&P 500 constituent list can be scraped from Wikipedia:
    https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
A full live scrape is not done here to avoid a network dependency at import
time.  To refresh the list call ``Universe.from_wikipedia()`` (requires
``requests`` and ``lxml`` / ``html5lib`` to be installed).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded universe data — top ~100 S&P 500 tickers by typical liquidity
# (as of early 2025; update periodically or use from_wikipedia())
# ---------------------------------------------------------------------------

# fmt: off
_SP500_TOP100: list[str] = [
    # Technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "META", "AVGO", "ORCL",
    "CRM", "AMD", "INTC", "QCOM", "TXN", "MU", "AMAT", "LRCX", "ADI",
    "KLAC", "MRVL", "NOW", "SNPS", "CDNS", "FTNT", "PANW",
    # Consumer Discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "BKNG",
    "MAR", "HLT", "ABNB", "DASH", "UBER", "LYFT",
    # Financials
    "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK",
    "SPGI", "MCO", "ICE", "CME", "CB", "PGR", "TRV",
    # Health Care
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "MDT",
    "SYK", "ISRG", "EW", "DXCM", "IDXX", "REGN", "VRTX", "GILD",
    "AMGN", "BMY", "PFE",
    # Industrials
    "GE", "CAT", "DE", "HON", "RTX", "LMT", "NOC", "GD", "BA", "UPS",
    "FDX", "NSC", "UNP", "CSX",
    # Communication Services
    "NFLX", "DIS", "T", "VZ", "CMCSA", "CHTR", "TMUS",
    # Consumer Staples
    "PG", "KO", "PEP", "COST", "WMT", "MDLZ", "CL", "EL",
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "MPC", "VLO",
    # Materials
    "LIN", "APD", "SHW", "FCX", "NEM",
    # Real Estate
    "AMT", "PLD", "CCI", "EQIX", "SPG",
    # Utilities
    "NEE", "SO", "DUK", "AEP", "SRE",
]
# fmt: on

# ---------------------------------------------------------------------------
# Russell 1000 — ~500 most-liquid large & mid-cap US stocks (NASDAQ + NYSE)
# Curated from iShares Russell 1000 ETF constituents as of early 2025.
# Covers 92%+ of US market cap across all 11 GICS sectors.
# ---------------------------------------------------------------------------

# fmt: off
_RUSSELL_1000: list[str] = [
    # ── Information Technology ─────────────────────────────────────────────
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "QCOM", "TXN",
    "AMAT", "MU", "ADI", "LRCX", "KLAC", "MRVL", "NOW", "SNPS", "CDNS",
    "FTNT", "PANW", "INTC", "HPQ", "HPE", "DELL", "STX", "WDC", "NTAP",
    "CTSH", "ACN", "INFY", "WIT", "EPAM", "GLOB", "FLUT", "GDDY", "GEN",
    "AKAM", "VRT", "ONTO", "ENTG", "ENPH", "SEDG", "FSLR", "OLED", "COHR",
    "KEYS", "TER", "MKSI", "NXPI", "SWKS", "QRVO", "MCHP", "ON", "MPWR",
    "WOLF", "AMBA", "SLAB", "SITM", "PI", "POWI", "DIOD", "NOVT",
    "PAYC", "PCTY", "DSGX", "PRGS", "MANH", "GWRE", "VRNS", "QLYS",
    "TENB", "ZS", "CRWD", "S", "CYBER", "OKTA", "SAIL", "ORCL",
    "IBM", "CSCO", "JNPR", "ANET", "FFIV", "NTGR", "CIEN", "VIAV",
    # ── Communication Services ────────────────────────────────────────────
    "GOOGL", "GOOG", "META", "NFLX", "DIS", "CMCSA", "CHTR", "TMUS",
    "T", "VZ", "PARA", "WBD", "LYV", "TTWO", "EA", "ATVI", "RBLX",
    "SNAP", "PINS", "MTCH", "IAC", "ZM", "DISH", "LUMN",
    # ── Consumer Discretionary ────────────────────────────────────────────
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "BKNG",
    "MAR", "HLT", "ABNB", "DASH", "UBER", "LYFT", "CMG", "YUM", "QSR",
    "DPZ", "DINE", "EAT", "DRI", "BLMN", "SHAK", "TXRH",
    "ROST", "TJX", "BURL", "FIVE", "DG", "DLTR", "OLLI",
    "BBY", "CC", "KMX", "AN", "PAG", "ABG", "LAD", "SAH",
    "WHR", "POOL", "SWK", "SNAP", "PVH", "VFC", "HBI", "GIII",
    "RL", "TPR", "CPRI", "LV", "MGM", "WYNN", "CZR", "BYD",
    "RCL", "CCL", "NCLH", "SIX", "FUN", "SEAS", "HAS", "MAT",
    "LKQ", "AZO", "ORLY", "GPC", "AAP",
    # ── Consumer Staples ──────────────────────────────────────────────────
    "WMT", "PG", "KO", "PEP", "COST", "MDLZ", "CL", "EL", "KHC",
    "GIS", "K", "CPB", "SJM", "HRL", "MKC", "CAG", "POST", "TWNK",
    "KR", "SFM", "ACI", "GO", "CASY", "WDFC", "CHD", "HENKEL",
    "CLX", "EDGEWELL", "SPB", "NWL", "ENR", "CSL", "HPC",
    "STZ", "BF-B", "TAP", "SAM", "MGPI", "COKE", "CELH",
    "MO", "PM", "BTI", "UVV", "SWMAY",
    "TSN", "HRL", "PPC", "SAFM", "CALM", "WH",
    "SYY", "USFD", "PFGC", "CHEF",
    # ── Financials ────────────────────────────────────────────────────────
    "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "AXP", "BLK",
    "SPGI", "MCO", "ICE", "CME", "CB", "PGR", "TRV", "MET", "PRU", "AFL",
    "ALL", "HIG", "AIG", "L", "EG", "CINF", "ERIE", "WTW", "AON", "MMC",
    "BEN", "IVZ", "TROW", "NTRS", "STT", "BK", "FHN", "USB", "PNC",
    "TFC", "FITB", "KEY", "CFG", "HBAN", "ZION", "CMA", "SNV", "EWBC",
    "PACW", "WAL", "BOKF", "UMBF", "CVBF", "FFIN", "IBOC", "IBCP",
    "COF", "SYF", "DFS", "ADS", "SLM", "NAVI", "ESLT",
    "ALLY", "CACC", "SC", "WRLD", "OMF",
    "LPLA", "RJF", "AMTD", "IBKR", "VIRT", "MKTX", "MSCI",
    "FDS", "CBOE", "NDAQ", "OWL", "STEP", "ARCC", "FS", "HTGC",
    # ── Health Care ───────────────────────────────────────────────────────
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "MDT",
    "SYK", "ISRG", "EW", "DXCM", "IDXX", "REGN", "VRTX", "GILD",
    "AMGN", "BMY", "PFE", "MRNA", "BNTX", "CVS", "CI", "HUM", "MOH",
    "CNC", "ELV", "HCA", "THC", "UHS", "CYH", "AMEH", "ACMR",
    "BDX", "BSX", "ZBH", "HOLX", "HSIC", "PDCO", "XRAY", "DVA",
    "INCY", "ALNY", "BMRN", "SGEN", "EXEL", "BLUE", "IONS",
    "IQV", "VEEV", "RCM", "NXGN", "HealthStream", "HCAT",
    "MCK", "CAH", "ABC", "PDCO", "PRGO",
    # ── Industrials ───────────────────────────────────────────────────────
    "GE", "CAT", "DE", "HON", "RTX", "LMT", "NOC", "GD", "BA", "UPS",
    "FDX", "NSC", "UNP", "CSX", "WAB", "TT", "JCI", "EMR", "ETN",
    "PH", "ROK", "AME", "FTV", "IR", "OTIS", "CARR", "ROP", "IEX",
    "XYL", "XYLEM", "REXNORD", "WTTR", "LII", "AIRLEASE",
    "GNRC", "TRMK", "AXE", "HUBB", "AOS", "MWA", "AWI", "TREX",
    "URI", "HEES", "KFRC", "MAN", "R", "KELYA",
    "WM", "RSG", "CLH", "CWST", "SRCL",
    "EXPD", "CHRW", "XPO", "SAIA", "ODFL", "JBHT", "WERN", "KNX",
    "GXO", "RXO", "DBO", "SEB", "VLDR",
    # ── Energy ────────────────────────────────────────────────────────────
    "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "MPC", "VLO", "PXD",
    "DVN", "FANG", "OXY", "HAL", "BKR", "NOV", "WFT", "HP", "PTEN",
    "NRG", "OGE", "LNG", "MPLX", "ET", "EPD", "PAA", "WMB", "OKE",
    "KMI", "TRP", "ENB", "PPL", "AES", "DTE", "EIX",
    "HES", "MRO", "APA", "SM", "CRGY", "VTLE", "NOG",
    "RRC", "EQT", "CTRA", "SWN", "CNX",
    # ── Materials ─────────────────────────────────────────────────────────
    "LIN", "APD", "SHW", "FCX", "NEM", "GOLD", "WPM", "AEM", "KGC",
    "ECL", "EMN", "ALB", "LIVENT", "SQM", "LAC",
    "PKG", "IP", "WRK", "SON", "GPK", "SLGN",
    "VMC", "MLM", "CX", "EXP", "USCR", "FRTA",
    "NUE", "STLD", "RS", "CMC", "X", "CLF", "MT", "ATI",
    "CF", "MOS", "NTR", "FMC", "CTVA", "ICL",
    "PPG", "RPM", "HUN", "OLN", "TROX", "VNTR",
    # ── Real Estate ───────────────────────────────────────────────────────
    "AMT", "PLD", "CCI", "EQIX", "SPG", "O", "VICI", "WPC", "NNN",
    "STOR", "STAG", "IIPR", "MPW", "HR", "DOC", "VTR", "WELL", "PEAK",
    "EXR", "PSA", "CUBE", "LSI", "NSA",
    "EQR", "AVB", "ESS", "UDR", "CPT", "AIV", "NMI",
    "BXP", "SLG", "KRC", "DEI", "PDM", "CUZ",
    "EGP", "FR", "REXR", "TRNO", "LPT",
    "DLR", "QTS", "CONE", "SWCH",
    # ── Utilities ─────────────────────────────────────────────────────────
    "NEE", "SO", "DUK", "AEP", "SRE", "D", "EXC", "XEL", "WEC", "CMS",
    "ES", "LNT", "EVRG", "NI", "OGE", "PNW", "POR", "AVA", "IDACORP",
    "AWK", "WTRG", "SJW", "MSEX", "ARTNA", "YORW",
    "CNP", "NWE", "SPKEP", "OTTR", "MGE",
]
# fmt: on

# ---------------------------------------------------------------------------
# Sector map — Russell 1000 additions (GICS classification)
# ---------------------------------------------------------------------------
_RUSSELL_SECTOR_MAP: dict[str, str] = {
    # Information Technology additions
    "HPQ": "Information Technology", "HPE": "Information Technology",
    "DELL": "Information Technology", "STX": "Information Technology",
    "WDC": "Information Technology", "NTAP": "Information Technology",
    "CTSH": "Information Technology", "ACN": "Information Technology",
    "INFY": "Information Technology", "WIT": "Information Technology",
    "EPAM": "Information Technology", "GLOB": "Information Technology",
    "FLUT": "Information Technology", "GDDY": "Information Technology",
    "GEN": "Information Technology", "AKAM": "Information Technology",
    "VRT": "Information Technology", "ONTO": "Information Technology",
    "ENTG": "Information Technology", "ENPH": "Information Technology",
    "SEDG": "Information Technology", "FSLR": "Information Technology",
    "OLED": "Information Technology", "COHR": "Information Technology",
    "KEYS": "Information Technology", "TER": "Information Technology",
    "MKSI": "Information Technology", "NXPI": "Information Technology",
    "SWKS": "Information Technology", "QRVO": "Information Technology",
    "MCHP": "Information Technology", "ON": "Information Technology",
    "MPWR": "Information Technology", "WOLF": "Information Technology",
    "AMBA": "Information Technology", "SLAB": "Information Technology",
    "SITM": "Information Technology", "PI": "Information Technology",
    "POWI": "Information Technology", "DIOD": "Information Technology",
    "NOVT": "Information Technology", "PAYC": "Information Technology",
    "PCTY": "Information Technology", "DSGX": "Information Technology",
    "PRGS": "Information Technology", "MANH": "Information Technology",
    "GWRE": "Information Technology", "VRNS": "Information Technology",
    "QLYS": "Information Technology", "TENB": "Information Technology",
    "ZS": "Information Technology", "CRWD": "Information Technology",
    "S": "Information Technology", "OKTA": "Information Technology",
    "SAIL": "Information Technology", "IBM": "Information Technology",
    "CSCO": "Information Technology", "JNPR": "Information Technology",
    "ANET": "Information Technology", "FFIV": "Information Technology",
    "NTGR": "Information Technology", "CIEN": "Information Technology",
    "VIAV": "Information Technology",
    # Communication Services additions
    "PARA": "Communication Services", "WBD": "Communication Services",
    "LYV": "Communication Services", "TTWO": "Communication Services",
    "EA": "Communication Services", "RBLX": "Communication Services",
    "SNAP": "Communication Services", "PINS": "Communication Services",
    "MTCH": "Communication Services", "IAC": "Communication Services",
    "ZM": "Communication Services", "DISH": "Communication Services",
    "LUMN": "Communication Services",
    # Consumer Discretionary additions
    "CMG": "Consumer Discretionary", "YUM": "Consumer Discretionary",
    "QSR": "Consumer Discretionary", "DPZ": "Consumer Discretionary",
    "DINE": "Consumer Discretionary", "EAT": "Consumer Discretionary",
    "DRI": "Consumer Discretionary", "BLMN": "Consumer Discretionary",
    "SHAK": "Consumer Discretionary", "TXRH": "Consumer Discretionary",
    "ROST": "Consumer Discretionary", "TJX": "Consumer Discretionary",
    "BURL": "Consumer Discretionary", "FIVE": "Consumer Discretionary",
    "DG": "Consumer Discretionary", "DLTR": "Consumer Discretionary",
    "OLLI": "Consumer Discretionary", "BBY": "Consumer Discretionary",
    "CC": "Consumer Discretionary", "KMX": "Consumer Discretionary",
    "AN": "Consumer Discretionary", "PAG": "Consumer Discretionary",
    "ABG": "Consumer Discretionary", "LAD": "Consumer Discretionary",
    "SAH": "Consumer Discretionary", "WHR": "Consumer Discretionary",
    "POOL": "Consumer Discretionary", "SWK": "Consumer Discretionary",
    "PVH": "Consumer Discretionary", "VFC": "Consumer Discretionary",
    "HBI": "Consumer Discretionary", "GIII": "Consumer Discretionary",
    "RL": "Consumer Discretionary", "TPR": "Consumer Discretionary",
    "CPRI": "Consumer Discretionary", "LV": "Consumer Discretionary",
    "MGM": "Consumer Discretionary", "WYNN": "Consumer Discretionary",
    "CZR": "Consumer Discretionary", "BYD": "Consumer Discretionary",
    "RCL": "Consumer Discretionary", "CCL": "Consumer Discretionary",
    "NCLH": "Consumer Discretionary", "SIX": "Consumer Discretionary",
    "FUN": "Consumer Discretionary", "SEAS": "Consumer Discretionary",
    "HAS": "Consumer Discretionary", "MAT": "Consumer Discretionary",
    "LKQ": "Consumer Discretionary", "AZO": "Consumer Discretionary",
    "ORLY": "Consumer Discretionary", "GPC": "Consumer Discretionary",
    "AAP": "Consumer Discretionary",
    # Consumer Staples additions
    "KHC": "Consumer Staples", "GIS": "Consumer Staples",
    "K": "Consumer Staples", "CPB": "Consumer Staples",
    "SJM": "Consumer Staples", "MKC": "Consumer Staples",
    "CAG": "Consumer Staples", "POST": "Consumer Staples",
    "TWNK": "Consumer Staples", "KR": "Consumer Staples",
    "SFM": "Consumer Staples", "ACI": "Consumer Staples",
    "GO": "Consumer Staples", "CASY": "Consumer Staples",
    "WDFC": "Consumer Staples", "CHD": "Consumer Staples",
    "CLX": "Consumer Staples", "NWL": "Consumer Staples",
    "ENR": "Consumer Staples", "STZ": "Consumer Staples",
    "BF-B": "Consumer Staples", "TAP": "Consumer Staples",
    "SAM": "Consumer Staples", "MGPI": "Consumer Staples",
    "COKE": "Consumer Staples", "CELH": "Consumer Staples",
    "MO": "Consumer Staples", "PM": "Consumer Staples",
    "BTI": "Consumer Staples", "TSN": "Consumer Staples",
    "PPC": "Consumer Staples", "SYY": "Consumer Staples",
    "USFD": "Consumer Staples", "PFGC": "Consumer Staples",
    # Financials additions
    "MET": "Financials", "PRU": "Financials", "AFL": "Financials",
    "ALL": "Financials", "HIG": "Financials", "AIG": "Financials",
    "L": "Financials", "EG": "Financials", "CINF": "Financials",
    "ERIE": "Financials", "WTW": "Financials", "AON": "Financials",
    "MMC": "Financials", "BEN": "Financials", "IVZ": "Financials",
    "TROW": "Financials", "NTRS": "Financials", "STT": "Financials",
    "BK": "Financials", "FHN": "Financials", "USB": "Financials",
    "PNC": "Financials", "TFC": "Financials", "FITB": "Financials",
    "KEY": "Financials", "CFG": "Financials", "HBAN": "Financials",
    "ZION": "Financials", "CMA": "Financials", "SNV": "Financials",
    "EWBC": "Financials", "PACW": "Financials", "WAL": "Financials",
    "BOKF": "Financials", "COF": "Financials", "SYF": "Financials",
    "DFS": "Financials", "ADS": "Financials", "SLM": "Financials",
    "ALLY": "Financials", "CACC": "Financials", "LPLA": "Financials",
    "RJF": "Financials", "IBKR": "Financials", "VIRT": "Financials",
    "MKTX": "Financials", "MSCI": "Financials", "FDS": "Financials",
    "CBOE": "Financials", "NDAQ": "Financials", "OWL": "Financials",
    "ARCC": "Financials", "HTGC": "Financials",
    # Health Care additions
    "MRNA": "Health Care", "BNTX": "Health Care", "CVS": "Health Care",
    "CI": "Health Care", "HUM": "Health Care", "MOH": "Health Care",
    "CNC": "Health Care", "ELV": "Health Care", "HCA": "Health Care",
    "THC": "Health Care", "UHS": "Health Care", "CYH": "Health Care",
    "BDX": "Health Care", "BSX": "Health Care", "ZBH": "Health Care",
    "HOLX": "Health Care", "HSIC": "Health Care", "PDCO": "Health Care",
    "XRAY": "Health Care", "DVA": "Health Care", "INCY": "Health Care",
    "ALNY": "Health Care", "BMRN": "Health Care", "SGEN": "Health Care",
    "EXEL": "Health Care", "IONS": "Health Care", "IQV": "Health Care",
    "VEEV": "Health Care", "MCK": "Health Care", "CAH": "Health Care",
    "ABC": "Health Care", "PRGO": "Health Care",
    # Industrials additions
    "TT": "Industrials", "JCI": "Industrials", "EMR": "Industrials",
    "ETN": "Industrials", "PH": "Industrials", "ROK": "Industrials",
    "AME": "Industrials", "FTV": "Industrials", "IR": "Industrials",
    "OTIS": "Industrials", "CARR": "Industrials", "ROP": "Industrials",
    "IEX": "Industrials", "XYL": "Industrials", "LII": "Industrials",
    "GNRC": "Industrials", "HUBB": "Industrials", "AOS": "Industrials",
    "MWA": "Industrials", "AWI": "Industrials", "TREX": "Industrials",
    "URI": "Industrials", "MAN": "Industrials", "R": "Industrials",
    "WM": "Industrials", "RSG": "Industrials", "CLH": "Industrials",
    "CWST": "Industrials", "SRCL": "Industrials", "EXPD": "Industrials",
    "CHRW": "Industrials", "XPO": "Industrials", "SAIA": "Industrials",
    "ODFL": "Industrials", "JBHT": "Industrials", "WERN": "Industrials",
    "KNX": "Industrials", "GXO": "Industrials",
    # Energy additions
    "PXD": "Energy", "DVN": "Energy", "FANG": "Energy", "OXY": "Energy",
    "HAL": "Energy", "BKR": "Energy", "NOV": "Energy", "HP": "Energy",
    "PTEN": "Energy", "NRG": "Energy", "LNG": "Energy", "MPLX": "Energy",
    "ET": "Energy", "EPD": "Energy", "PAA": "Energy", "WMB": "Energy",
    "OKE": "Energy", "KMI": "Energy", "HES": "Energy", "MRO": "Energy",
    "APA": "Energy", "SM": "Energy", "RRC": "Energy", "EQT": "Energy",
    "CTRA": "Energy", "SWN": "Energy", "CNX": "Energy",
    # Materials additions
    "GOLD": "Materials", "WPM": "Materials", "AEM": "Materials",
    "KGC": "Materials", "ECL": "Materials", "EMN": "Materials",
    "ALB": "Materials", "PKG": "Materials", "IP": "Materials",
    "WRK": "Materials", "SON": "Materials", "GPK": "Materials",
    "SLGN": "Materials", "VMC": "Materials", "MLM": "Materials",
    "CX": "Materials", "EXP": "Materials", "NUE": "Materials",
    "STLD": "Materials", "RS": "Materials", "CMC": "Materials",
    "X": "Materials", "CLF": "Materials", "MT": "Materials",
    "ATI": "Materials", "CF": "Materials", "MOS": "Materials",
    "NTR": "Materials", "FMC": "Materials", "CTVA": "Materials",
    "PPG": "Materials", "RPM": "Materials", "HUN": "Materials",
    "OLN": "Materials",
    # Real Estate additions
    "O": "Real Estate", "VICI": "Real Estate", "WPC": "Real Estate",
    "NNN": "Real Estate", "STAG": "Real Estate", "IIPR": "Real Estate",
    "MPW": "Real Estate", "HR": "Real Estate", "DOC": "Real Estate",
    "VTR": "Real Estate", "WELL": "Real Estate", "PEAK": "Real Estate",
    "EXR": "Real Estate", "PSA": "Real Estate", "CUBE": "Real Estate",
    "LSI": "Real Estate", "NSA": "Real Estate", "EQR": "Real Estate",
    "AVB": "Real Estate", "ESS": "Real Estate", "UDR": "Real Estate",
    "CPT": "Real Estate", "BXP": "Real Estate", "SLG": "Real Estate",
    "KRC": "Real Estate", "DEI": "Real Estate", "EGP": "Real Estate",
    "FR": "Real Estate", "REXR": "Real Estate", "DLR": "Real Estate",
    # Utilities additions
    "D": "Utilities", "EXC": "Utilities", "XEL": "Utilities",
    "WEC": "Utilities", "CMS": "Utilities", "ES": "Utilities",
    "LNT": "Utilities", "EVRG": "Utilities", "NI": "Utilities",
    "PNW": "Utilities", "POR": "Utilities", "AVA": "Utilities",
    "AWK": "Utilities", "WTRG": "Utilities", "CNP": "Utilities",
    "OTTR": "Utilities",
}
# fmt: on

# ---------------------------------------------------------------------------
# GICS sector mapping (representative; not exhaustive)
# ---------------------------------------------------------------------------

_SECTOR_MAP: dict[str, str] = {
    # Information Technology
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "NVDA": "Information Technology",
    "AVGO": "Information Technology",
    "ORCL": "Information Technology",
    "CRM": "Information Technology",
    "AMD": "Information Technology",
    "INTC": "Information Technology",
    "QCOM": "Information Technology",
    "TXN": "Information Technology",
    "MU": "Information Technology",
    "AMAT": "Information Technology",
    "LRCX": "Information Technology",
    "ADI": "Information Technology",
    "KLAC": "Information Technology",
    "MRVL": "Information Technology",
    "NOW": "Information Technology",
    "SNPS": "Information Technology",
    "CDNS": "Information Technology",
    "FTNT": "Information Technology",
    "PANW": "Information Technology",
    # Communication Services
    "GOOGL": "Communication Services",
    "GOOG": "Communication Services",
    "META": "Communication Services",
    "NFLX": "Communication Services",
    "DIS": "Communication Services",
    "T": "Communication Services",
    "VZ": "Communication Services",
    "CMCSA": "Communication Services",
    "CHTR": "Communication Services",
    "TMUS": "Communication Services",
    # Consumer Discretionary
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary",
    "SBUX": "Consumer Discretionary",
    "TGT": "Consumer Discretionary",
    "LOW": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary",
    "MAR": "Consumer Discretionary",
    "HLT": "Consumer Discretionary",
    "ABNB": "Consumer Discretionary",
    "DASH": "Consumer Discretionary",
    "UBER": "Consumer Discretionary",
    "LYFT": "Consumer Discretionary",
    # Consumer Staples
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    "PEP": "Consumer Staples",
    "COST": "Consumer Staples",
    "WMT": "Consumer Staples",
    "MDLZ": "Consumer Staples",
    "CL": "Consumer Staples",
    "EL": "Consumer Staples",
    # Financials
    "BRK-B": "Financials",
    "JPM": "Financials",
    "V": "Financials",
    "MA": "Financials",
    "BAC": "Financials",
    "WFC": "Financials",
    "GS": "Financials",
    "MS": "Financials",
    "AXP": "Financials",
    "BLK": "Financials",
    "SPGI": "Financials",
    "MCO": "Financials",
    "ICE": "Financials",
    "CME": "Financials",
    "CB": "Financials",
    "PGR": "Financials",
    "TRV": "Financials",
    # Health Care
    "UNH": "Health Care",
    "JNJ": "Health Care",
    "LLY": "Health Care",
    "ABBV": "Health Care",
    "MRK": "Health Care",
    "TMO": "Health Care",
    "ABT": "Health Care",
    "DHR": "Health Care",
    "MDT": "Health Care",
    "SYK": "Health Care",
    "ISRG": "Health Care",
    "EW": "Health Care",
    "DXCM": "Health Care",
    "IDXX": "Health Care",
    "REGN": "Health Care",
    "VRTX": "Health Care",
    "GILD": "Health Care",
    "AMGN": "Health Care",
    "BMY": "Health Care",
    "PFE": "Health Care",
    # Industrials
    "GE": "Industrials",
    "CAT": "Industrials",
    "DE": "Industrials",
    "HON": "Industrials",
    "RTX": "Industrials",
    "LMT": "Industrials",
    "NOC": "Industrials",
    "GD": "Industrials",
    "BA": "Industrials",
    "UPS": "Industrials",
    "FDX": "Industrials",
    "NSC": "Industrials",
    "UNP": "Industrials",
    "CSX": "Industrials",
    # Energy
    "XOM": "Energy",
    "CVX": "Energy",
    "COP": "Energy",
    "EOG": "Energy",
    "SLB": "Energy",
    "PSX": "Energy",
    "MPC": "Energy",
    "VLO": "Energy",
    # Materials
    "LIN": "Materials",
    "APD": "Materials",
    "SHW": "Materials",
    "FCX": "Materials",
    "NEM": "Materials",
    # Real Estate
    "AMT": "Real Estate",
    "PLD": "Real Estate",
    "CCI": "Real Estate",
    "EQIX": "Real Estate",
    "SPG": "Real Estate",
    # Utilities
    "NEE": "Utilities",
    "SO": "Utilities",
    "DUK": "Utilities",
    "AEP": "Utilities",
    "SRE": "Utilities",
}


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def get_sp500() -> list[str]:
    """
    Return the top ~100 most-liquid S&P 500 constituent tickers.

    The list is hardcoded for offline use.  For the full 503-member list,
    call :meth:`Universe.from_wikipedia` (requires network access).

    Returns
    -------
    list[str]
        Sorted list of ticker symbols.
    """
    return sorted(set(_SP500_TOP100))


def get_russell1000() -> list[str]:
    """
    Return ~500 of the most-liquid Russell 1000 large & mid-cap US tickers.

    Covers NASDAQ and NYSE stocks across all 11 GICS sectors, representing
    ~92% of US market capitalisation.  The list is hardcoded for offline use
    and curated from iShares Russell 1000 ETF constituents (early 2025).

    Returns
    -------
    list[str]
        Sorted, deduplicated list of ticker symbols.
    """
    return sorted(set(_RUSSELL_1000))


def get_sector_map() -> dict[str, str]:
    """
    Return a mapping of ticker → GICS sector for the full universe (S&P 100 + Russell 1000).

    Tickers not present in the map have an unknown sector (use
    ``sector_map.get(ticker, "Unknown")``).

    Returns
    -------
    dict[str, str]
        ``{"AAPL": "Information Technology", ...}``
    """
    combined = dict(_SECTOR_MAP)
    combined.update(_RUSSELL_SECTOR_MAP)
    return combined


# ---------------------------------------------------------------------------
# Universe class
# ---------------------------------------------------------------------------

# All known GICS sectors
GICS_SECTORS: list[str] = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
]


@dataclass
class Universe:
    """
    A filterable set of ticker symbols with associated metadata.

    Attributes
    ----------
    tickers:
        The full constituent list (before any filtering).
    sector_map:
        Mapping from ticker → GICS sector string.
    market_cap:
        Optional mapping from ticker → market-cap in USD.
    avg_dollar_volume:
        Optional mapping from ticker → trailing 30-day average dollar volume.

    Examples
    --------
    Build the default S&P 500 universe and slice by sector:

    >>> u = Universe.sp500()
    >>> tech = u.filter_by_sector("Information Technology")
    >>> print(tech.tickers[:5])

    Apply a minimum liquidity screen:

    >>> liquid = u.filter_by_liquidity(min_dollar_volume=1e9)
    """

    tickers: list[str]
    sector_map: dict[str, str] = field(default_factory=get_sector_map)
    market_cap: dict[str, float] = field(default_factory=dict)
    avg_dollar_volume: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def sp500(cls) -> "Universe":
        """Create a Universe from the hardcoded top-100 S&P 500 list."""
        return cls(tickers=get_sp500(), sector_map=get_sector_map())

    @classmethod
    def russell1000(cls) -> "Universe":
        """Create a Universe from the curated Russell 1000 large & mid-cap list (~500 tickers)."""
        return cls(tickers=get_russell1000(), sector_map=get_sector_map())

    @classmethod
    def from_tickers(
        cls,
        tickers: Sequence[str],
        sector_map: dict[str, str] | None = None,
    ) -> "Universe":
        """Create a Universe from an arbitrary list of tickers."""
        return cls(
            tickers=sorted(set(t.upper() for t in tickers)),
            sector_map=sector_map or {},
        )

    @classmethod
    def from_wikipedia(cls) -> "Universe":
        """
        Fetch the current S&P 500 constituents from Wikipedia and return a
        Universe.

        Requires ``requests`` and either ``lxml`` or ``html5lib``.

        Raises
        ------
        ImportError
            If required packages are missing.
        RuntimeError
            If the Wikipedia page cannot be parsed.
        """
        try:
            import requests  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "requests is required for Universe.from_wikipedia(). "
                "Install it with: pip install requests"
            ) from exc

        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        logger.info("Fetching S&P 500 list from %s", url)
        try:
            tables = pd.read_html(url, header=0)
        except Exception as exc:
            raise RuntimeError(
                f"Could not parse Wikipedia S&P 500 table: {exc}"
            ) from exc

        df = tables[0]
        symbol_col = next(
            (c for c in df.columns if "symbol" in c.lower() or "ticker" in c.lower()),
            df.columns[0],
        )
        sector_col = next(
            (c for c in df.columns if "gics" in c.lower() and "sector" in c.lower()),
            None,
        )

        tickers = [s.replace(".", "-") for s in df[symbol_col].tolist()]
        sector_map: dict[str, str] = {}
        if sector_col:
            for _, row in df.iterrows():
                ticker = str(row[symbol_col]).replace(".", "-")
                sector_map[ticker] = str(row[sector_col])

        logger.info("Loaded %d S&P 500 tickers from Wikipedia.", len(tickers))
        return cls(tickers=sorted(set(tickers)), sector_map=sector_map)

    # ------------------------------------------------------------------
    # Filtering methods (all return a new Universe instance)
    # ------------------------------------------------------------------

    def filter_by_sector(self, *sectors: str) -> "Universe":
        """
        Return a new Universe containing only tickers in the given GICS sector(s).

        Parameters
        ----------
        *sectors:
            One or more GICS sector names (case-sensitive, e.g.
            ``"Information Technology"``).

        Returns
        -------
        Universe
        """
        sectors_set = set(sectors)
        filtered = [
            t for t in self.tickers
            if self.sector_map.get(t, "Unknown") in sectors_set
        ]
        return Universe(
            tickers=filtered,
            sector_map=self.sector_map,
            market_cap=self.market_cap,
            avg_dollar_volume=self.avg_dollar_volume,
        )

    def filter_by_market_cap(
        self,
        min_market_cap: float | None = None,
        max_market_cap: float | None = None,
    ) -> "Universe":
        """
        Return a new Universe filtered by market capitalisation (USD).

        Tickers with no market-cap data are excluded when a filter is applied.
        """
        if not self.market_cap:
            logger.warning(
                "filter_by_market_cap called but no market_cap data loaded."
            )
            return Universe(
                tickers=list(self.tickers),
                sector_map=self.sector_map,
                market_cap=self.market_cap,
                avg_dollar_volume=self.avg_dollar_volume,
            )

        filtered = []
        for t in self.tickers:
            mc = self.market_cap.get(t)
            if mc is None:
                continue
            if min_market_cap is not None and mc < min_market_cap:
                continue
            if max_market_cap is not None and mc > max_market_cap:
                continue
            filtered.append(t)

        return Universe(
            tickers=filtered,
            sector_map=self.sector_map,
            market_cap=self.market_cap,
            avg_dollar_volume=self.avg_dollar_volume,
        )

    def filter_by_liquidity(
        self,
        min_dollar_volume: float | None = None,
        max_dollar_volume: float | None = None,
    ) -> "Universe":
        """
        Return a new Universe filtered by average daily dollar volume (USD).

        Tickers with no dollar-volume data are excluded when a filter is applied.
        """
        if not self.avg_dollar_volume:
            logger.warning(
                "filter_by_liquidity called but no avg_dollar_volume data loaded."
            )
            return Universe(
                tickers=list(self.tickers),
                sector_map=self.sector_map,
                market_cap=self.market_cap,
                avg_dollar_volume=self.avg_dollar_volume,
            )

        filtered = []
        for t in self.tickers:
            adv = self.avg_dollar_volume.get(t)
            if adv is None:
                continue
            if min_dollar_volume is not None and adv < min_dollar_volume:
                continue
            if max_dollar_volume is not None and adv > max_dollar_volume:
                continue
            filtered.append(t)

        return Universe(
            tickers=filtered,
            sector_map=self.sector_map,
            market_cap=self.market_cap,
            avg_dollar_volume=self.avg_dollar_volume,
        )

    def exclude(self, tickers: Iterable[str]) -> "Universe":
        """Return a new Universe with *tickers* removed."""
        exclude_set = {t.upper() for t in tickers}
        return Universe(
            tickers=[t for t in self.tickers if t not in exclude_set],
            sector_map=self.sector_map,
            market_cap=self.market_cap,
            avg_dollar_volume=self.avg_dollar_volume,
        )

    def with_market_caps(self, market_cap: dict[str, float]) -> "Universe":
        """Return a copy with updated market-cap data."""
        return Universe(
            tickers=list(self.tickers),
            sector_map=self.sector_map,
            market_cap=market_cap,
            avg_dollar_volume=self.avg_dollar_volume,
        )

    def with_avg_dollar_volume(self, adv: dict[str, float]) -> "Universe":
        """Return a copy with updated average dollar volume data."""
        return Universe(
            tickers=list(self.tickers),
            sector_map=self.sector_map,
            market_cap=self.market_cap,
            avg_dollar_volume=adv,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def sectors_present(self) -> list[str]:
        """Return a sorted list of unique GICS sectors in this universe."""
        return sorted({self.sector_map.get(t, "Unknown") for t in self.tickers})

    def sector_counts(self) -> dict[str, int]:
        """Return a dict mapping sector → number of tickers."""
        counts: dict[str, int] = {}
        for t in self.tickers:
            s = self.sector_map.get(t, "Unknown")
            counts[s] = counts.get(s, 0) + 1
        return dict(sorted(counts.items()))

    def __len__(self) -> int:
        return len(self.tickers)

    def __iter__(self):
        return iter(self.tickers)

    def __contains__(self, item: str) -> bool:
        return item.upper() in self.tickers

    def __repr__(self) -> str:
        return (
            f"Universe(n={len(self.tickers)}, "
            f"sectors={len(self.sectors_present())})"
        )
