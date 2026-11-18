"""Run the pre-registered asset-allocation test (preregistration.md) and score it on the bar.

usage: run_allocation.py <price cache dir> [--cost 0.002]
Downloads adjusted closes once to <dir>/alloc_prices.parquet and reuses them afterwards.
"""
import argparse
import os

import numpy as np
import pandas as pd

TICKERS = ["SPY", "VTI", "EFA", "IEF", "VNQ", "DBC", "AGG", "EEM", "LQD", "SHY", "BIL"]
END = "2026-11-14"
UNSEEN = {"GTAA5": "2008-01-01", "GEM": "2015-01-01", "VAA-G4": "2017-08-01", "60/40": "2008-01-01", "SPY": "2008-01-01"}


def load_prices(cache: str) -> pd.DataFrame:
    path = os.path.join(cache, "alloc_prices.parquet")
    if os.path.exists(path):
        return pd.read_parquet(path)
    import yfinance as yf
    frames = {}
    for t in TICKERS:
        h = yf.Ticker(t).history(start="2001-01-01", end=END, auto_adjust=True)["Close"]
        h.index = h.index.tz_localize(None).normalize()
        frames[t] = h
    px = pd.DataFrame(frames).sort_index()
    os.makedirs(cache, exist_ok=True)
    px.to_parquet(path)
    return px


def with_cash(px: pd.DataFrame) -> pd.DataFrame:
    """CASH = BIL where it exists, SHY before (chained on returns)."""
    r = px["BIL"].pct_change().where(px["BIL"].notna() & px["BIL"].shift().notna(), px["SHY"].pct_change())
    px = px.copy()
    px["CASH"] = (1 + r.fillna(0)).cumprod() * 100
    px.loc[px["SHY"].isna() & px["BIL"].isna(), "CASH"] = np.nan
    return px


def month_ends(px: pd.DataFrame) -> pd.DatetimeIndex:
    s = px.index.to_series()
    return pd.DatetimeIndex(s.groupby(s.dt.to_period("M")).max().values)


# ---- strategy rules: month-end closes up to and including t -> target weights -------------

def gtaa5(m: pd.DataFrame, t) -> dict:
    assets = ["VTI", "EFA", "IEF", "VNQ", "DBC"]
    hist = m.loc[:t]
    w = {}
    for a in assets:
        if hist[a].iloc[-1] > hist[a].tail(10).mean():
            w[a] = w.get(a, 0) + 0.2
        else:
            w["CASH"] = w.get("CASH", 0) + 0.2
    return w


def gem(m: pd.DataFrame, t) -> dict:
    hist = m.loc[:t]
    r12 = hist.iloc[-1] / hist.iloc[-13] - 1
    if r12["SPY"] > r12["CASH"]:
        return {"SPY" if r12["SPY"] >= r12["EFA"] else "EFA": 1.0}
    return {"AGG": 1.0}


def vaa_g4(m: pd.DataFrame, t) -> dict:
    hist = m.loc[:t]
    last = hist.iloc[-1]
    score = lambda a: 12 * (last[a] / hist[a].iloc[-2] - 1) + 4 * (last[a] / hist[a].iloc[-4] - 1) \
        + 2 * (last[a] / hist[a].iloc[-7] - 1) + (last[a] / hist[a].iloc[-13] - 1)
    off = {a: score(a) for a in ["SPY", "EFA", "EEM", "AGG"]}
    if all(v > 0 for v in off.values()):
        return {max(off, key=off.get): 1.0}
    dfn = {a: score(a) for a in ["LQD", "IEF", "SHY"]}
    return {max(dfn, key=dfn.get): 1.0}


def sixty_forty(m, t) -> dict:
    return {"SPY": 0.6, "IEF": 0.4}


RULES = {"GTAA5": (gtaa5, ["VTI", "EFA", "IEF", "VNQ", "DBC", "CASH"]),
         "GEM": (gem, ["SPY", "EFA", "AGG", "CASH"]),
         "VAA-G4": (vaa_g4, ["SPY", "EFA", "EEM", "AGG", "LQD", "IEF", "SHY"]),
         "60/40": (sixty_forty, ["SPY", "IEF"])}


def simulate(px: pd.DataFrame, rule, assets: list[str], cost: float) -> tuple[pd.Series, int]:
    """Daily strategy returns. Weights decided at month-end close, traded at next day's close."""
    px = px[sorted(set(assets) | {"SPY"})]
    first = px.dropna().index[0]
    px = px.loc[first:]
    me = month_ends(px)
    m = px.loc[me]
    start_i = 12  # need 12 months of month-end history
    rets = px.pct_change().fillna(0.0)
    days = px.index
    exec_days = {}
    for t in me[start_i:]:
        pos = days.get_loc(t)
        if pos + 1 < len(days):
            exec_days[days[pos + 1]] = rule(m, t)
    hold = pd.Series(0.0, index=px.columns)
    out, trades, started = [], 0, False
    for d in days:
        if not started and d not in exec_days:
            continue
        if started:
            r = float((hold * rets.loc[d]).sum())
            gross = hold * (1 + rets.loc[d])
            hold = gross / gross.sum() if gross.sum() > 0 else gross
        else:
            r = 0.0
        if d in exec_days:
            target = pd.Series(0.0, index=px.columns)
            for a, w in exec_days[d].items():
                target[a] += w
            turnover = float((target - hold).abs().sum()) if started else 1.0
            r = (1 + r) * (1 - cost * turnover) - 1
            trades += int(((target - hold).abs() > 1e-9).sum())
            hold, started = target, True
        out.append((d, r))
    s = pd.Series(dict(out))
    return s.iloc[1:], trades


def metrics(r: pd.Series) -> dict:
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    # longest time below a previous peak, in months
    under, longest, start = False, 0.0, None
    for d, v in dd.items():
        if v < 0 and not under:
            under, start = True, d
        elif v >= 0 and under:
            under = False
            longest = max(longest, (d - start).days / 30.44)
    if under:
        longest = max(longest, (dd.index[-1] - start).days / 30.44)
    yrs = len(r) / 252
    return {"cagr": eq.iloc[-1] ** (1 / yrs) - 1, "sharpe": r.mean() / r.std() * np.sqrt(252),
            "max_dd": dd.min(), "underwater_months": longest}


def roll5_worst(r: pd.Series) -> float:
    eq = (1 + r).cumprod()
    w = 1260
    if len(eq) <= w:
        return float("nan")
    return float(((eq / eq.shift(w)) ** (1 / 5) - 1).min())


def bootstrap(p: np.ndarray, s: np.ndarray, n_iter=10_000, block=21, seed=20261118):
    rng = np.random.default_rng(seed)
    n = len(p)
    dd_ok = cagr_ok = 0
    for _ in range(n_iter):
        starts = rng.random(n) < 1 / block
        idx = np.empty(n, int)
        i = rng.integers(n)
        for k in range(n):
            if k and starts[k]:
                i = rng.integers(n)
            idx[k] = i
            i = (i + 1) % n
        pe, se = np.cumprod(1 + p[idx]), np.cumprod(1 + s[idx])
        dd_ok += (pe / np.maximum.accumulate(pe) - 1).min() >= -0.25
        cagr_ok += pe[-1] ** (252 / n) - se[-1] ** (252 / n) >= -0.02
    return dd_ok / n_iter, cagr_ok / n_iter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cache")
    ap.add_argument("--cost", type=float, default=0.002)
    ap.add_argument("--no-bootstrap", action="store_true")
    a = ap.parse_args()
    px = with_cash(load_prices(a.cache)).loc[:"2026-11-13"]
    spy_all = px["SPY"].pct_change()
    results = {}
    for name, (rule, assets) in RULES.items():
        r, trades = simulate(px, rule, assets, a.cost)
        results[name] = (r, trades)
    results["SPY"] = (spy_all.loc[results["GTAA5"][0].index[0]:].dropna(), 1)
    print(f"costs {a.cost:.2%} per side | data to {px.index[-1].date()}\n")
    winners = []
    for name, (r, trades) in results.items():
        u = r.loc[UNSEEN[name]:]
        su = spy_all.reindex(u.index).fillna(0)
        mu, ms, mf = metrics(u), metrics(su), metrics(r)
        rows = [("worst drop ≥ −20%", mu["max_dd"] >= -0.20, f"{mu['max_dd']:.1%}"),
                ("CAGR ≥ SPY − 2", mu["cagr"] >= ms["cagr"] - 0.02, f"{mu['cagr']:.1%} vs SPY {ms['cagr']:.1%}"),
                ("Sharpe ≥ SPY", mu["sharpe"] >= ms["sharpe"], f"{mu['sharpe']:.2f} vs {ms['sharpe']:.2f}"),
                ("underwater ≤ 24 months", mu["underwater_months"] <= 24, f"{mu['underwater_months']:.0f} months"),
                ("worst 5-yr CAGR > 0", roll5_worst(r) > 0, f"{roll5_worst(r):.1%} (full period)")]
        if not a.no_bootstrap and name != "SPY":
            pdd, pc = bootstrap(u.to_numpy(), su.to_numpy())
            rows.append(("bootstrap", pdd >= 0.80 and pc >= 0.60, f"drop ≤25% in {pdd:.0%}, CAGR ok in {pc:.0%}"))
        passed = all(ok for _, ok, _ in rows) and name != "SPY"
        if passed:
            winners.append((mu["cagr"], name))
        print(f"=== {name}: unseen {u.index[0].date()}..{u.index[-1].date()} | full period from {r.index[0].date()}: "
              f"CAGR {mf['cagr']:.1%}, worst drop {mf['max_dd']:.1%}, Sharpe {mf['sharpe']:.2f} | "
              f"{trades / (len(r) / 252):.0f} trades/yr")
        for label, ok, detail in rows:
            print(f"   {'PASS' if ok else 'FAIL'}  {label}: {detail}")
        yr = (1 + pd.DataFrame({"s": r, "spy": spy_all.reindex(r.index).fillna(0)})).resample("YE").prod() - 1
        print("   by year:", ", ".join(f"{d.year} {x*100:+.0f}/{y*100:+.0f}" for d, (x, y) in zip(yr.index, yr.values)))
    print("\nWINNER:", max(winners)[1] if winners else "none passed every row")


if __name__ == "__main__":
    main()
