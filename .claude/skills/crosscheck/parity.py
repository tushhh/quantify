"""Backtest parity check: run one fixed, offline backtest on a base revision and on the
working tree, then diff the results.

Usage (from the repo root, with the project's Python environment):
    python .claude/skills/crosscheck/parity.py [--base origin/main] [--strategies a,b|all]
                                               [--days 800] [--seed 7]

Exit codes: 0 identical, 1 results differ, 2 a run failed.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pickle
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_STRATEGIES = [
    "trend_following",
    "cross_sectional_momentum",
    "pairs_mean_reversion",
    "volatility_regime",
]
# quality_value pulls live yfinance fundamentals; ml_return_predictor trains for minutes.
ALL_STRATEGIES = DEFAULT_STRATEGIES + ["quality_value", "ml_return_predictor"]

SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "JPM", "XOM",
    "JNJ", "PFE", "KO", "WMT", "PG", "UNH", "V", "HD",
]
PAIRS = [("KO", "PEP"), ("XOM", "CVX"), ("JPM", "BAC")]
RUNNER = Path(__file__).with_name("_run_one.py")
RUN_TIMEOUT_S = 1800


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _ohlcv(close: np.ndarray, idx: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    n = len(close)
    open_ = close * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(1_000_000, 8_000_000, n).astype("int64"),
            "vwap": np.nan,
        },
        index=idx,
    )
    frame.index.name = "timestamp"
    return frame


def make_data(days: int, seed: int) -> dict:
    """Seeded market: a common factor, varied drift (momentum dispersion), three
    cointegrated pairs, SPY as benchmark and a mean-reverting ^VIX series (so
    volatility_regime never falls back to fetching live VIX)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-02", periods=days, tz="UTC")
    market = rng.normal(0.0003, 0.010, days)

    log_px: dict[str, np.ndarray] = {}
    for i, sym in enumerate(SYMBOLS):
        beta = 0.7 + 0.06 * (i % 6)
        drift = 0.00025 * ((i % 5) - 2)
        log_px[sym] = np.log(40.0 + 12 * i) + np.cumsum(beta * market + rng.normal(drift, 0.014, days))
    for leg_a, leg_b in PAIRS:
        spread = np.zeros(days)
        for t in range(1, days):
            spread[t] = 0.92 * spread[t - 1] + rng.normal(0, 0.012)
        log_px[leg_b] = log_px[leg_a] + np.log(1.15) + spread
    log_px["SPY"] = np.log(300.0) + np.cumsum(market)

    data = {sym: _ohlcv(np.exp(lp), idx, rng) for sym, lp in log_px.items()}

    vix = np.empty(days)
    vix[0] = 18.0
    for t in range(1, days):
        shock = rng.normal(0, 1.2) + (8.0 if rng.random() < 0.01 else 0.0)
        vix[t] = max(9.0, vix[t - 1] + 0.08 * (18.0 - vix[t - 1]) + shock)
    data["^VIX"] = _ohlcv(vix, idx, rng)

    universe = [s for s in data if s not in ("SPY", "^VIX")]
    return {"data": data, "universe": universe, "pairs": PAIRS}


def _export(repo: Path, ref: str, dest: Path) -> None:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref], cwd=repo, check=True, capture_output=True
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")


def _run(src: Path, data_path: Path, names: str, workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    out = workdir / "summary.json"
    env = {**os.environ, "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, str(RUNNER), str(src), str(data_path), names, str(out)],
        cwd=workdir,  # strategies write ./models etc. relative to cwd
        env=env,
        capture_output=True,
        text=True,
        timeout=RUN_TIMEOUT_S,
    )
    if proc.returncode != 0 or not out.exists():
        tail = "\n".join((proc.stderr or proc.stdout).strip().splitlines()[-25:])
        raise RuntimeError(tail or f"exit code {proc.returncode}")
    return json.loads(out.read_text(encoding="utf-8"))


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return a == b or abs(a - b) <= 1e-12 * max(1.0, abs(a), abs(b))
    return a == b


def _flatten(summary: dict) -> dict:
    """{'trades_by_strategy': {'a': 3}} -> {'trades_by_strategy:a': 3}"""
    flat = {}
    for key, value in summary.items():
        if isinstance(value, dict):
            flat.update({f"{key}:{k}": v for k, v in value.items()})
        else:
            flat[key] = value
    return flat


def _fmt(value) -> str:
    return f"{value:,.6f}" if isinstance(value, float) else str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main", help="revision to compare against")
    parser.add_argument("--head", default=None,
                        help="revision to test (default: the working tree, uncommitted changes included)")
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES),
                        help="comma-separated strategy names, or 'all'")
    parser.add_argument("--days", type=int, default=800, help="trading days of synthetic data")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    names = ALL_STRATEGIES if args.strategies == "all" else args.strategies.split(",")
    unknown = sorted(set(names) - set(ALL_STRATEGIES))
    if unknown:
        parser.error(f"unknown strategies {unknown}; choose from {ALL_STRATEGIES}")
    days = max(args.days, 1600) if "ml_return_predictor" in names else args.days

    repo = Path(_git("rev-parse", "--show-toplevel", cwd=Path.cwd()))
    base_sha = _git("rev-parse", "--short", args.base, cwd=repo)
    if args.head:
        head_label = f"{args.head} ({_git('rev-parse', '--short', args.head, cwd=repo)})"
    else:
        dirty = bool(_git("status", "--porcelain", "--untracked-files=no", cwd=repo))
        head_label = f"working tree ({_git('rev-parse', '--short', 'HEAD', cwd=repo)}"
        head_label += ", uncommitted changes)" if dirty else ")"

    payload = make_data(days, args.seed)
    print(f"crosscheck: {args.base} ({base_sha}) vs {head_label}")
    print(f"  strategies: {', '.join(names)} | {days} days, {len(payload['data']) - 1} symbols"
          f" + ^VIX, seed {args.seed}")

    with tempfile.TemporaryDirectory(prefix="crosscheck-") as tmp:
        tmp_path = Path(tmp)
        data_path = tmp_path / "data.pkl"
        with open(data_path, "wb") as fh:
            pickle.dump(payload, fh)

        _export(repo, args.base, tmp_path / "base")
        head_src = repo / "src"
        if args.head:
            _export(repo, args.head, tmp_path / "head")
            head_src = tmp_path / "head" / "src"
        results = {}
        for label, src in (("base", tmp_path / "base" / "src"), ("head", head_src)):
            try:
                results[label] = _run(src, data_path, ",".join(names), tmp_path / f"run-{label}")
            except Exception as exc:  # report and stop: a failed side can't be compared
                print(f"\n{label} run FAILED:\n{exc}")
                return 2

    base, head = _flatten(results["base"]), _flatten(results["head"])
    print(f"\n  {'metric':<40}{'base':>22}{'head':>22}")
    differing = []
    for key in sorted(set(base) | set(head), key=lambda k: (":" in k, k)):
        same = _same(base.get(key), head.get(key))
        if not same:
            differing.append(key)
        print(f"  {key:<40}{_fmt(base.get(key, '-')):>22}{_fmt(head.get(key, '-')):>22}"
              f"  {'' if same else '<-- differs'}")

    if differing:
        print(f"\nRESULT: results differ ({', '.join(differing)}).")
        print("If this was meant to be a refactor, treat it as a bug. If the change was")
        print("intended, explain each moved metric to the user.")
        return 1
    print("\nRESULT: identical. No backtest drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
