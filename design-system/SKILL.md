---
name: quantify-design
description: Use this skill to generate well-branded interfaces and assets for Quantify, either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.
If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.
If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick reference
- **Brand:** Quantify — a dark, numbers-first ML quantitative trading platform.
- **Mode:** dark by default (`:root` is dark; `[data-theme="light"]` opts into light).
- **Tokens:** link `styles.css`. Accent `--color-accent` (steel-teal `#2F8DBA` dark / `#2474A0` light, from the logo); gold highlight `--color-gold` `#D9A93E` (use sparingly); surfaces `--color-bg`/`--color-surface`; status `--color-success`/`--color-danger`/`--color-warning`/`--color-info`.
- **Type:** Geist (UI) + Geist Mono (all numerics, tickers, z-scores). Tight, heavy headlines; uppercase tracked micro-labels.
- **Icons:** Lucide (CDN). Unicode ▲/▼ for deltas. No emoji.
- **Components:** `window.QuantifyDesignSystem_90f900.*` — Button, Badge, Card, Input, StatCard, Alert, DriverPill, PredictionRow. Load `_ds_bundle.js`.
- **Reference app:** `ui_kits/web/` (login, dashboard, predict, backtest, strategies).

## Rules of thumb
- Lead with the numbers; sign + units always; positive green / negative red with an arrow.
- Keep the accent rare. Flat dark surfaces; the only decoration is a faint teal radial glow. Gold is a sparing highlight, not a fill.
- Always hedge signals: "model predictions, not financial advice."
