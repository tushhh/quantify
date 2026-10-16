---
name: backtest-doctor
description: Sanity-check a Quantify backtest result before trusting it. Flags the failure modes this repo has actually hit, such as cost units (5% slippage typed as 0.05), strategies that never traded (a silently dead ML sleeve), lookahead from the cached ML model or live VIX, survivorship bias, dropped symbols, trading costs larger than the edge, too few trades, and results that hang on a handful of trades. Use when the user shares a backtest result, asks whether one is believable, or a result looks too good or too bad.
argument-hint: "[result.json | --job ID --api URL]"
---

# backtest-doctor

## Get the result

- **From the web app:** open DevTools, go to Network, find the `result/<job_id>` request, and save its response to a file.
- **From the API:** `curl -s "$API/api/backtest/result/<job_id>" > result.json`. Or let the script fetch it with `--job <job_id> --api <base url>` (the default is `$QUANTIFY_API_URL`, else `http://localhost:8000`).

## Run it

```bash
python ${CLAUDE_SKILL_DIR}/doctor.py result.json
```

It uses only the standard library, so no project environment is needed. Exit code 1 on any FAIL.

## Reading the findings

- **FAIL:** the number isn't meaningful until this is fixed. Examples are a cost-units error, or the ML sleeve never trading.
- **WARN:** the result is biased or fragile. Say which way it pushes: lookahead and survivorship flatter returns, while excess costs depress them.
- **INFO:** context, such as estimated cost drag, the return against the benchmark, and the run_id for reproducing the run.

Then:

- Explain each FAIL and WARN in trader terms, with the concrete fix: the request field to change, or the check to re-run.
- For a dead ML sleeve, run the model-health skill.
- For lookahead from the cached model, suggest re-running with `train_enabled=true` and comparing the two.
- Don't call a strategy good or bad from one run. If the conclusion hinges on it, suggest a second period or universe.

## Limits

- It judges the result, not the code. For code changes, use crosscheck.
- Cost drag is an estimate from the cost model and each trade's prices, using the same formula as `CostModel` in `src/quantify/backtest/costs.py`. Keep the two in sync if that formula changes.
