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

- **Portfolio Tracking with P&L**: The web app's Portfolio page (`/portfolio`) lets users log trades, track unrealized and realized P&L per position, set dip alert thresholds, and close positions with a recorded sell price. The old `/dashboard` URL redirects to `/portfolio`.
- **Quantify Trades Bot — Full Portfolio Commands**: The alert bot now supports `/buy`, `/sell`, and `/portfolio` commands via guided multi-step conversations. `/portfolio` shows live prices, per-position P&L, and portfolio-wide totals.
- **Live Price Feeds**: Portfolio positions are priced using `yfinance` `fast_info.last_price` — real-time during market hours, previous close after hours. Alerts run every 10 minutes during US market hours (9 AM–4:30 PM ET) and every 3 hours overnight/weekends.
- **ETF & Fund Support**: The symbol validator now accepts US-listed ETFs and mutual funds (e.g. VOO, SPY, QQQ) in addition to equities.
- **Screener News Sentiment**: `/top`, `/bottom`, and `/fullscan` bot commands now include a news sentiment line (bullish/bearish label + top headline) per ticker.
- **Security Hardening**: CORS wildcard removed — only whitelisted origins can make credentialed requests. JWT access tokens shortened from 7 days to 2 hours.
- **Serverless ML Training Pipeline**: The ML ensemble (LightGBM, XGBoost, CatBoost) trains daily via GitHub Actions on a 7 GB runner, pushing a `.joblib` artifact to a `model-cache` branch. The Heroku API downloads and serves it with <5 s inference latency.
- **Dual Telegram Bot Architecture**: Account-linked trade alerts via **Quantify Trades** and group/private ML predictions via **Quantify Predictions**.

---

Quantify is a modular, research-driven **quantitative trading framework** built in Python. It ships with six production-ready strategies, a full backtesting engine with realistic cost modeling, a multi-layered risk management system, and a portfolio tracker with Telegram alerts.

## Highlights

| | |
|---|---|
| **6 Built-in Strategies** | Trend following, cross-sectional momentum, pairs mean reversion, quality/value, ML return prediction (LightGBM), and volatility regime switching |
| **Realistic Backtesting** | Event-driven engine with configurable commissions, spread, slippage, and benchmark comparison |
| **Risk Management** | Portfolio drawdown limits, position sizing (equal-weight, vol-target, Kelly), stop-loss/take-profit, sector exposure caps |
| **Portfolio Tracker** | Log trades, track unrealized/realized P&L, set dip alert thresholds, close positions with sell price |
| **Performance Analytics** | Tearsheet generation, Sharpe/Sortino/Calmar ratios, drawdown analysis, and benchmark comparison |
| **Telegram Bots** | Real-time trade alerts and interactive ML predictions via [Quantify Trades](https://t.me/QuantifyAlertbot) and [Quantify Predictions](https://t.me/quantifychatbot) |

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
JWT_SECRET=your_secret_here

# Quantify Trades (alert bot)
TELEGRAM_BOT_TOKEN=your_trades_bot_token

# Quantify Predictions (prediction bot)
TELEGRAM_PREDICTION_BOT_TOKEN=your_prediction_bot_token

# GitHub Actions integration (for full screener workflow)
GITHUB_REPOSITORY=tushhh/quantify
GH_WORKFLOW_TOKEN=your_github_pat

# Heroku app URL (used for internal callbacks)
HEROKU_APP_URL=https://your-app.herokuapp.com

# Optional: shared secret for internal API endpoints
INTERNAL_API_SECRET=your_internal_secret
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

### Symbol Validation

When logging trades, Quantify validates that the ticker is US-listed. The validator accepts equities, ETFs, and mutual funds:

```
GET /api/utils/validate_symbol?symbol=VOO
```

```json
{ "valid": true, "exchange": "PCX" }
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
> The `ml` strategy uses an **Ensemble Committee** (Voting Regressor) combining **LightGBM**, **XGBoost**, and **CatBoost**. This provides significantly more stable predictions by averaging the signals of three independent models.

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

Quantify has two Telegram bots with distinct roles.

### 1. Quantify Trades — [@QuantifyAlertbot](https://t.me/QuantifyAlertbot)

Account-linked bot for managing your personal portfolio and receiving real-time trade alerts.

**Setup:** Go to Portfolio → Account Settings → enter your Telegram username → open [@QuantifyAlertbot](https://t.me/QuantifyAlertbot) and send `/start` to link your account.

**Commands:**

| Command | Description |
|---|---|
| `/start` | Links your Telegram chat to your Quantify account. |
| `/buy` | Guided 3-step flow: enter ticker → shares → buy price. Logs the trade and activates alerts. |
| `/sell` | Guided 3-step flow: enter ticker → quantity (or "all") → sell price. Records realized P&L. |
| `/portfolio` | Shows live prices, per-position P&L, and portfolio-wide totals (total value, unrealized P&L, realized P&L). |

**Automatic Alerts:**

| Alert | Trigger |
|---|---|
| **Holding period expired** | Fires when a trade's hold duration ends — time to sell. |
| **Dip alert** | Fires if the stock drops below your configured percentage threshold from entry. |
| **Sell signal** | Fires when the ML ensemble detects a negative holding strength. |

**Alert frequency:** Every 10 minutes during US market hours (Mon–Fri, 9 AM–4:30 PM ET). Every 3 hours overnight and on weekends.

---

### 2. Quantify Predictions — [@quantifychatbot](https://t.me/quantifychatbot)

Can be added to groups, channels, or queried in private chat for on-demand ML predictions. No account required.

**Commands:**

| Command | Description |
|---|---|
| `/predict <SYMBOL>` | ML prediction for any ticker (e.g. `/predict NVDA`). Returns direction, strength, predicted return, top feature drivers, and news sentiment. |
| `/top` | Top 10 bullish signals of the day with news sentiment. |
| `/bottom` | Top 10 bearish signals of the day with news sentiment. |
| `/fullscan` | Triggers a full 500-stock screener run via GitHub Actions. Results are delivered asynchronously when ready. |
| `/subscribe` | Subscribe the current group/channel to daily prediction summaries. |
| `/unsubscribe` | Disable automated daily broadcasts. |
| `/help` | Show command instructions. |

**How `/predict <SYMBOL>` works:**

1. Checks the pre-computed screener cache → replies instantly if found.
2. Checks the ad-hoc database cache (4-hour TTL) → replies instantly if fresh.
3. On a full cache miss: fetches 3 years of daily price history, computes technical indicators, runs the pre-trained ML ensemble, caches the result, and returns the signal.

**Resource Protections:**

| Protection | Detail |
|---|---|
| **Rate limiter** | Max 5 requests per 60 seconds per user/chat. |
| **Concurrency semaphore** | Caps parallel live predictions at 2 to prevent memory spikes. |
| **Async execution** | Live computations run in a thread pool to keep the server responsive. |
| **Short-term cache** | Results cached for 4 hours — repeat queries are instant. |

---

### Env Configuration

```dotenv
# Quantify Trades (account-linked alert bot)
TELEGRAM_BOT_TOKEN=your_trades_bot_token

# Quantify Predictions (group/private prediction bot)
TELEGRAM_PREDICTION_BOT_TOKEN=your_prediction_bot_token

# Force bot polling on web dyno (only if not running a dedicated worker)
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
|   |-- providers/          # Market data providers (yfinance)
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
|   |-- broker/             # Broker adapters (simulated)
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

api/
|-- main.py                 # FastAPI app and lifespan (scheduler, bots)
|-- models.py               # SQLAlchemy ORM models
|-- schemas.py              # Pydantic request/response schemas
|-- database.py             # DB session and runtime migrations
|-- market_data.py          # yfinance price fetching
|-- trade_service.py        # Portfolio P&L service layer
|-- telegram_bot.py         # Quantify Trades bot (alerts + /buy /sell /portfolio)
|-- prediction_bot.py       # Quantify Predictions bot (/predict /top /bottom /fullscan)
+-- routers/
    |-- auth.py             # JWT auth, registration, login
    |-- trades.py           # Portfolio CRUD and P&L endpoints
    |-- predict.py          # ML screener and cache endpoints
    |-- backtest.py         # Backtest submission and result polling
    |-- internal.py         # Internal callbacks (GitHub Actions → Heroku)
    |-- strategies.py
    |-- universe.py
    |-- risk.py
    +-- utils.py            # Symbol validation

web/
|-- src/app/
|   |-- portfolio/          # Portfolio tracker page (/portfolio)
|   |-- predict/            # ML screener page
|   |-- backtest/           # Backtest runner page
|   |-- strategies/         # Strategy configuration
|   |-- login/ signup/      # Auth pages
|   +-- account/            # Account settings (Telegram linking)
+-- src/components/
    |-- layout/             # Sidebar, header
    +-- ui/                 # Shared component primitives
```

---

## Configuration

All runtime behaviour is controlled by two files:

| File | Purpose |
|---|---|
| [`config/settings.yaml`](config/settings.yaml) | Strategy params, risk limits, backtest defaults, universe |
| [`.env`](.env.example) | API keys and secret overrides (never committed) |

Key configuration sections:

- **`data`** — universe of tickers, data provider, cache directory, history depth
- **`risk`** — max drawdown (15%), max single-position size (10%), daily loss limit (3%), sector caps
- **`backtest`** — initial capital, commission/spread/slippage assumptions, rebalance frequency
- **`strategies`** — per-strategy enable/disable, allocation weight, and all tunable hyper-parameters

---

## Testing

```bash
# Run the full test suite
pytest

# Quiet output
pytest -q

# With coverage
pytest --cov=quantify --cov-report=term-missing
```

Test modules cover `backtest`, `data`, `execution`, `risk`, `strategy`, and `api`.

---

## Tech Stack

| Category | Libraries |
|---|---|
| Data | pandas, NumPy, yfinance, pyarrow |
| ML / Stats | scikit-learn, LightGBM, XGBoost, CatBoost, statsmodels |
| Indicators | pandas-ta |
| Scheduling | APScheduler, pytz |
| Notifications | python-telegram-bot |
| Visualisation | matplotlib, seaborn |
| API | FastAPI, uvicorn, SQLAlchemy, passlib, python-jose |
| Frontend | Next.js (App Router), Tailwind CSS, Recharts, Vercel |
| CLI | Click |
| Config | PyYAML, python-dotenv |

---

## License

Copyright (c) 2026 Tushar Gupta. All rights reserved.

This software is **proprietary and confidential**. No part of this software may be reproduced, distributed, or transmitted in any form without the prior written permission of the copyright owner. See the `LICENSE` file for full details.
