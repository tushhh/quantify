"""Tests for the Claude Code branch guard (.claude/hooks/branch_guard.py).

main deploys to production on every push, and model-cache / screener-cache feed the live
/predict API, so the guard must block anything that would update them and allow the rest.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("branch_guard", HOOKS / "branch_guard.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("repo")
    git = ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
    subprocess.run([*git, "branch", "feature"], check=True)
    return path


def checkout(repo: Path, branch: str) -> None:
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", branch], check=True)


BLOCKED = [
    "git push origin main",
    "git push origin master",
    "git push origin HEAD:refs/heads/main",
    "cd x && GIT_TERMINAL_PROMPT=0 timeout 120 git push origin HEAD:main 2>&1 | tail -3",
    "git push origin feature:main",
    "git push origin :main",
    "git -C . push origin main",
    "git push --all origin",
    "git push --mirror origin",
    "git push --force origin feature",
    "git push -uf origin feature",
    "git push origin +feature",
    "git push --force-with-lease origin feature",
    "git push --prune origin 'refs/heads/*:refs/heads/*'",
    "git push origin --delete model-cache",
    "git push -d origin screener-cache",
    "git push origin feature:model-cache",
    "git push origin --delete pick-history",
    "git push origin feature:pick-history",
    'bash -c "git push origin main"',
    'powershell -Command "git push origin main; Write-Host done"',
    "git status\ngit push origin main",
    "gh pr merge 36 --squash",
    "gh api repos/o/r/pulls/36/merge -X PUT",
    "curl -X PATCH https://api.github.com/repos/o/r/git/refs/heads/main -d '{}'",
]

ALLOWED = [
    "git push origin HEAD:refs/heads/feature",
    "git push -u origin feature",
    "git push --dry-run origin main",
    "git push origin v1.0 --tags",
    "git log --oneline main..HEAD",
    "git fetch origin main model-cache",
    "git commit -F - <<'EOF'\nnever run git push origin main\nEOF",
    "echo 'git push origin main'",
    "gh pr create --base main --title x --body y",
    "gh api repos/o/r/pulls/36",
    "curl -s https://api.github.com/repos/o/r/pulls/36/merge",
]


@pytest.mark.parametrize("command", BLOCKED)
def test_blocks_anything_that_updates_main_or_the_data_branches(command, repo) -> None:
    checkout(repo, "feature")
    assert guard.check(command, str(repo)) is not None


@pytest.mark.parametrize("command", ALLOWED)
def test_allows_everything_else(command, repo) -> None:
    checkout(repo, "feature")
    assert guard.check(command, str(repo)) is None


@pytest.mark.parametrize("command", ["git push", "git push origin", "git push origin HEAD"])
def test_implicit_push_is_blocked_only_while_main_is_checked_out(command, repo) -> None:
    checkout(repo, "main")
    assert guard.check(command, str(repo)) is not None
    checkout(repo, "feature")
    assert guard.check(command, str(repo)) is None


def _payload(command: str, cwd: Path) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})


def test_hook_blocks_with_exit_code_2_and_a_reason(repo) -> None:
    checkout(repo, "feature")
    run = lambda cmd: subprocess.run(  # noqa: E731
        [sys.executable, str(HOOKS / "branch_guard.py")], input=_payload(cmd, repo),
        capture_output=True, text=True)
    blocked = run("git push origin main")
    assert blocked.returncode == 2
    assert "branch-guard blocked" in blocked.stderr
    assert run("git status").returncode == 0


@pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"),
                    reason="the bash entry point is exercised on Linux CI")
def test_bash_entry_point(repo) -> None:
    checkout(repo, "feature")
    run = lambda cmd: subprocess.run(  # noqa: E731
        ["bash", str(HOOKS / "branch-guard.sh")], input=_payload(cmd, repo),
        capture_output=True, text=True)
    assert run("git push origin main").returncode == 2
    assert run("git push origin feature").returncode == 0
    assert run("ls -la").returncode == 0  # prefilter: Python never starts
