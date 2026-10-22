---
name: prod-smoke
description: Is production Quantify actually serving? Hits the live Heroku API (/health and /api/predict/best) and the Vercel site, and explains a failure, e.g. Heroku's 503 "Application Error" means the dyno crashed. Use first when the user says the app or site shows nothing, predictions fail in the browser, or "is it down?", and after any merge to main (which deploys). model-health checks the data pipeline; this checks the serving path.
---

# prod-smoke: is the deployed app serving?

## Run it

```bash
python d:/tushargupta/Desktop/quantify/scripts/prod_smoke.py
python d:/tushargupta/Desktop/quantify/scripts/prod_smoke.py --api http://127.0.0.1:8000 --web http://localhost:3000   # local stack
```

Standard library only, read-only GETs. Exit code 1 on any FAIL. Each request is retried twice, 20 s apart, because a sleeping dyno can take ~30 s to wake.

It also runs every 2 hours in `.github/workflows/prod_smoke.yml`; check recent runs there first.

## Reading a failure

- **api: HTTP 503 Heroku 'Application Error':** the dyno crashed or isn't running. The cause is in the Heroku logs (dashboard → quantify-ai → More → View logs, or `heroku logs --tail -a quantify-ai`), usually an import error at boot. The 2026-10-16 outage was `ModuleNotFoundError: No module named 'psycopg'` after a fresh build pulled SQLAlchemy 2.1. Reproduce locally by booting `origin/main` with a `postgres://` `DATABASE_URL`; the `boot-like-heroku` CI job does the same.
- **api ok, predictions fail:** the API is up but `/api/predict/best` can't read screener-cache. Run the `model-health` skill.
- **web fails, api ok:** a Vercel problem. Check the latest Production deployment.
- **everything ok but the page is blank:** the site may call a different API than you think. The URL is baked into the JS bundle at build time from `NEXT_PUBLIC_API_URL`; grep the live `/_next/static/chunks/*.js` for `herokuapp.com`.

Don't "fix" a production failure by pushing to main. Find the cause, fix it on a branch with a regression test (`never-again`), and hand the PR to the user.
