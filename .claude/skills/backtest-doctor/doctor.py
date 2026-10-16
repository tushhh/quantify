"""Sanity-check a Quantify backtest result for the failure modes this repo has hit before.

Usage (from the repo root; standard library only):
    python .claude/skills/backtest-doctor/doctor.py result.json
    python .claude/skills/backtest-doctor/doctor.py --job JOB_ID [--api https://your-api-host]

Input is the JSON returned by POST /api/backtest?run_sync=true or
GET /api/backtest/result/{job_id}. Exit code 1 if any FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import date

# Kept in sync with CostModel.calculate_execution_price / calculate_commission
# (src/quantify/backtest/costs.py): a MARKET fill moves the price adversely by
# half-spread + market impact + slippage, and pays max(qty * per-share, minimum).
COST_FIELDS = ("commission_per_share", "min_commission", "spread_bps", "market_impact_bps",
               "slippage_pct")

# api/routers/backtest.py default universe: today's mega caps.
DEFAULT_UNIVERSE = {"AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "JPM", "BAC", "GS",
                    "V", "MA", "UNH", "JNJ", "PFE", "XOM", "CVX", "WMT", "PG", "KO"}

findings: list[tuple[str, str]] = []


def add(status: str, message: str) -> None:
    findings.append((status, message))


def load(args: argparse.Namespace) -> dict:
    if args.job:
        url = f"{args.api.rstrip('/')}/api/backtest/result/{args.job}"
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.load(resp)
    with open(args.path, encoding="utf-8") as fh:
        return json.load(fh)


def parse_cost_model(text: str) -> dict[str, float]:
    values = dict(re.findall(r"(\w+)=([-+0-9.eE]+)", text or ""))
    return {k: float(values[k]) for k in COST_FIELDS if k in values}


def check_costs(md: dict, trades: list[dict], initial: float) -> None:
    cost = parse_cost_model(md.get("cost_model", ""))
    if not cost:
        add("INFO", "cost model not recorded in metadata; cost checks skipped")
        return
    slip, spread = cost.get("slippage_pct", 0.0), cost.get("spread_bps", 0.0)
    impact, per_share = cost.get("market_impact_bps", 0.0), cost.get("commission_per_share", 0.0)
    if slip > 0.01:
        add("FAIL", f"slippage_pct={slip:g} means {slip:.1%} per fill. It's a fraction "
                    "(0.0005 = 5 bps), so this looks like a percent typed as a fraction. "
                    "The same units error produced the -11% / Sharpe -5 run in PR #33")
    if spread > 50 or impact > 50:
        add("WARN", f"spread {spread:g} bps / market impact {impact:g} bps per fill are far "
                    "above large-cap US equity norms (single digits)")
    if per_share > 0.05:
        add("WARN", f"commission ${per_share:g}/share is high for US equities")

    per_fill = spread / 2 / 1e4 + impact / 1e4 + slip
    est = 0.0
    for t in trades:
        qty = abs(float(t.get("quantity") or 0))
        for price in (t.get("entry_price"), t.get("exit_price")):
            if price:
                est += float(price) * qty * per_fill + max(qty * per_share,
                                                           cost.get("min_commission", 0.0))
    net = sum(float(t.get("pnl") or 0) for t in trades)
    if initial and est:
        status = "WARN" if est > abs(net) and est > 0.02 * initial else "INFO"
        add(status, f"estimated trading costs ${est:,.0f} ({est / initial:.1%} of capital; "
                    f"{2 * per_fill * 1e4:.0f} bps per round trip) vs net trade P&L ${net:,.0f}"
                    + (". Costs exceed the edge" if status == "WARN" else ""))


def check_strategies(md: dict, trades: list[dict]) -> None:
    ran = md.get("strategies_run") or md.get("strategies") or []
    counts = Counter(t.get("strategy_name") for t in trades)
    for name in ran:
        if counts.get(name):
            continue
        if name == "volatility_regime":
            add("INFO", "volatility_regime never trades: it only scales the other strategies' "
                        "signals. Allocations aren't renormalised, so its share of capital "
                        "appears to stay in cash")
        elif name == "ml_return_predictor":
            add("FAIL", "ml_return_predictor made 0 trades: the ML sleeve was silently dead. "
                        "Check the model/feature schema first (model-health skill; PR #33)")
        else:
            add("WARN", f"{name} made 0 trades over the whole run. Its allocation sat idle")
    if md.get("ml_model_mode") == "cached_pretrained":
        add("WARN", "ML used today's pre-trained model for every historical date: lookahead, "
                    "so its contribution is optimistic. Re-run with train_enabled=true to check")
    symbols = set(md.get("symbols") or [])
    if "volatility_regime" in ran and not symbols & {"^VIX", "VIX"}:
        add("WARN", "volatility_regime had no ^VIX in the data, so it used the latest live VIX "
                    "for every date: lookahead, and the result changes from day to day")


def check_data(md: dict, equity: list[dict]) -> None:
    symbols = set(md.get("symbols") or []) - {"SPY", "^VIX", md.get("benchmark", "SPY")}
    if len(symbols) >= 400:
        add("WARN", f"{len(symbols)}-symbol universe built from today's index members: "
                    "survivorship bias (delisted names are missing), so returns skew high")
    elif symbols and symbols <= DEFAULT_UNIVERSE:
        add("WARN", "default universe = today's mega caps: survivorship bias, since these are "
                    "the winners of the period by construction")
    skipped = md.get("skipped_symbols") or []
    if skipped:
        add("WARN", f"{len(skipped)} requested symbols had no usable data and were dropped: "
                    f"{', '.join(skipped[:15])}")
    start, requested = md.get("start"), md.get("start_date")
    try:
        lag = (date.fromisoformat(str(start)[:10]) - date.fromisoformat(str(requested)[:10])).days
        if lag > 10:
            add("WARN", f"first simulated day {str(start)[:10]} is {lag} days after the requested "
                        f"start {requested}; some history was missing")
    except (TypeError, ValueError):
        pass
    if equity and all(p.get("benchmark_value") in (None, 0) for p in equity):
        add("WARN", "no benchmark series: the benchmark ticker is missing from the data")


def check_metrics(m: dict, md: dict, trades: list[dict], equity: list[dict]) -> None:
    days, n = md.get("n_trading_days") or len(equity), m.get("total_trades", len(trades))
    if days and days < 126:
        add("WARN", f"only {days} trading days: too short to judge a strategy")
    if n < 30:
        add("WARN", f"only {n} trades: too few for the win rate or Sharpe to mean much")
    sharpe, mdd = m.get("sharpe_ratio", 0.0), m.get("max_drawdown", 0.0)
    if sharpe > 3:
        add("WARN", f"Sharpe {sharpe:.2f} is implausibly high for daily equity strategies. "
                    "Look for lookahead before celebrating")
    elif sharpe < -2:
        add("WARN", f"Sharpe {sharpe:.2f} is implausibly bad. Check the cost settings first")
    if mdd < -0.5:
        add("WARN", f"max drawdown {mdd:.0%}")
    if m.get("avg_holding_days", 99) < 2 and n > 200:
        add("WARN", f"{n} trades held {m['avg_holding_days']:.1f} days on average: high churn, "
                    "so costs scale with turnover")

    net = sum(float(t.get("pnl") or 0) for t in trades)
    top3 = sum(sorted((float(t.get("pnl") or 0) for t in trades), reverse=True)[:3])
    if net > 0 and len(trades) > 10 and top3 > 0.75 * net:
        add("WARN", f"the 3 best trades made {top3 / net:.0%} of net P&L: the result hangs on "
                    "a handful of trades")

    first, last = (equity[0], equity[-1]) if equity else ({}, {})
    if first.get("benchmark_value") and last.get("benchmark_value"):
        bench = last["benchmark_value"] / first["benchmark_value"] - 1
        total = m.get("total_return", 0.0)
        add("INFO", f"total return {total:+.1%} vs benchmark {bench:+.1%} "
                    f"(excess {total - bench:+.1%})")
    if md.get("run_id"):
        add("INFO", f"run_id {md['run_id']}: identical inputs reproduce this fingerprint")
    else:
        add("INFO", "no run_id: this result predates run manifests and can't be fingerprinted")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", nargs="?", help="saved backtest response JSON")
    parser.add_argument("--job", help="fetch /api/backtest/result/JOB from --api")
    parser.add_argument("--api", default=os.getenv("QUANTIFY_API_URL", "http://localhost:8000"),
                        help="API base URL (default $QUANTIFY_API_URL or localhost:8000)")
    args = parser.parse_args()
    if not args.path and not args.job:
        parser.error("pass a JSON file or --job")

    result = load(args)
    if result.get("status") == "running":
        print("Backtest is still running; try again when it finishes.")
        return 0
    m, md = result.get("metrics") or {}, result.get("metadata") or {}
    trades, equity = result.get("trades") or [], result.get("equity_curve") or []
    initial = float(md.get("initial_capital") or 0)

    check_costs(md, trades, initial)
    check_strategies(md, trades)
    check_data(md, equity)
    check_metrics(m, md, trades, equity)

    print(f"backtest-doctor: {md.get('start_date', '?')} to {md.get('end_date', '?')}, "
          f"{', '.join(md.get('strategies_run') or [])}")
    print(f"  total return {m.get('total_return', 0):+.1%} | Sharpe {m.get('sharpe_ratio', 0):.2f}"
          f" | max DD {m.get('max_drawdown', 0):.1%} | {m.get('total_trades', len(trades))} trades"
          f" | win rate {m.get('win_rate', 0):.0%}\n")
    order = {"FAIL": 0, "WARN": 1, "INFO": 2}
    for status, message in sorted(findings, key=lambda f: order[f[0]]):
        print(f"[{status:<4}] {message}")
    fails = sum(s == "FAIL" for s, _ in findings)
    warns = sum(s == "WARN" for s, _ in findings)
    print(f"\nRESULT: {fails} FAIL, {warns} WARN"
          + ("" if fails or warns else ". Nothing suspicious found"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
