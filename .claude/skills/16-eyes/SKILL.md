---
name: 16-eyes
description: Skeptical merge review of a Quantify PR, branch or diff against this repo's invariants, including protected areas, the API contract with web/, the model-cache and screener-cache data branches, and the fact that main deploys to Heroku and Vercel. Maps the diff to risk areas with a script, then verifies each claim by running checks instead of trusting the PR description or a CI badge. Use when asked to review a PR or branch, to decide whether something is safe to merge, or before pushing to main.
argument-hint: "[branch | base...head]"
---

# 16-eyes: review it like it's going to production (merging to main deploys it)

1. **Map the diff:**
   ```bash
   git fetch origin
   python ${CLAUDE_SKILL_DIR}/areas.py $ARGUMENTS
   ```
   With no argument it maps this branch against `origin/main`, plus uncommitted work. For a PR, pass `origin/<branch>`.
2. **Apply each area's lens** (below), and run the checks the script prints.
3. **Trace the data flow** for anything touching money or messages. Follow it from input (API request, Telegram command, workflow callback) through validation, strategy, risk and execution, then persistence and notification. At each step, ask what empty, malformed, duplicated or hostile input does, and who can send it.
4. **Verify, don't trust.** Reproduce CI locally with `ruff check .` and `pytest`, plus `cd web && npm run build` if `web/` changed. A red CI can be environmental, like an unpinned tool. A green one may have skipped steps. Confirm a suspected bug with a small script or failing test before reporting it.
5. **Report:** give the verdict first (merge, fix first, or don't merge). Then rank findings by severity, each with `file:line`, a concrete failure scenario and the evidence (probe output or a failing test). Say what's good, too.

## Lenses

- **Trading logic:** run crosscheck (`--head origin/<branch>` works without checking out). Sizing, risk limits and cost units (a fraction vs bps) stay unchanged unless the PR says otherwise.
- **ML:** the `_ALL_FEATURES` list is locked to the persisted model (`areas.py` flags changes to it). Check model file paths and the model-cache download.
- **API contract:** compare request and response fields with `web/src/lib/api.ts` and the pages that use them. Metadata values must be scalars or lists. Responses must not carry raw exception text or server environment details.
- **Security:** run deep-security-check. Internal routes must call `_verify_secret`. There should be no new unauthenticated writes, and GET must not change state.
- **Data branches:** `model-cache` and `screener-cache` are written only by `ml_train.yml` and `screener_cron.yml`. Never merge or delete them.
- **Deploy:** main deploys to Vercel and Heroku. Keep within Heroku's 512 MB: no heavy imports or work on bot or paper-trading paths, and no new runtime dependencies without a reason.
- **Protected areas** (CLAUDE.md "What not to touch"): `engine.py`, the ML pipeline and features, Telegram notification logic, and the DB schema. Flag any change there the user didn't ask for.
- **Bugs that look pre-existing:** flag them separately. Don't fold fixes for them into the PR silently.
