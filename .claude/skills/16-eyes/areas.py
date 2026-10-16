"""Map a diff onto Quantify's risk areas and list the checks each one needs.

Usage (from the repo root):
    python .claude/skills/16-eyes/areas.py                      # this branch vs origin/main + uncommitted
    python .claude/skills/16-eyes/areas.py origin/some-branch   # that branch vs origin/main
    python .claude/skills/16-eyes/areas.py A...B                # any range
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

SKILLS = ".claude/skills"
CROSSCHECK = f"python {SKILLS}/crosscheck/parity.py --base <base> [--head <head>]"
FEATURES = f"python {SKILLS}/pandas-ta-executor/check_features.py"
SECURITY = f"python {SKILLS}/deep-security-check/scan.py"

# (path regex, area, why it matters, checks to run). A file can match several areas.
RULES = [
    (r"^src/quantify/backtest/engine\.py$", "Backtest engine core",
     "CLAUDE.md: do not touch without being asked", [CROSSCHECK]),
    (r"^src/quantify/(strategy|risk|execution|backtest)/", "Trading logic",
     "changes P&L and risk; prove there's no unintended drift", [CROSSCHECK]),
    (r"^src/quantify/data/features\.py$|^src/quantify/strategy/ml_return_predictor\.py$",
     "ML features / model inputs",
     "the persisted model is locked to its feature list; changing it needs retraining", [FEATURES]),
    (r"^src/quantify/data/(provider|providers/|cache|universe|fundamentals|earnings|sector)",
     "Market data pipeline",
     "changes what every backtest, screener and prediction sees; crosscheck uses synthetic "
     "data and won't catch it",
     ["run one real backtest before/after; compare run_id and skipped_symbols"]),
    (r"^\.github/workflows/(ml_train|daily_retrain|walk_forward)\.ya?ml$|^scripts/\w*train",
     "ML training pipeline", "CLAUDE.md: do not touch without being asked", []),
    (r"^\.github/workflows/", "CI/CD and scheduled pipelines",
     "run from main; ml_train/screener_cron write the model-cache and screener-cache branches",
     ["check no workflow stops writing, or starts deleting, model-cache / screener-cache"]),
    (r"^api/schemas\.py$|^api/routers/", "API contract",
     "web/src/lib/api.ts and the pages using it must still match; metadata values must be "
     "scalars or lists (the web card prints String(v))",
     ["compare changed request/response fields with web/src/lib/api.ts"]),
    (r"^api/routers/(internal|auth)\.py$|^api/(database|models)\.py$",
     "Auth, internal callbacks, DB schema",
     "internal routes must call _verify_secret; schema changes need explicit instruction",
     [SECURITY]),
    (r"^api/(prediction_bot|telegram_bot|gain_scanner|hold_health|trade_service)\.py$",
     "Telegram bots and notifications",
     "CLAUDE.md: do not touch notification logic without being asked", [SECURITY]),
    (r"(^|/)requirements\.txt$|^pyproject\.toml$|^web/package(-lock)?\.json$|^dockerfile$"
     r"|^Procfile$|^\.python-version$",
     "Dependencies and deploy config",
     "Heroku 512 MB memory; no minor-version pins (CLAUDE.md known issues)",
     [f"{SECURITY} --deps"]),
    (r"^web/vercel\.json$", "Vercel config",
     "CLAUDE.md known issue: understand the existing setup before changing it",
     ["cd web && npm run build"]),
    (r"^web/", "Frontend", "design system and copy rules in CLAUDE.md", ["cd web && npm run build"]),
    (r"^CLAUDE\.md$|^\.claude/", "Agent instructions", "changes how future agents behave", []),
]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def changed_files(target: str | None) -> tuple[str, list[str], str | None]:
    if target and "..." in target:
        label, rng = target, target
    elif target:
        label, rng = f"origin/main...{target}", f"origin/main...{target}"
    else:
        label, rng = "origin/main...HEAD + uncommitted", "origin/main...HEAD"
    files = set(_git("diff", "--name-only", rng).split())
    if not target:
        files |= set(_git("diff", "--name-only", "HEAD").split())
        files |= set(_git("ls-files", "-o", "--exclude-standard").split())
    head = rng.partition("...")[2] or "HEAD"
    return label, sorted(files), head if target else None


def ml_feature_change(rng_head: str | None) -> str | None:
    """Compare _ALL_FEATURES in ml_return_predictor.py between origin/main and the head."""
    path = "src/quantify/strategy/ml_return_predictor.py"

    def features(source: str) -> list[str]:
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                target = node.targets[0] if isinstance(node, ast.Assign) else node.target
                if isinstance(target, ast.Name) and target.id == "_ALL_FEATURES":
                    return [ast.literal_eval(e) for e in node.value.elts]
        return []

    try:
        before = features(_git("show", f"origin/main:{path}"))
        after_src = _git("show", f"{rng_head}:{path}") if rng_head else Path(path).read_text(
            encoding="utf-8")
        after = features(after_src)
    except (subprocess.CalledProcessError, OSError, ValueError, SyntaxError):
        return None
    added, removed = sorted(set(after) - set(before)), sorted(set(before) - set(after))
    if not added and not removed:
        return None
    return f"_ALL_FEATURES changed: +{added} -{removed}. The persisted model needs retraining."


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    label, files, head = changed_files(target)
    print(f"16-eyes: {len(files)} files changed ({label})\n")
    if not files:
        print("Nothing to review.")
        return 0

    matched: dict[str, dict] = {}
    unmatched = []
    for path in files:
        hits = [rule for rule in RULES if re.search(rule[0], path)]
        if not hits:
            unmatched.append(path)
        for _, area, why, checks in hits:
            entry = matched.setdefault(area, {"why": why, "checks": checks, "files": []})
            entry["files"].append(path)

    for area, entry in matched.items():
        print(f"## {area}\n   why: {entry['why']}")
        for path in entry["files"]:
            print(f"   - {path}")
        for check in entry["checks"]:
            print(f"   run: {check}")
        print()
    if unmatched:
        print("## Other files")
        for path in unmatched:
            print(f"   - {path}")
        print()

    if any(f.startswith("src/quantify/strategy/ml_return_predictor.py") for f in files):
        note = ml_feature_change(head)
        if note:
            print(f"!! {note}\n")

    print("Always: ruff check . && pytest (what CI runs). Merging to main deploys the API to")
    print("Heroku and the web app to Vercel. Never merge or delete model-cache / screener-cache.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
