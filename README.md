<p align="center">
  <h1 align="center">Quantify</h1>
  <p align="center">
    <strong>A quantitative trading system for US equities</strong>
  </p>
  <p align="center">
    <a href="#strategies">Strategies</a> &middot; <a href="#quickstart">Quickstart</a> &middot; <a href="#cli-reference">CLI</a> &middot; <a href="#architecture">Architecture</a>
  </p>
</p>

---

Quantify is a modular, research-driven **quantitative trading framework** built in Python. It ships with six production-ready strategies, a full backtesting engine with realistic cost modeling, a multi-layered risk management system, and seamless integration with [Alpaca Markets](https://alpaca.markets/) for paper and live trading.

## Highlights

| | |
|---|---|
| **6 Built-in Strategies** | Trend following, cross-sectional momentum, pairs mean reversion, quality/value, ML return prediction (LightGBM), and volatility regime switching |
| **Realistic Backtesting** | Event-driven engine with configurable commissions, spread, slippage, and benchmark comparison |
| **Risk Management** | Portfolio drawdown limits, position sizing (equal-weight, vol-target, Kelly), stop-loss/take-profit, sector exposure caps |
| **Paper and Live Trading** | Scheduled execution via Alpaca with dry-run mode for signal inspection |
| **Performance Analytics** | Tearsheet generation, Sharpe/Sortino/Calmar ratios, drawdown analysis, and benchmark comparison |
| **Optional Dashboard** | Streamlit-powered UI for monitoring and analysis |

---

## Strategies

| Strategy | Key Idea | Default Allocation |
|---|---|---|
| **Trend Following** | EMA crossover (50/200) filtered by ADX, ATR-based stops | 15% |
| **Cross-Sectional Momentum** | Long top-quintile / short bottom-quintile by 12-1 month returns | 20% |
| **Pairs Mean Reversion** | Engle-Granger cointegration with z-score entry/exit | 20% |
| **Quality Value** | Composite rank on value (P/E, P/B, EV/EBITDA) and quality (ROE, ROA, margins) metrics | 20% |
| **ML Return Predictor** | **Ensemble Model** (LightGBM + XGBoost + CatBoost) trained on 5 years of historical features | 15% |
| **Volatility Regime** | VIX-based regime detection that dynamically re-weights the other strategies | 10% |

Allocations and parameters are fully configurable in [`config/settings.yaml`](config/settings.yaml).

---

## Quickstart

### Prerequisites

- **Python >= 3.11**
- An [Alpaca](https://alpaca.markets/) paper-trading account (free) for live/paper trading

### Installation

```bash
# Clone the repository
git clone https://github.com/tushhh/quantify.git
cd quantify

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Install in editable mode
pip install -e ".[dev]"
```

### Environment Setup

**Mac/Linux:**
```bash
# Copy the example env file and fill in your Alpaca keys
cp .env.example .env
```

**Windows Terminal:**
```powershell
# Copy the example env file and fill in your Alpaca keys
copy .env.example .env
```

```dotenv
ALPACA_API_KEY=your_paper_api_key_here
ALPACA_SECRET_KEY=your_paper_secret_key_here
ALPACA_PAPER=true
```

### Run a Backtest

**On Mac/Linux:**
```bash
# Note: Date format is YYYY-MM-DD
quantify backtest \
  --strategy trend_following \
  --start 2022-01-01 \
  --end 2024-01-01 \
  --capital 100000
```

**On Windows Terminal (PowerShell / Command Prompt):**
```powershell
# Note: Date format is YYYY-MM-DD
quantify backtest `
  --strategy trend_following `
  --start 2022-01-01 `
  --end 2024-01-01 `
  --capital 100000
```
*(Alternatively, in CMD, replace the backticks ``` ` ``` with carets `^` or run the command on a single line).*

### Paper Trade (Dry Run)

```bash
quantify paper-trade --strategy momentum --dry-run
```

---

## CLI Reference

```
quantify [OPTIONS] COMMAND [ARGS]
```

| Command | Description |
|---|---|
| `backtest` | Run a historical backtest for one or more strategies |
| `paper-trade` | Start the paper trading engine (supports `--dry-run`) |
| `report` | Generate a performance tearsheet from the trade log |
| `universe` | Display the stock universe, filter by sector |

### `backtest`

```
Options:
  --strategy NAME    Strategy to run (repeatable). Choices: ml, momentum,
                     pairs, quality_value, trend_following, vol_regime
  --start TEXT       Start date (YYYY-MM-DD)                    [required]
  --end TEXT         End date (YYYY-MM-DD)                      [required]
  --capital FLOAT    Initial capital in USD                     [default: 100000]
  --sizer TEXT       Position sizer: equal_weight | volatility_target |
                     risk_parity | half_kelly                   [default: equal_weight]
  --output-dir TEXT  Directory to save reports and charts
```

### `paper-trade`
  
> [!TIP]
> The `ml` strategy now uses an **Ensemble Committee** (Voting Regressor) combining **LightGBM**, **XGBoost**, and **CatBoost**. This provides significantly more stable predictions by averaging the signals of three independent "experts."

Options:
  --strategy NAME  Strategy to run (repeatable). Omit to use all enabled
                   strategies from config.
  --dry-run        Generate signals without submitting orders.
```

### `report`

```
Options:
  --start TEXT       Filter from date (YYYY-MM-DD)
  --end TEXT         Filter to date (YYYY-MM-DD)
  --output-dir TEXT  Directory to save the tearsheet
  --db-path TEXT     Path to the SQLite trade database
```

### `universe`

```
Options:
  --list        List all tickers grouped by sector
  --sector TEXT  Filter by GICS sector name
```

---

## Architecture

```
src/quantify/
|-- cli.py                  # Click CLI entry point
|-- config.py               # YAML + env config loader
|-- data/
|   |-- cache.py            # Parquet-based local data cache
|   |-- features.py         # Technical feature engineering
|   |-- models.py           # Bar / OHLCV data models
|   |-- providers/          # Market data providers (yfinance, Alpaca)
|   +-- universe.py         # S&P 500 universe and sector mapping
|-- strategy/
|   |-- base.py             # Abstract strategy interface
|   |-- signal.py           # Signal data model
|   |-- trend_following.py
|   |-- cross_sectional_momentum.py
|   |-- pairs_mean_reversion.py
|   |-- quality_value.py
|   |-- ml_return_predictor.py
|   +-- volatility_regime.py
|-- backtest/
|   |-- engine.py           # Event-driven backtest engine
|   |-- costs.py            # Commission / spread / slippage model
|   |-- analysis.py         # Post-backtest analysis
|   +-- report.py           # HTML and console report generation
|-- execution/
|   |-- broker/             # Broker adapters (Alpaca)
|   |-- order.py            # Order types and lifecycle
|   |-- order_manager.py    # Order routing and fill tracking
|   +-- portfolio.py        # Live portfolio state
|-- risk/
|   |-- limits.py           # Portfolio and position limit checks
|   |-- portfolio_risk.py   # Drawdown, leverage, exposure analytics
|   |-- position_sizer.py   # Equal-weight, vol-target, Kelly sizers
|   +-- stop_manager.py     # Stop-loss and take-profit management
|-- evaluation/
|   |-- metrics.py          # Sharpe, Sortino, Calmar, max drawdown, etc.
|   |-- benchmark.py        # Benchmark comparison (SPY)
|   +-- tearsheet.py        # Full performance tearsheet
|-- paper/
|   |-- trader.py           # Paper trading orchestrator
|   |-- scheduler.py        # APScheduler-based job scheduling
|   +-- monitor.py          # P&L and health monitoring
+-- persistence/
    |-- database.py         # SQLite trade and state database
    |-- trade_log.py        # Trade record logging
    +-- state.py            # Strategy state serialisation
```

---

## Configuration

All runtime behaviour is controlled by two files:

| File | Purpose |
|---|---|
| [`config/settings.yaml`](config/settings.yaml) | Strategy params, risk limits, backtest defaults, universe, Alpaca endpoints |
| [`.env`](.env.example) | API keys and secret overrides (never committed) |

Key configuration sections:

- **`data`** -- universe of tickers, data provider, cache directory, history depth
- **`risk`** -- max drawdown (15%), max single-position size (10%), daily loss limit (3%), sector caps
- **`backtest`** -- initial capital, commission/spread/slippage assumptions, rebalance frequency
- **`strategies`** -- per-strategy enable/disable, allocation weight, and all tunable hyper-parameters

---

## Testing

```bash
# Run the full test suite
pytest

# With coverage
pytest --cov=quantify --cov-report=term-missing
```

Test modules cover `backtest`, `data`, `execution`, `risk`, and `strategy`.

---

## Tech Stack

| Category | Libraries |
|---|---|
| Data | pandas, NumPy, yfinance, pyarrow |
| ML / Stats | scikit-learn, LightGBM, statsmodels |
| Indicators | pandas-ta |
| Broker | alpaca-py |
| Scheduling | APScheduler |
| Visualisation | matplotlib, seaborn |
| Dashboard | Streamlit (optional) |
| CLI | Click |
| Config | PyYAML, python-dotenv |

---

## License

This project is for personal / educational use. See the repository for license details.
