"""Prove a regression test catches its bug: it must FAIL on the code without the fix and
PASS with the fix.

Usage (from the repo root, with the project's Python environment):
    python .claude/skills/never-again/prove_regression.py TEST_NODE [TEST_NODE ...] [--base REV]

TEST_NODE is a pytest node id, e.g. tests/test_data/test_x.py::test_name.
--base is the revision WITHOUT the fix (default HEAD: the fix is still uncommitted).
Test files (and tests/conftest.py) always come from the working tree, so new tests work.

Exit code 0 when the test fails on base and passes on the fix, 1 otherwise.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True).stdout


def _copy_working_tree(repo: Path, dest: Path) -> None:
    listing = _git(repo, "ls-files", "-z", "-co", "--exclude-standard").decode("utf-8")
    for rel in filter(None, listing.split("\0")):
        src = repo / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)


def _pytest(tree: Path, nodes: list[str]) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    env.setdefault("JWT_SECRET", "test-secret")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", *nodes],
        cwd=tree, env=env, capture_output=True, text=True, timeout=1800,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _kind_of_failure(output: str) -> str:
    if re.search(r"ERROR collecting|ImportError|ModuleNotFoundError|fixture '.*' not found", output):
        return "collection/import error"
    if re.search(r"AssertionError|^E\s+assert|Failed: DID NOT RAISE", output, re.M):
        return "assertion failure"
    return "exception during the test"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("nodes", nargs="+", help="pytest node ids")
    parser.add_argument("--base", default="HEAD", help="revision without the fix")
    args = parser.parse_args()

    repo = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
    test_files = sorted({node.split("::")[0] for node in args.nodes})
    for rel in test_files:
        if not (repo / rel).is_file():
            parser.error(f"no such test file in the working tree: {rel}")

    with tempfile.TemporaryDirectory(prefix="never-again-") as tmp:
        base_tree, fixed_tree = Path(tmp, "base"), Path(tmp, "fixed")
        with tarfile.open(fileobj=io.BytesIO(_git(repo, "archive", "--format=tar", args.base))) as tar:
            tar.extractall(base_tree, filter="data")
        for rel in [*test_files, "tests/conftest.py"]:
            if (repo / rel).is_file():
                (base_tree / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo / rel, base_tree / rel)
        _copy_working_tree(repo, fixed_tree)

        base_code, base_out = _pytest(base_tree, args.nodes)
        fixed_code, fixed_out = _pytest(fixed_tree, args.nodes)

    base_sha = _git(repo, "rev-parse", "--short", args.base).decode().strip()
    print(f"never-again: {', '.join(args.nodes)}")
    if base_code == 0:
        print(f"  base {args.base} ({base_sha}): PASSED  <-- the test doesn't catch the bug")
    else:
        print(f"  base {args.base} ({base_sha}): failed ({_kind_of_failure(base_out)})")
    print(f"  working tree (with fix): {'passed' if fixed_code == 0 else 'FAILED'}")

    ok = base_code != 0 and fixed_code == 0

    def tail(text: str) -> str:
        return "\n".join(text.strip().splitlines()[-30:])

    if base_code != 0 and _kind_of_failure(base_out) == "collection/import error":
        print("\nNote: on base the test fails before it runs (import/collection). It may only be")
        print("depending on new code. Make sure it fails because of the bug itself.")
        print("\n--- pytest output (base) ---\n" + tail(base_out))
    if fixed_code != 0:
        print("\n--- pytest output (working tree) ---\n" + tail(fixed_out))
    print("\nRESULT: " + ("proven. Fails without the fix, passes with it." if ok else "not proven."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
