---
name: deep-security-check
description: Security audit for the Quantify repo, which is public. Scans for committed secrets and sensitive files, checks every FastAPI route's authentication (internal routes must call _verify_secret, and unauthenticated routes that change state or return user identifiers are flagged), finds secrets passed through workflow_dispatch inputs, and with --deps audits Python and npm dependencies. Use before merging changes to api/, auth, workflows, the Dockerfile/Procfile or dependencies, or when asked for a security review.
argument-hint: "[--deps] [--all]"
---

# deep-security-check

## Run it

From the repo root:

```bash
python ${CLAUDE_SKILL_DIR}/scan.py           # secrets, route auth, workflow secrets
python ${CLAUDE_SKILL_DIR}/scan.py --deps    # plus pip-audit (via uvx) and npm audit; needs network
python ${CLAUDE_SKILL_DIR}/scan.py --all     # also list INFO findings (public read-only routes)
```

Exit code 1 when anything is HIGH. Matched secret values are redacted. Never print a full secret in your reply either.

## Triage every finding

- **Real secret in the repo (HIGH):** the repo is public, so it's already leaked, history included. Tell the user to **rotate it first**. Then move it to an environment variable. Removing it from the code doesn't un-leak it.
- **Internal route without `_verify_secret` (HIGH):** add `_verify_secret(x_internal_secret or secret)`, plus a test like `tests/test_api/test_internal_auth.py`.
- **Unauthenticated route that changes state (MEDIUM):** decide with the user whether it should be public. If it stays public, make sure it can't be abused, for example by triggering paid work, spamming Telegram, or overwriting data. Sign-up and sign-in are allowlisted in the script.
- **Secret as a `workflow_dispatch` input (MEDIUM):** inputs aren't masked like `${{ secrets.* }}`. The workflow should read the repo secret, and callers should send an empty value, as `api/routers/backtest.py` does.
- **State change on GET (LOW):** link previews and crawlers can trigger it. Prefer POST, or keep it behind the secret.
- **Raw exception text in `detail=` (LOW):** CLAUDE.md says never show backend errors in the UI. Log the exception and return a specific, user-safe message.
- **Vulnerable dependency (`--deps`):** report the package, the advisory and the fixed version. Don't bump pinned packages (for example `bcrypt==3.2.2`, which passlib needs) without checking why they're pinned.

The scanner is heuristic. Confirm each finding by reading the code before you report it, and note anything it can't see (business-logic authorization, rate limiting).

Known open findings, as of October 2026, for the user to decide on:

- `api/prediction_bot.py` passes the live `INTERNAL_API_SECRET` as a `workflow_dispatch` input to `full_screener.yml`.
- `POST /api/backtest` is unauthenticated and can dispatch GitHub Actions runs.
- `GET /api/backtest/result/{job_id}` returns raw exception text.

For a review of just the current diff, the built-in `/security-review` complements this scan.
