"""Score the PLAN_V1 vetting runs against the pass marks in vetting.md.

usage: vet_score.py <repo> <vet dir>"""
import os, sys
repo, vet = sys.argv[1:]
sys.path[:0] = [os.path.join(repo, "scripts"), os.path.join(repo, "src")]
import numpy as np, pandas as pd
from backtest_picks import report, bar_rows

def load(v):
    return pd.read_csv(os.path.join(vet, f"daily_{v}.csv"), index_col=0, parse_dates=True)

def cagr(r):
    return (1 + r).prod() ** (252 / len(r)) - 1

def line(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")
    return ok

res = {}
B = load("base"); rb = report(B)
res["B"] = line("B survivorship (point-in-time members)", rb["excess_cagr_pct"] > 0 and rb["sharpe"] >= rb["spy_sharpe"],
                f"{rb['cagr_pct']:.1f}%/yr vs SPY {rb['spy_cagr_pct']:.1f}% (excess {rb['excess_cagr_pct']:+.1f}), Sharpe {rb['sharpe']:.2f} vs {rb['spy_sharpe']:.2f}, worst drop {rb['max_drawdown_pct']:.1f}% vs {rb['spy_max_drawdown_pct']:.1f}%")
C = load("c2007"); rc = report(C)
res["C"] = line("C 2007-2016 incl. 2008", rc["excess_cagr_pct"] > 0 and rc["max_dd_vs_spy"] <= 1.25,
                f"{rc['cagr_pct']:.1f}%/yr vs SPY {rc['spy_cagr_pct']:.1f}% (excess {rc['excess_cagr_pct']:+.1f}), worst drop {rc['max_drawdown_pct']:.1f}% vs SPY {rc['spy_max_drawdown_pct']:.1f}% ({rc['max_dd_vs_spy']:.2f}x)")
for key, v, label in [("D", "cost2x", "D double costs"), ("E", "delay1", "E one-day delay")]:
    r = report(load(v)); res[key] = line(label, r["excess_cagr_pct"] > 0, f"excess {r['excess_cagr_pct']:+.1f}%/yr ({r['cagr_pct']:.1f}% vs {r['spy_cagr_pct']:.1f}%)")
fs = {v: report(load(v))["excess_cagr_pct"] for v in ["u80", "u120", "alloc5050", "earlier", "later"]}
res["F"] = line("F settings (every variant)", all(x > 0 for x in fs.values()), ", ".join(f"{k} {x:+.1f}" for k, x in fs.items()))

# G: remove the realised P&L of the 5 symbols with the largest total P&L
T = pd.concat([pd.read_csv(os.path.join(vet, f"trades_base_{y}.csv")).assign(period=y) for y in ("2017", "2022")])
top5 = T.groupby("symbol")["pnl"].sum().nlargest(5)
growth = 1.0
for y, d in B.groupby(B.index <= "2021-12-31"):
    pass
parts = {"2017": B.loc[:"2021-12-31"], "2022": B.loc["2022-01-01":]}
for y, d in parts.items():
    end_eq = 100_000 * (1 + d.port).prod()
    removed = T[(T.period == y) & T.symbol.isin(top5.index)].pnl.sum()
    growth *= (end_eq - removed) / 100_000
g_cagr = growth ** (252 / len(B)) - 1
res["G"] = line("G without the top 5 stocks", g_cagr > cagr(B.spy),
                f"{g_cagr*100:.1f}%/yr vs SPY {cagr(B.spy)*100:.1f}% (removed {', '.join(top5.index)}: ${top5.sum():,.0f})")

# H and I: stationary block bootstrap, mean block 21 days, 10,000 resamples, paired days
rng = np.random.default_rng(20261117)
P, S = B.port.to_numpy(), B.spy.to_numpy(); n = len(P)
def idx(length):
    out, i = np.empty(length, int), rng.integers(n)
    for k in range(length):
        out[k] = i
        i = rng.integers(n) if rng.random() < 1 / 21 else (i + 1) % n
    return out
wins, dd1, dd5, hit5 = 0, [], [], 0
for _ in range(10_000):
    j = idx(n); p, s = P[j], S[j]
    wins += cagr(pd.Series(p)) > cagr(pd.Series(s))
    for horizon, store in ((252, dd1), (1260, dd5)):
        eq = np.cumprod(1 + p[:horizon]); d = (eq / np.maximum.accumulate(eq) - 1).min(); store.append(d)
    hit5 += dd1[-1] <= -0.05
res["H"] = line("H luck (block bootstrap)", wins / 10_000 >= 0.90, f"beats SPY in {wins/100:.1f}% of 10,000 resamples")
print(f"INFO  I your 5% limit: chance of a 5%+ drop within a year {hit5/100:.0f}%; median worst drop in a year {np.median(dd1)*100:.1f}%, in 5 years {np.median(dd5)*100:.1f}%; 1-in-20 worst in a year {np.percentile(dd1,5)*100:.1f}%")

print("\nfull bar on B:")
beta = np.cov(B.port, B.spy)[0, 1] / B.spy.var(); alpha = (B.port.mean() - beta * B.spy.mean()) * 252 * 100
for label, ok in bar_rows(rb) + [(f"Positive alpha after beta ({alpha:+.1f}%/yr)", alpha > 0)]:
    print(("  PASS " if ok else "  FAIL ") + label)
yr = ((1 + pd.concat([C, B])).resample("YE").prod() - 1) * 100
print("\nby year (strategy / SPY):", ", ".join(f"{d.year} {a:+.0f}/{b:+.0f}" for d, (a, b) in zip(yr.index, yr[["port", "spy"]].values)))
verdict = "DO NOT BUILD" if not (res["B"] and res["C"] and res["H"]) else "OK TO BUILD" + ("" if all(res.values()) else " (with weaknesses)")
print("\nVERDICT:", verdict)
