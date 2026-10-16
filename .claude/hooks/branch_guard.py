"""Claude Code PreToolUse guard: nothing reaches production or the data branches without
the user.

main deploys on every push (Vercel serves web/, Heroku runs the API), and model-cache /
screener-cache are written only by GitHub Actions and read by the live /predict API.
For Bash and PowerShell tool calls this blocks:

  * git push that updates main or master: an explicit refspec, HEAD while main is checked
    out, an implicit push from main, or --all / --branches / --mirror
  * force pushes (--force, -f, --force-with-lease, --force-if-includes, +refspec) and
    --prune, which deletes remote branches
  * any push to, or deletion of, model-cache or screener-cache
  * merging into main from the command line: gh pr merge, or a GitHub API call that merges
    or rewrites one of those refs

Reads the hook JSON on stdin. Exit 2 with the reason on stderr blocks the call (Claude
sees the reason); exit 0 allows it. Tests: tests/test_tooling/test_branch_guard.py
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys

DEPLOY_BRANCHES = {"main", "master"}
DATA_BRANCHES = {"model-cache", "screener-cache"}
PROTECTED = DEPLOY_BRANCHES | DATA_BRANCHES

FORCE_FLAGS = {"--force", "--force-with-lease", "--force-if-includes"}
ALL_BRANCH_FLAGS = {"--all", "--branches", "--mirror"}
PUSH_VALUE_OPTIONS = {"--repo", "-o", "--push-option", "--receive-pack", "--exec"}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                     "--config-env"}
SHELLS = {"bash", "sh", "zsh", "dash", "pwsh", "powershell", "pwsh.exe", "powershell.exe",
          "bash.exe", "cmd", "cmd.exe"}
WRAPPERS = {"command", "builtin", "exec", "env", "nohup", "time", "sudo", "nice", "xargs"}
SEPARATORS = {"&&", "||", ";", "|", "&", "\n", "(", ")", ";;", "|&"}

MERGE_API = re.compile(
    r"repos/[^/\s'\"]+/[^/\s'\"]+/(?:pulls/\d+/merge\b|merges\b|git/refs/heads/"
    r"(?:main|master|model-cache|screener-cache)\b)"
)
WRITE_FLAGS = {"-X", "--request", "--method", "-d", "--data", "--data-raw", "-f", "-F",
               "--field", "--raw-field", "--input"}

WHY_DEPLOY = ("main deploys to production on every push (Vercel + Heroku). Push a branch "
              "and let the user merge the PR")
WHY_DATA = ("model-cache and screener-cache are written only by GitHub Actions and read by "
            "the live /predict API")
WHY_FORCE = "force pushes rewrite shared history"


def strip_heredocs(command: str) -> str:
    """Drop heredoc bodies (commit messages etc.) so their text isn't parsed as commands."""
    out, lines, i = [], command.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        match = re.search(r"(?<!<)<<-?(?!<)\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", line)
        if match:
            i += 1
            while i < len(lines) and lines[i].strip() != match.group(1):
                i += 1
        i += 1
    return "\n".join(out)


def split_commands(command: str) -> list[list[str]]:
    lexer = shlex.shlex(strip_heredocs(command), posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token in SEPARATORS or set(token) <= set("();<>|&\n"):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def unwrap(tokens: list[str]) -> list[str]:
    """Skip env assignments and wrappers such as `timeout 120` or `env`."""
    i = 0
    while i < len(tokens):
        word = tokens[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word in WRAPPERS:
            i += 1
        elif word == "timeout":
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 1
            i += 1  # the duration
        else:
            break
    return tokens[i:]


def current_branch(directory: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", directory, "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def check_push(args: list[str], directory: str) -> str | None:
    positionals, dry_run, delete = [], False, False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            positionals.extend(args[i + 1:])
            break
        name = arg.split("=", 1)[0]
        if name in PUSH_VALUE_OPTIONS:
            i += 1 if "=" in arg else 2
            continue
        if name in FORCE_FLAGS:
            return WHY_FORCE + f" ({arg})"
        if name == "--prune":
            return ("--prune deletes remote branches that don't exist locally, such as "
                    "model-cache and screener-cache, which the live /predict API reads")
        if name in ALL_BRANCH_FLAGS:
            return f"{arg} would push every branch including main, and " + WHY_DEPLOY
        if name == "--dry-run":
            dry_run = True
        elif name == "--delete":
            delete = True
        elif re.match(r"^-[A-Za-z]+$", arg):  # short flag cluster, e.g. -uf
            if "f" in arg:
                return WHY_FORCE + f" ({arg})"
            dry_run = dry_run or "n" in arg
            delete = delete or "d" in arg
        elif not arg.startswith("-"):
            positionals.append(arg)
        i += 1
    if dry_run:
        return None  # nothing is pushed

    refspecs = positionals[1:]
    branch = current_branch(directory)
    if not refspecs:
        if branch in DEPLOY_BRANCHES:
            return f"this would push the checked-out branch ({branch}), and " + WHY_DEPLOY
        if branch in DATA_BRANCHES:
            return f"this would push the checked-out branch ({branch}), and " + WHY_DATA
        return None

    for spec in refspecs:
        if spec.startswith("+"):
            return WHY_FORCE + f" ({spec})"
        src, has_dst, dst = spec.partition(":")
        target = dst if has_dst else src
        if delete or (has_dst and not src):
            action = "delete"
        else:
            action = "update"
        target = re.sub(r"^refs/heads/", "", target)
        if target in ("HEAD", "@"):
            target = branch or target
        if "*" in target:
            return f"wildcard refspec {spec!r} could update main, and " + WHY_DEPLOY
        if target in DEPLOY_BRANCHES:
            return f"{spec!r} would {action} {target}, and " + WHY_DEPLOY
        if target in DATA_BRANCHES:
            return f"{spec!r} would {action} {target}, and " + WHY_DATA
    return None


def check_command(tokens: list[str], cwd: str, depth: int = 0) -> str | None:
    tokens = unwrap(tokens)
    if not tokens:
        return None
    program = os.path.basename(tokens[0]).lower()

    # Commands handed to another shell or to eval: check the inner command too.
    if depth < 3 and (program in SHELLS or program == "eval"):
        for j, arg in enumerate(tokens[1:], 1):
            if program == "eval" or arg.lower() in ("-c", "/c", "-command", "/k"):
                inner = " ".join(tokens[j:]) if program == "eval" else " ".join(tokens[j + 1:])
                return check(inner, cwd, depth + 1)

    if program in ("git", "git.exe"):
        directory, i = cwd, 1
        while i < len(tokens) and tokens[i].startswith("-"):
            name = tokens[i].split("=", 1)[0]
            if name == "-C" and i + 1 < len(tokens):
                directory = os.path.join(cwd, tokens[i + 1])
            i += 2 if name in GIT_VALUE_OPTIONS and "=" not in tokens[i] else 1
        if i < len(tokens) and tokens[i] == "push":
            return check_push(tokens[i + 1:], directory)
        return None

    touches_protected_api = any(MERGE_API.search(t) for t in tokens)
    writes = any(t.split("=", 1)[0] in WRITE_FLAGS or t.lower() in ("-method", "-body")
                 for t in tokens)
    if program in ("gh", "gh.exe") and tokens[1:3] == ["pr", "merge"]:
        return "gh pr merge would merge into main, and " + WHY_DEPLOY
    if program in ("gh", "gh.exe", "curl", "curl.exe", "wget", "invoke-restmethod",
                   "invoke-webrequest", "irm", "iwr", "http", "https") \
            and touches_protected_api and writes:
        return "this GitHub API call merges or rewrites a protected branch"
    return None


def check(command: str, cwd: str, depth: int = 0) -> str | None:
    """Reason to block `command`, or None to allow it."""
    try:
        commands = split_commands(command)
    except ValueError:  # unbalanced quotes: fail closed only if it looks like a push/merge
        if re.search(r"\bgit\b.*\bpush\b|\bgh\b.*\bmerge\b|/merges?\b", command, re.S):
            return "couldn't parse this push/merge command safely"
        return None
    for tokens in commands:
        reason = check_command(tokens, cwd, depth)
        if reason:
            return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or os.getcwd()
    reason = check(command, cwd)
    if reason:
        print(f"branch-guard blocked this command: {reason}. If the user wants it anyway, "
              "they can run it themselves. Rules: .claude/hooks/branch_guard.py",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
