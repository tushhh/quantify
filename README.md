<p align="center">
  <h1 align="center">Quantify</h1>
  <p align="center">
    <strong>A quantitative trading system for US equities</strong>
  </p>
  <p align="center">
    <a href="#strategies">Strategies</a> &middot; <a href="#quickstart">Quickstart</a> &middot; <a href="#cli-reference">CLI</a> &middot; <a href="#telegram-integration">Telegram</a> &middot; <a href="#architecture">Architecture</a>
  </p>
</p>

---

## What's New (June 2026)

- **Serverless ML Training Pipeline**: The heavy-lifting of the Machine Learning ensemble (LightGBM, XGBoost, CatBoost) has been entirely decoupled from the Heroku web server.
- **GitHub Actions Integration**: A new automated workflow (`.github/workflows/ml_train.yml`) now runs daily at 05:00 UTC. It spins up a 7GB GitHub runner, downloads 3 years of market data, trains the model, and pushes the `.joblib` model artifact to a hidden `model-cache` branch.
- **Lightweight Inference**: The Heroku API (`/api/predict/best`) no longer attempts to train the model locally. Instead, it securely downloads the latest pre-trained model directly from GitHub and performs instant inference (taking <5 seconds), completely resolving all memory limit (R15) crashes.
- **Telegram Bots Integration**: Added support for a dual-Telegram-bot architecture — an Account-linked Alert Bot and a Group Prediction Bot — to monitor portfolios and request on-demand ML predictions.
- **Ad-Hoc Stock Predictions**: The prediction bot resolves queries for *any* global ticker by fetching daily prices, extracting features dynamically, and executing the pre-trained ML model, with rate-limiting, concurrency semaphores, and a 4-hour database caching layer to run safely on Heroku's basic dyno.

## What's New (May 2026)

- Prediction API: added `/api/predict/best` endpoint that returns ML-ranked signals (5‑day horizon). Responses include per-symbol driver explanations and optional `model_metrics` (rmse, mae, hit_rate, spearman_ic).
- Cache & re-run: predictions are cached (in-memory + DB) and a manual re-run is supported via `?force=true` — the API now performs a synchronous recompute for forced requests and writes fresh results to the cache. Use the `PREDICTION_CACHE_TTL_SECONDS` and `PREDICTION_DATA_CACHE_DIR` env vars to control cache TTL and market-data cache location.
- ML backends: LightGBM/XGBoost/CatBoost are optional. If they are not installed the project falls back to an sklearn ensemble; install the preferred libraries for better performance: `pip install lightgbm xgboost catboost`
- Feature engineering: feature NaN/Inf handling improved to avoid corrupt z-scores. Targets are winsorized by default to reduce outlier impact.
- Frontend: `web` UI updated with a compact card variant for dense tables, global spacing tokens (8/12/16px grid), and driver/explanation pills in the screener UI. The Next.js app uses `next` 16 and Turbopack; run `npm run dev` for local development and `npm run build` for production builds.

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
| **Telegram Bots** | Real-time trade alerts and interactive ML predictions via [@QuantifyAlertbot](https://t.me/QuantifyAlertbot) and [@quantifychatbot](https://t.me/quantifychatbot) |

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
cp .env.example .env
```

**Windows:**
```powershell
copy .env.example .env
```

Then fill in your keys:

```dotenv
ALPACA_API_KEY=your_paper_api_key_here
ALPACA_SECRET_KEY=your_paper_secret_key_here
ALPACA_PAPER=true
```

### Run a Backtest

**Mac/Linux:**
```bash
quantify backtest \
  --strategy trend_following \
  --start 2022-01-01 \
  --end 2024-01-01 \
  --capital 100000
```

**Windows (PowerShell):**
```powershell
quantify backtest `
  --strategy trend_following `
  --start 2022-01-01 `
  --end 2024-01-01 `
  --capital 100000
```

### Paper Trade (Dry Run)

```bash
quantify paper-trade --strategy momentum --dry-run
```

### Portfolio Symbol Validation

When logging trades in the dashboard, Quantify validates that the ticker exists and is a US-listed equity. The API exposes a lightweight validator at:

```
GET /api/utils/validate_symbol?symbol=AMD
```

Response:

```json
{ "valid": true, "exchange": "NASDAQ" }
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

```
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
  --list         List all tickers grouped by sector
  --sector TEXT  Filter by GICS sector name
```

---

## Telegram Integration

Quantify features a dual-Telegram-bot architecture to provide real-time trade updates and interactive ML prediction queries.

### 1. Alert Bot — [@QuantifyAlertbot](https://t.me/QuantifyAlertbot)

Designed for individual users to receive real-time alerts for active trades linked to their Quantify account.

**Alert Types:**

| Alert | Trigger |
|---|---|
| **Holding Duration** | Notifies you when a trade's hold period ends — time to sell. |
| **Drawdown / Dip** | Fires if a stock drops below your custom percentage threshold (e.g. 10%) from entry. |
| **Sell Signal** | Triggers when the ML ensemble evaluates that holding strength has turned negative. |

**Commands:**

| Command | Description |
|---|---|
| `/start` | Links your Telegram chat to your Quantify account. Enter your exact Telegram username in Account Settings first. |

**Setup:** Go to your Quantify dashboard → Account Settings → enter your Telegram username → open [@QuantifyAlertbot](https://t.me/QuantifyAlertbot) and send `/start`.

---

### 2. Prediction Bot — [@quantifychatbot](https://t.me/quantifychatbot)

An interactive bot that can be added to Telegram groups, channels, or queried in private chats for on-demand ML predictions on any stock in the market.

**Commands:**

| Command | Description |
|---|---|
| `/predict <SYMBOL>` | Query ML predictions for *any* global ticker (e.g. `/predict GME`). Returns direction, strength, predicted 1d return, and top feature drivers. |
| `/top` | List the top 10 bullish (Long) predictions of the day. |
| `/bottom` | List the top 10 bearish (Short) predictions of the day. |
| `/subscribe` | Subscribe the current group/channel to receive automatic daily prediction summaries. |
| `/unsubscribe` | Disable automated daily broadcasts. |
| `/help` | Show command instructions. |

**How `/predict <SYMBOL>` works:**

1. Checks the pre-computed top-100 S&P 500 cache → replies instantly if found.
2. Checks the ad-hoc database cache (4-hour TTL) → replies instantly if fresh.
3. On a full cache miss: fetches 3 years of daily price history from Yahoo Finance, computes technical indicators via `FeatureEngine`, runs the pre-trained ML ensemble, caches the result, and returns the signal.

**Resource Protections (Heroku Basic Dyno Safe):**

| Protection | Detail |
|---|---|
| **Rate Limiter** | Max 5 requests per 60 seconds per user / chat. Returns a friendly error if exceeded. |
| **Concurrency Semaphore** | Caps parallel live predictions at 2 to prevent CPU/RAM spikes. |
| **Async Execution** | Live computations run in a background thread pool (`asyncio.to_thread`) to keep the server responsive. |
| **Short-Term Cache** | Results cached in `adhoc_prediction_cache` for 4 hours — repeat queries are instant. |

---

### Env Configuration

Configure the following keys in your `.env` file or Heroku Config Vars:

```dotenv
# Account-linked Alert Bot
TELEGRAM_BOT_TOKEN="your_alerts_bot_token"

# Group Prediction Bot
TELEGRAM_PREDICTION_BOT_TOKEN="your_prediction_bot_token"

# Force bot polling on Heroku web dynos (set to true if not using a worker dyno)
FORCE_RUN_BOTS=true
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
| ML / Stats | scikit-learn, LightGBM, XGBoost, CatBoost, statsmodels |
| Indicators | pandas-ta |
| Broker | alpaca-py |
| Scheduling | APScheduler |
| Notifications | python-telegram-bot |
| Visualisation | matplotlib, seaborn |
| API | FastAPI, uvicorn, SQLAlchemy |
| Frontend | Next.js (React), Vercel |
| CLI | Click |
| Config | PyYAML, python-dotenv |

---

## License

Copyright (c) 2026 Tushar. All rights reserved.

This software is **proprietary and confidential**. No part of this software may be reproduced, distributed, or transmitted in any form without the prior written permission of the copyright owner. See the `LICENSE` file for full details.
