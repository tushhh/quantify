---
name: grill-me
description: Interview the user, one round of questions at a time, until a Quantify plan or design is fully specified before any code is written. Use when the user types /grill-me or asks to be grilled on a plan.
disable-model-invocation: true
---

# grill-me

The method is adapted from Matt Pocock's grill-me and grilling skills ([mattpocock/skills](https://github.com/mattpocock/skills), MIT).

Interview the user until you both understand the plan the same way. Treat it as a **design tree**: each decision opens up the decisions that depend on it.

**Work in rounds.** Ask every question whose prerequisites are already settled, all in one round. Number them, give your recommended answer for each, and word each one so that "yes" accepts your recommendation. Wait for the answers, recompute what's now open, and ask the next round. A question that depends on another question still open in the same round belongs in a later round.

**Finding facts is your job.** Look up anything the code, git history, CI runs or GitHub can tell you. Use a subagent for big searches, and keep asking the rest of the round while it runs. Only decisions go to the user.

**You're done** when nothing is left open or silently assumed. Summarise the agreed plan, and don't write code until the user confirms it.

## Seed the tree with Quantify's high-stakes branches

Ask only about the ones the plan touches:

- **Outcome:** what changes for the trader, and how we'll know it worked (a metric, a test, a screenshot).
- **Money and risk:** backtest, paper or live? Position sizing, drawdown limits, sector caps, and cost units (a fraction vs bps).
- **Protected areas:** does it touch `engine.py`, the ML pipeline or feature list (meaning a retrain), Telegram notification logic, the DB schema (meaning a migration), or the API contract (and so the consumers of `web/src/lib/api.ts`)?
- **Data:** universe and survivorship bias, the date range and lookahead, the data provider, and whether it involves model-cache or screener-cache.
- **Deploy:** main deploys to Vercel and Heroku. What's the Heroku memory budget, and the rollback plan?
- **Done means:** a regression test (never-again), backtest parity (crosscheck), a security scan (deep-security-check), `npm run build`, and green CI.
