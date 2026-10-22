"""Tests for scripts/prod_smoke.py, the production liveness check.

The 2026-10-16 outage went unnoticed for days because every workflow checked the data
pipeline and none checked the serving path. These tests pin down what the smoke check
must treat as an outage.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("prod_smoke", SCRIPTS / "prod_smoke.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)

API = "https://api.example.test"
WEB = "https://web.example.test"
HEROKU_503 = b"<!DOCTYPE html><html><head><title>Application Error</title></head></html>"
HEALTHY = {
    f"{API}/health": (200, json.dumps({"status": "ok", "version": "1.0.0"}).encode()),
    f"{API}/api/predict/best?top_n=5": (
        200,
        json.dumps({"status": "ok", "date": "2026-10-20", "signals": [{"symbol": "AAPL"}]}).encode(),
    ),
    f"{WEB}/": (200, b"<html>Quantify</html>"),
}


def fake_fetch(responses):
    """A fetch(url, timeout) stand-in that serves canned (status, body) pairs or raises."""
    calls = []

    def fetch(url, timeout):
        calls.append(url)
        result = responses[url]
        if isinstance(result, list):  # a sequence of outcomes, one per call
            result = result.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    fetch.calls = calls
    return fetch


def run(responses):
    return smoke.run_checks(API, WEB, fetch=fake_fetch(responses), sleep=lambda s: None)


def by_name(results):
    return {r.name: r for r in results}


def test_all_checks_pass_when_api_predictions_and_site_are_up() -> None:
    results = run(dict(HEALTHY))

    assert all(r.ok for r in results), [r for r in results if not r.ok]


def test_heroku_application_error_fails_the_api_check() -> None:
    responses = dict(HEALTHY)
    responses[f"{API}/health"] = (503, HEROKU_503)
    responses[f"{API}/api/predict/best?top_n=5"] = (503, HEROKU_503)

    results = by_name(run(responses))

    assert not results["api"].ok
    assert "503" in results["api"].detail
    assert not results["predictions"].ok
    assert results["web"].ok  # Vercel stays up when Heroku dies, which is why nobody noticed


def test_predictions_with_no_signals_fail() -> None:
    responses = dict(HEALTHY)
    responses[f"{API}/api/predict/best?top_n=5"] = (200, json.dumps({"status": "ok", "signals": []}).encode())

    results = by_name(run(responses))

    assert not results["predictions"].ok
    assert "no signals" in results["predictions"].detail


def test_a_sleeping_dyno_gets_another_try_before_failing() -> None:
    responses = dict(HEALTHY)
    responses[f"{API}/health"] = [TimeoutError("timed out"), HEALTHY[f"{API}/health"]]

    results = by_name(run(responses))

    assert results["api"].ok


def test_main_exits_nonzero_and_writes_a_summary_on_failure(tmp_path, monkeypatch) -> None:
    responses = dict(HEALTHY)
    responses[f"{API}/health"] = (503, HEROKU_503)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    code = smoke.main(["--api", API, "--web", WEB], fetch=fake_fetch(responses), sleep=lambda s: None)

    assert code == 1
    assert "FAIL" in summary.read_text(encoding="utf-8")
