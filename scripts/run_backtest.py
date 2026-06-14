#!/usr/bin/env python
"""
Run a backtest from a serialized request and POST the result to the Heroku
callback URL. Invoked by the Cloud Backtest GitHub Actions workflow so heavy
runs use a full-memory runner instead of a small dyno.

Reads from the environment:
  INPUT_JOB_ID              tracking id (echoed back so the web process can
                            match the result to the polling client)
  INPUT_REQUEST_JSON        serialized BacktestRequest JSON
  INPUT_HEROKU_CALLBACK_URL where to POST the result
  INTERNAL_API_SECRET       shared secret for the callback
"""

import json
import logging
import os
import sys
import urllib.error
import urllib.request

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)                        # api package
sys.path.insert(0, os.path.join(_ROOT, "src"))   # quantify package

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s – %(message)s")
log = logging.getLogger("run_backtest")


def main() -> None:
    job_id = os.getenv("INPUT_JOB_ID", "default")
    request_json = os.getenv("INPUT_REQUEST_JSON", "")
    callback_url = os.getenv("INPUT_HEROKU_CALLBACK_URL", "")
    secret = os.getenv("INTERNAL_API_SECRET", "")

    if not request_json.strip():
        log.error("No INPUT_REQUEST_JSON provided.")
        _send_callback(callback_url, job_id, secret, "failed", error="No request payload")
        sys.exit(1)

    from api.schemas import BacktestRequest
    from api.routers.backtest import _run_backtest_sync
    from fastapi import HTTPException

    try:
        req = BacktestRequest(**json.loads(request_json))
    except Exception as exc:
        log.exception("Invalid backtest request: %s", exc)
        _send_callback(callback_url, job_id, secret, "failed", error=f"Invalid request: {exc}")
        sys.exit(1)

    log.info("Running offloaded backtest job_id=%s (%s → %s)", job_id, req.start_date, req.end_date)
    try:
        response = _run_backtest_sync(req, job_id)
    except HTTPException as exc:
        log.error("Backtest failed: %s", exc.detail)
        _send_callback(callback_url, job_id, secret, "failed", error=str(exc.detail))
        sys.exit(1)
    except Exception as exc:
        log.exception("Backtest failed: %s", exc)
        _send_callback(callback_url, job_id, secret, "failed", error=str(exc))
        sys.exit(1)

    log.info("Backtest complete: %d trades, %.2f%% return",
             response.metrics.total_trades, response.metrics.total_return * 100)
    _send_callback(callback_url, job_id, secret, "complete", result_json=response.model_dump_json())


def _send_callback(url: str, job_id: str, secret: str, status: str,
                   result_json: str | None = None, error: str | None = None) -> None:
    if not url:
        log.info("No callback URL set — skipping (status=%s).", status)
        return

    payload = json.dumps({
        "job_id": job_id,
        "status": status,
        "result_json": result_json,
        "error": error,
    }).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if secret:
        req.add_header("X-Internal-Secret", secret)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            log.info("Callback sent to %s (HTTP %d)", url, resp.status)
    except Exception as e:
        log.error("Failed to send callback to %s: %s", url, e)


if __name__ == "__main__":
    main()
