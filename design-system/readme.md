# Quantify — Design System

> A quantitative, research-grade **ML trading platform** for US equities. Quantify pairs a Python backtesting/strategy engine with a Next.js web app and a dual Telegram-bot layer. This design system captures the web product's visual language so agents can build on-brand screens, decks, and prototypes.

---

## Sources

This system was reverse-engineered from the product's own source. If you have access, explore these to go deeper:

- **GitHub (primary):** `tushhh/quantify` — https://github.com/tushhh/quantify
  - Web frontend: `web/` (Next.js 16 + Tailwind v4 `@theme` tokens). The canonical design tokens live in `web/src/app/globals.css`; primitives in `web/src/components/ui/`.
  - Product copy + feature set: root `README.md`.
- The platform also ships a Python framework (6 strategies, backtester, risk engine) and two Telegram bots — context for tone and terminology, not visual surface.

> **Substitution flags**
> - **Fonts:** the product uses **Geist** + **Geist Mono** (via `next/font`). This system ships them from the Google Fonts CSS API rather than self-hosted `.woff2`. If you have the original binaries, drop them in `tokens/` and swap the `@import` in `tokens/fonts.css` for `@font-face` rules.
> - **Icons:** the product uses **Lucide** (`lucide-react`). The UI kit loads Lucide from CDN. This is the genuine icon set, not a substitute.

---

## Content Fundamentals

How Quantify writes.

- **Voice — confident, plain, a little technical.** Short declaratives. Headlines stack two beats: *"Faster research. Cleaner execution."* Marketing copy favors verbs and outcomes over adjectives.
- **Person.** Marketing addresses **you** ("your trading home", "See Today's Picks"). Product chrome is terse and impersonal ("No active positions", "Log a New Trade").
- **Casing.** Sentence case for headings and body. **UPPERCASE micro-labels** with wide tracking for overlines, table headers, and tags (`WHAT CHANGED`, `DRIVER LEGEND`, `LONG` / `SHORT`). Title Case only on nav/section names ("Active Portfolio", "Backtest Lab").
- **Numbers are first-class.** Returns, Sharpe, z-scores, prices are always shown with explicit sign and units, in mono/tabular figures: `+2.41% 1d`, `z=−2.07`, `Sharpe 1.84`, `$128,406`. Positive is green, negative is red — never rely on color alone (arrows ▲/▼ accompany).
- **Compliance reflex.** Predictions are always hedged: *"These are model predictions, not financial advice."* Keep this disclaimer near any signal output.
- **No emoji.** The product uses **Unicode arrows** (▲ ▼) and **Lucide icons**, never emoji. Don't introduce them.
- **Terminology.** strategy, signal, driver, z-score, strength, allocation, drawdown, dip alert, paper trade, backtest, universe, ensemble (LightGBM/XGBoost/CatBoost), horizon. Tickers are uppercase.

Examples (verbatim from product):
- Hero: *"Quantify combines portfolio tracking, Telegram automation, strategy research, and backtesting in a sharper interface…"*
- Empty state: *"No active positions being tracked."*
- Confirmation: *"Trade logged! Telegram alert activated if connected."*

---

## Visual Foundations

- **Mode — dark by default.** The app hardcodes `data-theme="dark"`, so `:root` in this system **is** the dark theme; a light theme is available via `[data-theme="light"]`. Build dark unless asked otherwise.
- **Palette.** A near-black blue-tinted neutral base (`bg #0B1220`, `surface #0F1724`) — which harmonizes with the logo's navy — paired with a **steel-teal accent** (`#2F8DBA` dark / `#2474A0` light) drawn from the emblem, and a **gold highlight** (`#D9A93E`) from the arrow, used sparingly. Status colors: **green** gains/long, **red** losses/short, **amber** caution, **blue** info. Accent is used sparingly — primary buttons, active nav, focus rings, key numbers, small glow accents.
- **Type.** Geist for everything UI; **Geist Mono** for any numeric (tickers, prices, z-scores, strength) and code. Headlines are tight (`-0.02em`), heavy (700–800), sometimes 900 on marketing. Micro-labels are 10–11px uppercase, tracking `0.08em`–`0.22em`.
- **Backgrounds.** Flat dark surfaces — **no photography, no illustration, no texture**. The only decorative device is a soft, low-opacity **radial accent glow** (blurred teal circle, ~0.1–0.2 opacity) behind hero panels, login, and ranked cards. Use it whisper-quiet.
- **Gradients.** One only: `gradient-accent` (135° accent → accent-hover) on hero feature icons and the occasional primary CTA. Avoid blue-purple background gradients.
- **Cards.** `surface` fill, 1px `border` hairline, `radius-lg` (14px), `shadow-sm`. Hover (interactive cards) brightens the border to `border-bright` and lifts to `shadow-md`. Compact variant = 16px padding. A 2px top accent stripe (green/red/accent) marks status on position cards.
- **Radii.** 6 / 10 / 14 / 20 / 28 / full. Inputs & buttons use `md` (10px); cards `lg` (14px); hero glass panels `2xl` (28px); pills/badges full.
- **Borders & elevation.** Hairlines do most of the structural work; shadows are soft and dark-tuned (`rgba(2,6,23,…)`). Dividers are `border` / `border-subtle`. There is no heavy/neumorphic shadow.
- **Spacing.** 4px base on an **8 / 12 / 16** rhythm. Card padding 16–20px; section gaps 14–20px; page padding 24px.
- **Motion.** Restrained. `fade-in` (350ms) and `fade-in-up` (400ms) on mount; `hover-lift` (translateY -2px) on cards; buttons `scale(0.98)` on press; standard easing `cubic-bezier(0.4,0,0.2,1)`. Respect `prefers-reduced-motion`. No bounces, no infinite loops.
- **Hover / press states.** Hover = lighter background (`surface-raised`) or brighter border; primary buttons darken to `accent-hover`. Press = subtle scale-down. Focus = 3px `accent-subtle` ring + accent border.
- **Transparency & blur.** Used in two places: the topbar (`surface` at 80% + `blur(8px)`) and badges' subtle tinted fills (`color/10`). Otherwise surfaces are opaque.
- **Imagery vibe.** None shipped. If you must add imagery, keep it cool, dark, and data-flavored (charts, grids) — never warm or lifestyle.

---

## Iconography

- **System:** [Lucide](https://lucide.dev) — the product's `lucide-react` set. Thin (2px), rounded-cap, monoline outline icons on a 24×24 grid.
- **In this system:** the UI kit (`ui_kits/web/`) loads Lucide from CDN (`unpkg.com/lucide`) and renders via a small `<Icon name="…" />` helper (kebab-case names: `layout-dashboard`, `bar-chart-2`, `trending-up`, `refresh-cw`, `shield`, `activity`, `sparkles`, `bell`, `user-circle`, `plus`, `play`, `info`). For static HTML, link Lucide from CDN and call `lucide.createIcons()`.
- **Unicode as icons:** directional **▲ / ▼** are used inline for favorability/deltas (cheaper than an icon, aligns with mono numerics). Keep these.
- **Emoji:** never.
- **Logo:** an **emblem mark** — a circular "Q" formed by a ring and an upward chart-arrow, in a navy → teal → gold gradient — plus the full **QUANTIFY** wordmark lockup with the tagline *"Quantitative Strategies & Analytics."* Shipped as `assets/logo-emblem.png` (transparent, works on dark or light) and `assets/logo-full.png` (lockup, for light backgrounds). The emblem's navy reads low on very dark surfaces; prefer the emblem on `surface`/light or pair it with the "Quantify" text label.

---

## Index / Manifest

**Root**
- `styles.css` — global entry point (consumers link this). `@import`s only.
- `tokens/` — `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `base.css`.
- `assets/` — `logo-mark.svg`, `logo-wordmark.svg`.
- `guidelines/` — foundation specimen cards (Colors, Type, Spacing, Brand).
- `SKILL.md` — Agent-Skills-compatible entry point.

**Components** (`window.QuantifyDesignSystem_90f900.*`)
- `components/core/` — **Button**, **Badge**, **Card** (+ CardHeader/Content/Footer), **Input**, **StatCard**
- `components/data/` — **DriverPill**, **PredictionRow** (signature ML-signal row)
- `components/feedback/` — **Alert**

Each component directory has `<Name>.jsx`, `<Name>.d.ts`, `<Name>.prompt.md`, and a `*.card.html` specimen.

**UI kits**
- `ui_kits/web/` — interactive recreation of the Quantify web app: **Login → Dashboard, Predict, Backtest, Strategies**. Composes the DS primitives. See its `README.md`.

---

*Build dark, lead with the numbers, keep the accent rare, and always hedge the signal.*
