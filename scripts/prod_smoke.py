"""Production smoke check: is the live app actually serving?

The model-health workflow checks the data pipeline (model-cache, screener-cache), but
nothing checked the serving path, so a crashed Heroku API went unnoticed for days while
every workflow stayed green. This hits the deployed API and site and exits 1 on failure.

Usage:
    python scripts/prod_smoke.py [--api URL] [--web URL]
URLs default to $PROD_API_URL and $PROD_WEB_URL, then to the production deployments.
Standard library only, so it runs without installing the project.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import NamedTuple

DEFAULT_API = "https://quantify-ai-8a8cdafff4ea.herokuapp.com"
DEFAULT_WEB = "https://www.quantify.software"
TIMEOUT_S = 45  # an Eco dyno waking from sleep can take ~30 s
ATTEMPTS = 3
RETRY_WAIT_S = 20


class Result(NamedTuple):
    name: str
    ok: bool
    detail: str


def http_get(url: str, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "quantify-prod-smoke"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def _get_with_retries(url, fetch, sleep) -> tuple[int | None, bytes, str]:
    """Return (status, body, error). Retries timeouts, connection errors and 5xx."""
    status, body, error = None, b"", ""
    for attempt in range(ATTEMPTS):
        try:
            status, body = fetch(url, TIMEOUT_S)
            error = ""
            if status < 500:
                break
        except (OSError, TimeoutError) as err:
            status, body, error = None, b"", f"{type(err).__name__}: {err}"
        if attempt < ATTEMPTS - 1:
            sleep(RETRY_WAIT_S)
    return status, body, error


def _describe_failure(status, body, error) -> str:
    if error:
        return error
    if b"Application Error" in body:
        return f"HTTP {status} Heroku 'Application Error' (dyno crashed or not running; check heroku logs)"
    return f"HTTP {status}"


def _json(body: bytes):
    try:
        return json.loads(body)
    except ValueError:
        return None


def check_api(api, fetch, sleep) -> Result:
    status, body, error = _get_with_retries(f"{api}/health", fetch, sleep)
    payload = _json(body) if status == 200 else None
    if isinstance(payload, dict) and payload.get("status") == "ok":
        return Result("api", True, f"{api}/health ok")
    return Result("api", False, f"{api}/health: {_describe_failure(status, body, error)}")


def check_predictions(api, fetch, sleep) -> Result:
    url = f"{api}/api/predict/best?top_n=5"
    status, body, error = _get_with_retries(url, fetch, sleep)
    if status != 200:
        return Result("predictions", False, f"{url}: {_describe_failure(status, body, error)}")
    payload = _json(body)
    if not isinstance(payload, dict):
        return Result("predictions", False, f"{url}: response is not JSON")
    signals = payload.get("signals")
    if not signals:
        return Result("predictions", False, f"{url}: no signals (date {payload.get('date')})")
    return Result("predictions", True, f"{len(signals)} signals for {payload.get('date')}")


def check_web(web, fetch, sleep) -> Result:
    status, body, error = _get_with_retries(f"{web}/", fetch, sleep)
    if status == 200:
        return Result("web", True, f"{web}/ ok")
    return Result("web", False, f"{web}/: {_describe_failure(status, body, error)}")


def run_checks(api: str, web: str, fetch=http_get, sleep=time.sleep) -> list[Result]:
    api, web = api.rstrip("/"), web.rstrip("/")
    return [check_api(api, fetch, sleep), check_predictions(api, fetch, sleep), check_web(web, fetch, sleep)]


def main(argv=None, fetch=http_get, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default=os.getenv("PROD_API_URL") or DEFAULT_API)
    parser.add_argument("--web", default=os.getenv("PROD_WEB_URL") or DEFAULT_WEB)
    args = parser.parse_args(argv)

    results = run_checks(args.api, args.web, fetch=fetch, sleep=sleep)
    lines = [f"[{'OK  ' if r.ok else 'FAIL'}] {r.name}: {r.detail}" for r in results]
    failed = sum(not r.ok for r in results)
    lines.append(f"\nRESULT: {failed} FAIL")
    report = "\n".join(lines)
    print(report)

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(f"## Production smoke check\n\n```\n{report}\n```\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
