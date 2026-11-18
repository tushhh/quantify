"""Score one vetting variant on checks B, G, H (pass marks as in vetting.md) and I, plus the full bar.

usage: vet_score_one.py <repo> <vet dir> <variant>"""
import os, sys
repo, vet, variant = sys.argv[1:]
sys.path[:0] = [os.path.join(repo, "scripts"), os.path.join(repo, "src")]
import numpy as np, pandas as pd
from backtest_picks import report, bar_rows

B = pd.read_csv(os.path.join(vet, f"daily_{variant}.csv"), index_col=0, parse_dates=True)
cagr = lambda r: (1 + r).prod() ** (252 / len(r)) - 1
rb = report(B)
ok_b = rb["excess_cagr_pct"] > 0 and rb["sharpe"] >= rb["spy_sharpe"]
print(f"{'PASS' if ok_b else 'FAIL'}  B real past members: {rb['cagr_pct']:.1f}%/yr vs SPY {rb['spy_cagr_pct']:.1f}% (excess {rb['excess_cagr_pct']:+.1f}), "
      f"Sharpe {rb['sharpe']:.2f} vs {rb['spy_sharpe']:.2f}, worst drop {rb['max_drawdown_pct']:.1f}% vs {rb['spy_max_drawdown_pct']:.1f}%")
T = pd.concat([pd.read_csv(os.path.join(vet, f"trades_{variant}_{y}.csv")).assign(period=y) for y in ("2017", "2022")])
top5 = T.groupby("symbol")["pnl"].sum().nlargest(5)
growth = 1.0
for y, d in {"2017": B.loc[:"2021-12-31"], "2022": B.loc["2022-01-01":]}.items():
    growth *= (100_000 * (1 + d.port).prod() - T[(T.period == y) & T.symbol.isin(top5.index)].pnl.sum()) / 100_000
g = growth ** (252 / len(B)) - 1
print(f"{'PASS' if g > cagr(B.spy) else 'FAIL'}  G without top 5: {g*100:.1f}%/yr vs SPY {cagr(B.spy)*100:.1f}% (removed {', '.join(top5.index)})")
rng = np.random.default_rng(20261117); P, S = B.port.to_numpy(), B.spy.to_numpy(); n = len(P)
wins, dd1 = 0, []
for _ in range(10_000):
    j, i = np.empty(n, int), rng.integers(n)
    for k in range(n):
        j[k] = i; i = rng.integers(n) if rng.random() < 1 / 21 else (i + 1) % n
    p = P[j]; wins += cagr(pd.Series(p)) > cagr(pd.Series(S[j]))
    eq = np.cumprod(1 + p[:252]); dd1.append((eq / np.maximum.accumulate(eq) - 1).min())
print(f"{'PASS' if wins >= 9000 else 'FAIL'}  H luck: beats SPY in {wins/100:.1f}% of resamples (need 90%)")
print(f"INFO  I: median worst drop in a year {np.median(dd1)*100:.1f}%, 1-in-20 {np.percentile(dd1,5)*100:.1f}%")
print("\nfull bar:")
for label, ok in bar_rows(rb):
    print(("  PASS " if ok else "  FAIL ") + label)
yr = ((1 + B).resample("YE").prod() - 1) * 100
print("by year:", ", ".join(f"{d.year} {a:+.0f}/{b:+.0f}" for d, (a, b) in zip(yr.index, yr[["port", "spy"]].values)))
