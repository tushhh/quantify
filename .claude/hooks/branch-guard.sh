#!/usr/bin/env bash
# PreToolUse hook entry point (wired up in .claude/settings.json).
# Cheap prefilter so ordinary commands never start Python; the rules live in branch_guard.py.
input=$(cat)
case "$input" in
  *push*|*merge*|*/git/refs/*) ;;
  *) exit 0 ;;
esac

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
for py in python3 python py; do
  # Skip launchers that exist but don't run (e.g. the Windows Store python3 stub).
  if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys; sys.exit(sys.version_info < (3, 8))" >/dev/null 2>&1; then
    printf '%s' "$input" | "$py" "$here/branch_guard.py"
    exit $?
  fi
done
echo "branch-guard: no Python 3 found, so this push/merge command is blocked. Ask the user to run it." >&2
exit 2
