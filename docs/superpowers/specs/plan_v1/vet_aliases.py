"""Add members whose Yahoo history now lives under a new ticker (renames since 2025-09).

usage: vet_aliases.py <vet dir>
For each selection date, an aliased member enters the top-n list only if its 63-day median dollar
volume beats the n-th selected stock's, exactly as if it had been ranked with the rest. Prices are
stored under the old (member) ticker. EQR/AVB (merged into VMRK) are left out: which history VMRK
carries is ambiguous."""
import json, os, pickle, sys
import pandas as pd, yfinance as yf

ALIASES = {"BK": "BNY", "MMC": "MRSH", "FI": "FISV"}
vet = sys.argv[1]
S = json.load(open(os.path.join(vet, "selections.json")))
M = json.load(open(os.path.join(vet, "members.json")))["members"]
prices = pickle.load(open(os.path.join(vet, "prices.pkl"), "rb"))

hist = {}
for old, new in ALIASES.items():
    df = yf.Ticker(new).history(start="2004-06-01", end="2026-11-14", auto_adjust=True).dropna(how="all")
    df.columns = [c.lower() for c in df.columns]
    df.index = df.index.tz_localize(None)
    hist[old] = df[["open", "high", "low", "close", "volume"]]

def dv(df, asof):
    w = df.loc[:asof].tail(63)
    return float((w["close"] * w["volume"]).median()) if len(w) >= 40 else 0.0

added = {}
for key, syms in list(S["selections"].items()):
    asof = key.split(":")[0]
    cand = [o for o in ALIASES if o in M[asof] and o not in syms]
    if not cand:
        continue
    pool = {s: dv(prices[s], asof) for s in syms}
    pool.update({o: dv(hist[o], asof) for o in cand})
    n = len(syms)
    new_list = sorted(pool, key=pool.get, reverse=True)[:n]
    added[key] = [o for o in cand if o in new_list]
    S["selections"][key] = new_list
for o, df in hist.items():
    prices[o] = df
S["aliases"] = {"map": ALIASES, "added_by_selection": added}
json.dump(S, open(os.path.join(vet, "selections.json"), "w"), indent=0)
pickle.dump(prices, open(os.path.join(vet, "prices.pkl"), "wb"))
print({k: v for k, v in added.items() if v})
