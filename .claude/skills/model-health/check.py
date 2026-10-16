"""Health check for Quantify's production ML pipeline.

Reads the live model (model-cache branch), the live screener output (screener-cache
branch) and recent GitHub Actions runs, and checks them against the code on origin/main.

Usage (from the repo root):
    python .claude/skills/model-health/check.py [--code origin/main] [--no-actions]

Exit code 1 if any FAIL. Needs network for git fetch and, unless --no-actions, the public
GitHub API (unauthenticated: 60 requests/hour; this uses 3).
"""

from __future__ import annotations

import argparse
import ast
import io
import itertools
import json
import os
import re
import statistics
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MODEL_BRANCH, SCREENER_BRANCH = "model-cache", "screener-cache"
MODEL_FILE, META_FILE = "ml_return_predictor.joblib", "ml_return_predictor_meta.json"
SCREENER_FILE = "screener_results.json"

# Every feature the code can produce is the union of these constants.
FEATURE_SOURCES = {
    "src/quantify/strategy/ml_return_predictor.py": ("_ALL_FEATURES", "_SECTOR_FEATURES",
                                                     "_CS_FEATURES"),
    "src/quantify/data/fundamentals.py": ("FUNDAMENTAL_FEATURES",),
    "src/quantify/data/earnings.py": ("EARNINGS_FEATURES",),
}

# Workflow file -> expected hours between runs (from its cron schedule).
WORKFLOWS = {"ml_train.yml": 24, "screener_cron.yml": 1 / 3, "daily_retrain.yml": 24}

MODEL_WARN_HOURS, MODEL_FAIL_HOURS = 36, 60
SCREENER_WARN_HOURS, SCREENER_FAIL_HOURS = 3, 26
MIN_USEFUL_IC = 0.01

NOW = datetime.now(timezone.utc)
results: list[tuple[str, str]] = []


def report(status: str, message: str) -> None:
    results.append((status, message))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def hours_since(moment: datetime) -> float:
    return (NOW - moment).total_seconds() / 3600


def _every(hours: float) -> str:
    return f"{hours * 60:.0f} min" if hours < 1 else f"{hours:g}h"


def repo_slug() -> str | None:
    url = git("remote", "get-url", "origin").strip()
    match = re.search(r"github\.com[:/](.+?/.+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def constants(source: str, names: tuple[str, ...]) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and target.id in names and node.value is not None:
                found |= set(ast.literal_eval(node.value))
    return found


_REGISTRY_SNIPPET = (
    "import json, logging, sys, warnings; logging.disable(50); warnings.simplefilter('ignore');"
    "sys.path.insert(0, sys.argv[1]); import quantify.data.features as f;"
    "print(json.dumps(sorted(f._REGISTRY)))"
)


def registered_features(code_ref: str) -> set[str] | None:
    """Names FeatureEngine registers at import time on code_ref (several are registered in
    loops, so reading the source isn't enough). None if the project env can't import it."""
    archive = subprocess.run(["git", "archive", "--format=tar", code_ref, "src"],
                             check=True, capture_output=True).stdout
    with tempfile.TemporaryDirectory(prefix="model-health-") as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        proc = subprocess.run([sys.executable, "-c", _REGISTRY_SNIPPET, str(Path(tmp, "src"))],
                              capture_output=True, text=True, timeout=180,
                              env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return set(json.loads(proc.stdout.strip().splitlines()[-1]))


def check_model(code_ref: str) -> dict | None:
    try:
        meta = json.loads(git("show", f"origin/{MODEL_BRANCH}:{META_FILE}"))
        size = int(git("cat-file", "-s", f"origin/{MODEL_BRANCH}:{MODEL_FILE}"))
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        report("FAIL", f"model-cache: can't read {META_FILE} / {MODEL_FILE} ({exc})")
        return None

    trained = datetime.fromisoformat(meta["last_train_date"])
    age = hours_since(trained)
    backends = meta.get("model_backends", [])
    status = "FAIL" if age > MODEL_FAIL_HOURS else "WARN" if age > MODEL_WARN_HOURS else "OK"
    report(status, f"model trained {age:.1f}h ago ({trained:%Y-%m-%d %H:%M} UTC), "
                   f"{size / 1e6:.1f} MB, backends: {', '.join(backends) or 'none'}")
    if len(backends) < 3:
        report("WARN", f"ensemble degraded: only {backends} of lgbm/xgboost/catboost loaded")

    # Feature schema: the model must only need features the deployed code produces.
    model_features = set(meta.get("features", []))
    code_features: set[str] = set()
    for path, names in FEATURE_SOURCES.items():
        code_features |= constants(git("show", f"{code_ref}:{path}"), names)
    registered = registered_features(code_ref)
    base = constants(git("show", f"{code_ref}:src/quantify/strategy/ml_return_predictor.py"),
                     ("_ALL_FEATURES",))
    missing, unused = sorted(model_features - code_features), sorted(code_features - model_features)
    unregistered = sorted(base - registered) if registered is not None else []
    if registered is None:
        report("WARN", "feature schema: couldn't import FeatureEngine (project environment "
                       "missing?), so registration of the base features wasn't verified")
    if missing:
        report("FAIL", f"feature schema: model needs {missing}, which {code_ref} no longer "
                       "produces. Inference will drop or zero-fill them (see PR #33).")
    elif unregistered:
        report("FAIL", f"feature schema: {unregistered} are in _ALL_FEATURES but not registered "
                       f"in FeatureEngine on {code_ref}")
    else:
        report("OK", f"feature schema: all {len(model_features)} model features are produced "
                     f"by {code_ref}")
    if unused:
        report("WARN", f"feature schema: {code_ref} defines {unused}, which the model wasn't "
                       "trained on (retrain to use them)")

    metrics = meta.get("model_metrics") or {}
    ic, hit = metrics.get("spearman_ic"), metrics.get("hit_rate")
    if ic is None or hit is None:
        report("WARN", "model quality: no validation metrics in the model metadata")
    else:
        weak = ic <= MIN_USEFUL_IC or hit <= 0.5
        report("WARN" if weak else "OK",
               f"model quality (held-out validation): Spearman IC {ic:+.3f}, hit rate {hit:.1%}"
               + (". No measurable edge: the ranking is no better than chance" if weak else ""))
    return meta


def check_screener(meta: dict | None) -> None:
    try:
        screener = json.loads(git("show", f"origin/{SCREENER_BRANCH}:{SCREENER_FILE}"))
        tip = datetime.fromtimestamp(int(git("log", "-1", "--format=%ct",
                                             f"origin/{SCREENER_BRANCH}").strip()), timezone.utc)
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        report("FAIL", f"screener-cache: can't read {SCREENER_FILE} ({exc})")
        return

    signals = screener.get("signals") or []
    age = hours_since(tip)
    if screener.get("status") != "ok" or not signals:
        report("FAIL", f"screener: status={screener.get('status')!r}, {len(signals)} signals. "
                       "/predict has nothing to show")
    else:
        status = ("FAIL" if age > SCREENER_FAIL_HOURS else
                  "WARN" if age > SCREENER_WARN_HOURS else "OK")
        report(status, f"screener: {len(signals)} signals for {screener.get('date')} "
                       f"({screener.get('mode')}, universe {screener.get('universe_size')}), "
                       f"updated {age:.1f}h ago")
    if (screener.get("universe_size") or 0) < 400:
        report("WARN", f"screener universe is only {screener.get('universe_size')} symbols "
                       "(expected ~500)")
    if meta and screener.get("model_metrics") not in (None, meta.get("model_metrics")):
        report("WARN", "screener results came from a different model than model-cache holds "
                       "(stale screener, or caught mid-update)")


def check_actions(slug: str) -> None:
    for workflow, expected_gap_h in WORKFLOWS.items():
        url = (f"https://api.github.com/repos/{slug}/actions/workflows/{workflow}"
               "/runs?per_page=10")
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"Accept": "application/vnd.github+json"}), timeout=20) as resp:
                runs = json.load(resp).get("workflow_runs", [])
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                report("WARN", "GitHub Actions: skipped, unauthenticated API rate limit hit "
                               "(60/hour). Re-run later or pass --no-actions")
                return
            report("WARN", f"GitHub Actions: {workflow}: HTTP {exc.code}")
            continue
        except OSError as exc:
            report("WARN", f"GitHub Actions: can't reach api.github.com ({exc})")
            return
        if not runs:
            report("WARN", f"{workflow}: no runs found")
            continue

        latest = runs[0]
        created = [datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in runs]
        gaps = [(a - b).total_seconds() / 3600 for a, b in itertools.pairwise(created)]
        median_gap = statistics.median(gaps) if gaps else float("nan")
        failures = sum(r["conclusion"] == "failure" for r in runs)
        conclusion = latest["conclusion"] or latest["status"]
        detail = (f"{workflow}: last run {conclusion} {hours_since(created[0]):.1f}h ago, "
                  f"{failures}/{len(runs)} recent runs failed, median gap {median_gap:.1f}h "
                  f"(scheduled every {_every(expected_gap_h)})")
        if conclusion == "failure":
            report("FAIL", detail + f". {latest['html_url']}")
        elif failures >= 2 or hours_since(created[0]) > max(2 * expected_gap_h, 3):
            report("WARN", detail)
        else:
            report("OK", detail)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--code", default="origin/main",
                        help="code revision the deployed API runs (default origin/main)")
    parser.add_argument("--no-actions", action="store_true",
                        help="skip the GitHub Actions run history (saves API calls)")
    args = parser.parse_args()

    fetch = subprocess.run(["git", "fetch", "-q", "origin", "main", MODEL_BRANCH, SCREENER_BRANCH],
                           capture_output=True, text=True)
    if fetch.returncode != 0:
        report("WARN", "git fetch failed; checking the last fetched copies: "
                       + (fetch.stderr.strip().splitlines() or ["?"])[-1])

    meta = check_model(args.code)
    check_screener(meta)
    slug = repo_slug()
    if not args.no_actions and slug:
        check_actions(slug)

    print(f"model-health ({NOW:%Y-%m-%d %H:%M} UTC, code {args.code})")
    for status, message in results:
        print(f"[{status:<4}] {message}")
    fails = sum(s == "FAIL" for s, _ in results)
    warns = sum(s == "WARN" for s, _ in results)
    print(f"\nRESULT: {fails} FAIL, {warns} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
