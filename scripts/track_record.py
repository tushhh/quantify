#!/usr/bin/env python
"""
Live track record of the published picks.

The screener-cache branch keeps only the latest list, so nothing recorded whether past picks
made money. screener_cron.yml now appends each new monthly list to picks.jsonl on the
append-only `pick-history` branch, and this script scores every list against SPY using what the
stocks actually did afterwards (bought at the first close after the list date, held until the
next list is bought).

    python scripts/track_record.py append --history picks.jsonl --result screener_results.json
    python scripts/track_record.py score  --history picks.jsonl [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


def load(history_path) -> list[dict]:
    path = Path(history_path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(history_path, result: dict) -> bool:
    """Record a trend-screen list unless its list date is already recorded. Returns True if added."""
    if result.get("method") != "trend" or not result.get("as_of"):
        return False
    history = load(history_path)
    if any(entry["as_of"] == result["as_of"] for entry in history):
        return False
    entry = {
        "as_of": result["as_of"],
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "symbols": [s["symbol"] for s in result.get("signals", []) if s.get("side") == "long"],
    }
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return True


def score(history: list[dict], close: pd.DataFrame, cost_bps: float = 6.0) -> pd.DataFrame:
    """One row per list: equal-weight buy-and-hold return of its picks vs SPY over its month."""
    dates = close.index
    buys = []
    for entry in history:
        after = dates[dates > pd.Timestamp(entry["as_of"])]
        buys.append(after[0] if len(after) else None)

    rows, prev = [], set()
    for i, entry in enumerate(history):
        bought = buys[i]
        if bought is None:
            continue
        later = [b for b in buys[i + 1:] if b is not None]
        sold = later[0] if later else dates[-1]
        syms = [s for s in entry["symbols"] if s in close.columns]
        rets = close.loc[sold, syms] / close.loc[bought, syms] - 1
        changed = len(set(syms) ^ prev) / max(len(syms), 1)  # share of the book traded (both sides)
        cost = changed * cost_bps / 1e4
        picks = rets.mean() - cost
        spy = close.at[sold, "SPY"] / close.at[bought, "SPY"] - 1
        rows.append({
            "as_of": entry["as_of"], "bought": str(bought.date()), "sold": str(sold.date()),
            "open": not later, "n": len(syms),
            "picks_return_pct": picks * 100, "spy_return_pct": spy * 100, "excess_pct": (picks - spy) * 100,
            "best": rets.idxmax() if len(rets) else None, "worst": rets.idxmin() if len(rets) else None,
        })
        prev = set(syms)
    return pd.DataFrame(rows)


def summary(table: pd.DataFrame) -> dict:
    if table.empty:
        return {"lists": 0}
    growth = (1 + table["picks_return_pct"] / 100).prod() - 1
    spy_growth = (1 + table["spy_return_pct"] / 100).prod() - 1
    closed = table[~table["open"]]
    return {
        "lists": len(table),
        "since": table["as_of"].iloc[0],
        "picks_total_pct": growth * 100,
        "spy_total_pct": spy_growth * 100,
        "months_beat_spy": int((closed["excess_pct"] > 0).sum()),
        "months_closed": len(closed),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live track record of the published picks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append")
    a.add_argument("--history", required=True)
    a.add_argument("--result", required=True)
    s = sub.add_parser("score")
    s.add_argument("--history", required=True)
    s.add_argument("--json")
    s.add_argument("--cost-bps", type=float, default=6.0)
    args = ap.parse_args(argv)

    if args.cmd == "append":
        result = json.loads(Path(args.result).read_text(encoding="utf-8"))
        added = append(args.history, result)
        print(f"track-record: {'recorded' if added else 'already recorded or not a trend list'} ({result.get('as_of')})")
        return 0

    history = load(args.history)
    if not history:
        print("track-record: no lists recorded yet")
        return 0
    from quantify.trend_screen import download_prices
    symbols = sorted({s for e in history for s in e["symbols"]} | {"SPY"})
    close, _ = download_prices(symbols, period="2y")
    table = score(history, close, cost_bps=args.cost_bps)
    pd.set_option("display.width", 200)
    print(table.round(2).to_string(index=False))
    info = summary(table)
    print(f"\nSince {info['since']}: picks {info['picks_total_pct']:+.1f}% vs SPY {info['spy_total_pct']:+.1f}%, "
          f"beat SPY in {info['months_beat_spy']} of {info['months_closed']} closed months")
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": info, "lists": table.to_dict("records")}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
