"""Stage 1 of the PLAN_V1 vetting: point-in-time universes and one shared price download.

usage: vet_prepare.py <members.json> <out_dir>
Writes selections.json ({"<asof>:<n>": [symbols], ... , "coverage": {...}}) and prices.pkl
({symbol: OHLCV DataFrame} for every selected symbol plus SPY, 2004-06-01 .. 2026-11-14)."""
import json, os, pickle, sys
import pandas as pd, yfinance as yf

members_path, out = sys.argv[1:]
M = json.load(open(members_path))["members"]
SELECT = {"2006-12-29": [100], "2011-12-30": [100], "2016-12-30": [80, 100, 120], "2021-12-31": [80, 100, 120],
          "2016-11-30": [100], "2021-11-30": [100], "2017-01-31": [100], "2022-01-31": [100]}

def download(symbols, start, end, chunk=40):
    frames = {}
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]
        raw = yf.download(part, start=start, end=end, auto_adjust=True, group_by="ticker", threads=False, progress=False)
        for s in part:
            try:
                df = raw[s] if len(part) > 1 else raw
            except KeyError:
                continue
            df = df.dropna(how="all")
            if len(df):
                df.columns = [c.lower() for c in df.columns]
                frames[s] = df[["open", "high", "low", "close", "volume"]]
    for s in [s for s in symbols if s not in frames]:  # bulk downloads drop some symbols: retry one by one
        try:
            df = yf.Ticker(s).history(start=start, end=end, auto_adjust=True).dropna(how="all")
        except Exception:
            continue
        if len(df):
            df.columns = [c.lower() for c in df.columns]
            df.index = df.index.tz_localize(None)
            frames[s] = df[["open", "high", "low", "close", "volume"]]
    return frames

selections, coverage = {}, {}
for asof, sizes in SELECT.items():
    members = sorted(M[asof])
    t = pd.Timestamp(asof)
    win = download(members, str((t - pd.Timedelta(days=110)).date()), str((t + pd.Timedelta(days=1)).date()))
    dv = {s: float((df["close"] * df["volume"]).tail(63).median()) for s, df in win.items() if len(df) >= 40}
    ranked = sorted(dv, key=dv.get, reverse=True)
    coverage[asof] = {"members": len(members), "with_prices": len(dv), "missing": sorted(set(members) - set(dv))}
    for n in sizes:
        selections[f"{asof}:{n}"] = ranked[:n]
    print(asof, coverage[asof]["members"], "members,", len(dv), "with prices", flush=True)

symbols = sorted({s for v in selections.values() for s in v} | {"SPY"})
prices = download(symbols, "2004-06-01", "2026-11-14")
print("downloaded", len(prices), "of", len(symbols), "symbols", flush=True)
json.dump({"selections": selections, "coverage": coverage}, open(os.path.join(out, "selections.json"), "w"), indent=0)
pickle.dump(prices, open(os.path.join(out, "prices.pkl"), "wb"))
