---
name: model-health
description: Health check for Quantify's live ML pipeline. Checks the model in model-cache (age, ensemble backends, an exact feature-schema match against the deployed code), its held-out validation quality (Spearman IC, hit rate), the screener-cache output (freshness, signal count), and recent GitHub Actions runs of ml_train, screener_cron and daily_retrain. Use when the user asks whether predictions are stale, broken or any good, when /predict shows nothing, after changing features or the training pipeline, or on a daily schedule.
argument-hint: "[--code REF] [--no-actions]"
---

# model-health: is the live ML signal fresh, consistent, and worth anything?

## Run it

```bash
python ${CLAUDE_SKILL_DIR}/check.py                 # checks against the deployed code, origin/main
python ${CLAUDE_SKILL_DIR}/check.py --code HEAD     # would this branch still match the live model?
python ${CLAUDE_SKILL_DIR}/check.py --no-actions    # skip the GitHub API (60 calls/hour unauthenticated)
```

Exit code 1 on any FAIL. It reads the data branches with `git fetch`, so it needs network but no token. The feature-registration check imports FeatureEngine, so run it with the project environment (setup is in the crosscheck skill). Without that environment, that one check is skipped with a WARN.

## What each line means

- **model trained Xh ago:** `ml_train.yml` runs daily at 05:00 UTC, and GitHub often starts it hours late. WARN after 36h, FAIL after 60h.
- **feature schema:** every feature the model was trained on must still be produced by the code. If one isn't, that's a FAIL. This is the bug that silently killed the ML sleeve in PR #33. Features the code defines but the model wasn't trained on are a WARN: retraining would use them.
- **model quality (held-out validation):** from the training run's validation split. An IC at or below 0.01, or a hit rate at or below 50%, means the ranking has no measurable edge. The pipeline can be perfectly healthy while the model is useless, so say that plainly.
- **screener:** the signals `/predict` serves. FAIL if there are none. WARN if the branch is more than 3h old, FAIL after 26h. A WARN that the screener used a different model means it ran before the latest training.
- **workflow lines:** the last run's conclusion, failures in the last 10 runs, and the real cadence. `screener_cron` is scheduled every 20 minutes, but GitHub throttles it: the median gap was about 4h in October 2026.

## On a failure

- Quote the FAIL lines, then investigate read-only: the failing run's page, and the model metadata (`git show origin/model-cache:ml_return_predictor_meta.json`).
- Don't push to model-cache or screener-cache, and don't edit the training pipeline or feature definitions to make a mismatch go away. CLAUDE.md puts both off-limits, and the branch-guard hook blocks the pushes. Explain the cause and the fix (usually a retrain with `ml_train.yml`), and let the user decide.

## Schedule it

It already runs on a schedule: `.github/workflows/model_health.yml` runs it every weekday at 12:30 UTC, and on demand from the Actions tab. Each run puts the report in its job summary, and the job fails (so GitHub emails you) on any FAIL. When the user asks how the model has been doing, read recent runs there before re-running the check locally.
