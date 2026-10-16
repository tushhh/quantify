# CLAUDE.md — quantify.software

Project instruction file for Claude Code. Read this before touching any file.

---

## What this is

Quantify is an AI-powered quantitative trading platform targeting retail and semi-professional traders. It combines six trading strategies, an ML ensemble (LightGBM + XGBoost + CatBoost), an event-driven backtest engine, paper trading, and a Telegram bot — all surfaced through a Next.js frontend and FastAPI backend.

The product's core value proposition: institutional-grade quant tools, made accessible. The UI should feel like a Bloomberg terminal crossed with a modern SaaS product — precise, data-dense, and deliberate. Not a toy. Not a dashboard template.

---

## Stack

### Frontend
- **Framework**: Next.js (App Router)
- **Styling**: Tailwind CSS — use utility classes, no custom CSS files unless unavoidable
- **Language**: TypeScript
- **Deployment**: Vercel — see known issues below

### Backend
- **Framework**: FastAPI (Python)
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **ML**: LightGBM, XGBoost, CatBoost ensemble — trained daily via GitHub Actions
- **Broker integration**: IBKR via `ib_insync`
- **Notifications**: Telegram bot

### Key files and directories
```
/src/quantify/           # Python backend source
  strategy/              # Six trading strategies including ml_return_predictor.py
  backtest/              # Event-driven backtest engine
  risk/                  # Drawdown, sector caps, position sizing
/api/                    # FastAPI app (main.py) and routers/ — what Heroku runs
/web/                    # Next.js app (deployed by Vercel)
  src/app/               # App Router pages
  src/components/        # Shared UI components
  src/lib/               # API client, utils
/tests/                  # pytest suite (run from the repo root)
/.github/workflows/      # CI plus the scheduled ML/screener pipelines
CLAUDE.md                # This file
```

### Branches
- `main` is the only code branch. Pushes to it deploy: Vercel (web) and Heroku (API).
- `model-cache` and `screener-cache` are data stores, not work branches. `ml_train.yml` (daily) and `screener_cron.yml` (every 20 min) force-push them, and the production `/predict` API reads them. Never merge or delete them.
- A PreToolUse hook enforces both rules in every permission mode. It's wired up in `.claude/settings.json`, with the rules in `.claude/hooks/branch_guard.py`. It blocks pushes or merges into main, force pushes, and pushes to or deletions of the data branches. Don't work around a block: tell the user what you wanted to run.

---

## Known issues — do not break these further

1. **Vercel config**: The `vercel.json` has a broken build config. Don't modify it without understanding the existing issue first — check git log for context.
2. **DB table creation**: Table creation is disabled in prod config. Don't re-enable it without explicit instruction.
3. **Hardcoded credentials**: Some API keys are hardcoded in older files. Don't copy that pattern — use environment variables.
4. **Python version**: There's a mismatch between local dev and prod Python versions. Don't add dependencies that pin to a specific minor version.
5. **Heroku memory**: The paper trading service hits memory limits on Heroku's free tier. Don't add memory-heavy operations to that service path.

---

## What not to touch (without being asked)

- API contracts between frontend and FastAPI — don't change endpoint signatures
- The backtest engine core logic (`backtest/engine.py`)
- ML model training pipeline and feature definitions
- Telegram bot notification logic
- Database schema (migrations require explicit instruction). Tables are SQLAlchemy models in `api/models.py`; columns added after launch are patched in at startup by the `ensure_*_columns()` helpers in `api/database.py`

---

## Frontend conventions

### Component patterns
- Functional components with TypeScript props interfaces
- Co-locate component styles with the component file
- Prefer Tailwind utility classes over custom CSS
- Use `cn()` (clsx + tailwind-merge) for conditional class composition

### Data display
- Numbers: always format with appropriate precision — prices to 2dp, percentages to 1dp, large numbers with commas
- Loading states: use skeleton loaders, not spinners, for content areas
- Errors: show inline, with specific messaging — never just "Something went wrong"
- Empty states: treat as invitations to act, not dead ends

### API integration
- All backend calls go through `web/src/lib/api.ts` — don't fetch directly from components
- Handle loading, error, and success states explicitly for every API call
- Don't expose raw backend error messages to the UI

---

## Design system and visual direction

### Identity
Quantify targets traders who take themselves seriously. The aesthetic should communicate precision, speed, and control. Every design decision should ask: does this feel like a tool a professional would trust?

### Palette (target)
- `--bg-primary`: `#0A0A0F` — near-black, slight blue cast
- `--bg-surface`: `#13131A` — card/panel background
- `--bg-elevated`: `#1C1C26` — modals, dropdowns
- `--accent-primary`: `#6366F1` — indigo, primary actions
- `--accent-success`: `#22C55E` — positive returns, bullish signals
- `--accent-danger`: `#EF4444` — negative returns, bearish signals, risk alerts
- `--accent-warning`: `#F59E0B` — caution states, approaching limits
- `--text-primary`: `#F1F5F9` — main content
- `--text-secondary`: `#94A3B8` — labels, supporting info
- `--text-muted`: `#475569` — disabled, metadata
- `--border`: `#1E293B` — subtle borders

Use green/red semantically and consistently throughout — they carry meaning for traders.

### Typography
- **Display/headings**: `Inter` or `DM Sans` — clean, neutral, professional
- **Data/numbers**: `JetBrains Mono` or `IBM Plex Mono` — monospace for all numeric values, tickers, percentages, prices. This is non-negotiable for a trading product.
- **Body**: `Inter` — readable at small sizes
- Type scale: establish and follow one. Don't mix arbitrary sizes.

### Layout principles
- **Data density over whitespace**: traders want more information, not more breathing room. Don't over-pad data tables or stat cards.
- **Progressive disclosure**: advanced controls (backtest parameters, strategy config) start collapsed. Show simple by default, reveal complexity on demand.
- **Hierarchy through weight and color, not size alone**: a label and a value should be distinguishable at a glance.
- **Consistent grid**: 12-column grid, 16px gutters. Don't break the grid for decorative reasons.

### Component design standards

**Stat cards** (for ML predictions, portfolio metrics):
- Value in monospace, large
- Label in small caps or muted text above or below
- Delta/change indicator with semantic color (green up, red down)
- Subtle border, no drop shadow

**Tables** (backtests, trade history):
- Zebra striping with very low contrast
- Numeric columns right-aligned, monospace
- Sortable headers with visible sort state
- No horizontal scroll on desktop — design for the data, not against it

**Charts**:
- Dark background, minimal gridlines
- Use accent colors semantically — green for profit, red for loss, indigo for neutral series
- Always show axis labels and a legend
- Recharts is already in the stack — use it

**Buttons**:
- Primary: indigo fill, white text
- Secondary: transparent with border
- Destructive: red fill or red border
- Never more than two button variants in the same view

**Forms / inputs**:
- Dark background inputs with subtle border
- Error state: red border + inline message below the field
- Labels always above the input, never placeholder-only

### Motion
- Keep it minimal — this is a professional tool, not a marketing site
- Acceptable: subtle fade-in on page load, skeleton→content transition, hover state changes
- Avoid: scroll-triggered animations, dramatic entrance effects, anything that delays showing data

### Copy style
- Sentence case everywhere — no Title Case In Button Labels
- Active verbs: "Run backtest", "Add strategy", "View results" — not "Submit" or "Confirm"
- Data labels should describe what the number means, not how it was computed
  - ✅ "Today's return" — ❌ "daily_pct_chg"
  - ✅ "Prediction confidence" — ❌ "model_output_score"
- Error messages: specific and actionable — "Date range must be at least 30 days" not "Invalid input"
- Empty states: tell the user what to do — "No strategies added yet. Add one to start backtesting."

---

## Page-specific notes

### `/` (Homepage)
- Current issue: visual hierarchy is weak, copy doesn't differentiate from generic quant platforms
- Goal: the hero should communicate the ML ensemble + backtest combination as the key differentiator
- Don't use the generic "big number + gradient" hero pattern

### `/predict`
- Core product page — the ML output is the most differentiated feature
- Should surface: direction (bull/bear), confidence, top feature drivers, prediction horizon
- Driver explanations should be human-readable labels, not raw feature names
- This page should feel like a signal dashboard, not a form output

### `/backtest`
- Advanced controls (strategy params, position sizer, risk settings) must be collapsed by default
- Visible on load: strategy selector, date range, starting capital, Run button
- Results should appear below the form inline, not on a new page

### `/strategies`
- Six strategies — each needs a clear name, one-sentence description, and key parameters visible
- Status (active/inactive) should be immediately scannable

### `/dashboard`
- Portfolio overview — current positions, P&L, active strategies
- Data density is appropriate here — this is the "cockpit" view

---

## Development workflow

```bash
# Frontend dev server
cd web && npm run dev

# Backend dev server (same app as the Procfile)
PYTHONPATH=src:. uvicorn api.main:app --reload

# Lint and tests: exactly what CI runs, from the repo root
ruff check .
pytest

# Build check before committing frontend changes
cd web && npm run build
```

Always run `npm run build` before considering frontend work done — catch type errors and missing imports before they hit Vercel.

- CI (`.github/workflows/ci.yml`) pins the ruff version and `pyproject.toml` selects the rules. Bump them deliberately, never by leaving ruff unpinned.
- A bug fix comes with a regression test that fails without the fix, so the bug can't quietly return.

### Project skills (`.claude/skills/`)
Use these instead of improvised checks:
- `crosscheck`: backtest parity against main. Run it before committing changes to backtest, strategy, risk or execution code.
- `pandas-ta-executor`: indicator rules, plus the lookahead and fallback-drift checker for `data/features.py`.
- `never-again`: every bug fix gets a regression test, proven to fail without the fix.
- `deep-security-check`: secrets, route auth, secrets in workflow inputs, dependency audit.
- `16-eyes`: merge review against this file's rules. Use it before anything goes to main.
- `model-health`: is the live model fresh, matched to the code's feature schema, and better than chance? Also checks screener output and workflow runs. It runs every weekday in `.github/workflows/model_health.yml`, so check recent runs there first.
- `backtest-doctor`: sanity-check a backtest result for cost-unit errors, dead strategies, lookahead, survivorship bias and cost drag before trusting it.
- `grill-me` (only as `/grill-me`): an interview to pin down a plan before building it.

---

## When in doubt

- Preserve existing API contracts
- Match the existing Tailwind/TypeScript patterns in the codebase
- Ask before making structural changes to routing or database schema
- If something looks like a bug in the existing code, flag it rather than silently fixing it
