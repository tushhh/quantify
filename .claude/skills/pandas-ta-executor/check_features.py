"""Check FeatureEngine features for lookahead, nondeterminism and pandas_ta-vs-fallback drift.

Usage (from the repo root, with the project's Python environment):
    python .claude/skills/pandas-ta-executor/check_features.py [feature ...] [--strict]

Exit code 1 on lookahead, nondeterminism or errors; with --strict also on fallback
drift or features that are always NaN.
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

N_BARS = 700
CUTS = (350, 560)          # recompute on these truncated histories
DRIFT_TOLERANCE = 1e-6     # relative; fallback vs pandas_ta


def synthetic_ohlcv(n: int = N_BARS, seed: int = 11) -> pd.DataFrame:
    """One symbol shaped like YFinanceProvider output (UTC index, int volume, NaN vwap)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-02", periods=n, tz="UTC", name="timestamp")
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n)))
    open_ = close * (1 + rng.normal(0, 0.004, n))
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n))),
            "low": np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n))),
            "close": close,
            "volume": rng.integers(1_000_000, 5_000_000, n).astype("int64"),
            "vwap": np.nan,
        },
        index=idx,
    )


def max_diff(a: pd.Series, b: pd.Series) -> tuple[float, object]:
    """Largest absolute difference (NaN-aware: NaN vs number counts as infinite)
    and the index label where the series first differ."""
    a = pd.Series(a, dtype=float)
    b = pd.Series(b, dtype=float).reindex(a.index)
    both_nan = a.isna() & b.isna()
    diff = (a - b).abs().where(~both_nan, 0.0).fillna(np.inf)
    scale = max(1.0, float(np.nanmax(np.abs(a.to_numpy()))) if a.notna().any() else 1.0)
    bad = diff > 1e-9 * scale
    return float(diff.max()) if len(diff) else 0.0, (diff.index[bad.argmax()] if bad.any() else None)


def check(name: str, fn, df: pd.DataFrame, features_module) -> dict:
    row = {"feature": name, "warmup": "-", "lookahead": "-", "deterministic": "-",
           "fallback_drift": "-", "status": "OK"}
    try:
        full = fn(df)
        if full.notna().sum() == 0:
            row.update(status="ALWAYS-NaN")
            return row
        row["warmup"] = int(full.notna().to_numpy().argmax())

        row["deterministic"] = "yes" if max_diff(full, fn(df))[0] == 0 else "NO"

        leaks = []
        for cut in CUTS:
            diff, where = max_diff(full.iloc[:cut], fn(df.iloc[:cut]))
            if where is not None:
                leaks.append(f"bar {full.index.get_loc(where)} (max diff {diff:.3g})")
        row["lookahead"] = "none" if not leaks else "YES at " + leaks[0]

        if getattr(features_module, "_TA_AVAILABLE", False):
            features_module._TA_AVAILABLE = False
            try:
                manual = fn(df)
            finally:
                features_module._TA_AVAILABLE = True
            manual = pd.Series(manual, dtype=float).reindex(full.index)
            both = full.notna() & manual.notna()
            scale = max(float(np.nanmax(np.abs(full.to_numpy()))), 1e-12)
            rel = ((full - manual).abs() / scale).where(both, 0.0)
            late = rel.iloc[len(rel) // 2:]  # steady state, well past any warm-up
            nan_pattern_differs = bool((full.notna() != manual.notna()).any())
            if float(late.max()) > DRIFT_TOLERANCE:
                row["fallback_drift"] = f"{float(late.max()):.2%} of scale, persistent"
            elif float(rel.max()) > DRIFT_TOLERANCE or nan_pattern_differs:
                row["fallback_drift"] = f"early bars only (max {float(rel.max()):.2%})"
            else:
                row["fallback_drift"] = "none"

        if row["deterministic"] == "NO":
            row["status"] = "NONDETERMINISTIC"
        elif leaks:
            row["status"] = "LOOKAHEAD"
        elif row["fallback_drift"].endswith("persistent"):
            row["status"] = "DRIFT"
    except Exception as exc:  # report every feature, don't stop at the first failure
        row["status"] = f"ERROR: {type(exc).__name__}: {exc}"[:90]
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("features", nargs="*", help="feature names (default: all registered)")
    parser.add_argument("--strict", action="store_true",
                        help="also fail on fallback drift and always-NaN features")
    args = parser.parse_args()

    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    import quantify.data.features as features

    registry = features._REGISTRY
    names = args.features or sorted(registry)
    missing = [n for n in names if n not in registry]
    if missing:
        parser.error(f"not registered: {missing}. Registered: {sorted(registry)}")

    if not features._TA_AVAILABLE:
        print("note: pandas_ta is not importable here, so only the manual branches are checked.")

    df = synthetic_ohlcv()
    rows = [check(name, registry[name], df, features) for name in names]

    cols = ["feature", "warmup", "lookahead", "deterministic", "fallback_drift", "status"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print("  ".join(c.ljust(widths[c]) for c in cols))
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))

    hard = [r for r in rows if r["status"] in ("LOOKAHEAD", "NONDETERMINISTIC") or
            r["status"].startswith("ERROR")]
    soft = [r for r in rows if r["status"] in ("DRIFT", "ALWAYS-NaN")]
    print(f"\n{len(rows)} features checked: {len(hard)} failing, {len(soft)} warnings.")
    if any(r["fallback_drift"] not in ("-", "none") for r in rows):
        print("fallback_drift compares pandas_ta with the manual branch used when pandas_ta")
        print("can't import. 'early bars only' = a warm-up transient that converges; 'persistent'")
        print("= the formulas differ, so models would see different inputs per environment.")
    if any(r["status"] == "ALWAYS-NaN" for r in rows):
        print("ALWAYS-NaN: the feature never produces a value on yfinance-shaped input.")
    return 1 if hard or (args.strict and soft) else 0


if __name__ == "__main__":
    sys.exit(main())
