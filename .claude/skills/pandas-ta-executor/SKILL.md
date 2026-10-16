---
name: pandas-ta-executor
description: Rules and a checker for indicator and feature math in Quantify. Use when adding or changing a technical indicator, a FeatureEngine feature (src/quantify/data/features.py), or signal math inside a strategy. Routes indicator math through pandas_ta and library code instead of hand-rolled formulas, and checks every feature for lookahead, nondeterminism, and drift between the pandas_ta and manual fallback branches.
---

# pandas-ta-executor: indicator math without guesswork

## Rules

1. **Reuse first.** `FeatureEngine` in `src/quantify/data/features.py` registers 36 features (`python ${CLAUDE_SKILL_DIR}/check_features.py` lists them all). Search there before writing a new one.
2. **Library math, not hand-written formulas.** New indicators call `pandas_ta`, or vectorised pandas/numpy, statsmodels or scipy. Register them with `@register_feature("name")`. The function takes one symbol's OHLCV frame and returns a Series on the same index.
3. **Keep fallbacks honest.** Several features have a manual branch for when `pandas_ta` can't import (`if _TA_AVAILABLE:`). A new fallback must agree with pandas_ta in the checker below, at least after warm-up.
4. **No lookahead.** The value at bar *t* may only use bars up to *t*. That rules out `shift(-n)`, `center=True` windows, `bfill`, and normalising over the whole series (`rank(pct=True)` or z-scores over all rows).
5. **Don't `dropna()` frames.** Warm-up NaNs are expected (`sma_200` has 199 of them), and strategies handle them. Dropping rows misaligns symbols and throws away history.
6. **The ML feature list is locked.** The persisted model was trained on the names in `_ALL_FEATURES` in `src/quantify/strategy/ml_return_predictor.py`. Adding, removing, renaming or redefining one of those means retraining (`ml_train.yml`). CLAUDE.md puts feature definitions off-limits unless the user asks. New features used only by other strategies are fine.

## Check

```bash
python ${CLAUDE_SKILL_DIR}/check_features.py                 # every registered feature
python ${CLAUDE_SKILL_DIR}/check_features.py rsi_14 my_new_feature
```

On synthetic, yfinance-shaped data it reports, per feature:

- **warmup**: bars before the first value.
- **lookahead**: whether earlier values change when the feature is recomputed on a truncated history.
- **deterministic**: whether two runs give identical output.
- **fallback_drift**: the pandas_ta branch against the manual branch. "early bars only" is a warm-up transient that converges. "persistent" means the formulas differ.

Exit code 1 on lookahead, nondeterminism or errors. `--strict` also fails on persistent drift and on always-NaN features.

As of October 2026 all 36 features pass. RSI, RSI divergence, MACD, ATR, MFI and OBV slope show early-bar fallback drift that converges by about bar 100.

For any new feature, also add a unit test in `tests/test_data/` that pins a known value or compares against a pandas_ta reference (see the never-again skill). For environment setup, see the crosscheck skill.
