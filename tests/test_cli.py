from __future__ import annotations

from quantify.cli import _sanitize_argv


def test_sanitize_argv_removes_shell_continuation_tokens() -> None:
    argv = [
        "backtest",
        "`",
        "--strategy",
        "trend_following",
        "   ",
        "^",
        "--start",
        "2025-01-01",
    ]

    assert _sanitize_argv(argv) == [
        "backtest",
        "--strategy",
        "trend_following",
        "--start",
        "2025-01-01",
    ]