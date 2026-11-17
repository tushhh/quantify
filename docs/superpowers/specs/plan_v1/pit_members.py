"""Point-in-time S&P 500 membership: the 2025-09-30 list with Wikipedia's "Selected changes" undone backwards."""
import io, json, sys
import pandas as pd, requests

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

REVISION = 1314254751  # 2025-09-30 revision: the last with the "Selected changes" table on this page

def load():
    html = requests.get("https://en.wikipedia.org/w/index.php", params={"oldid": REVISION},
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    tables = pd.read_html(io.StringIO(html))
    current = set(tables[0]["Symbol"].str.replace(".", "-", regex=False))
    ch = tables[1]
    dates = pd.to_datetime(ch[("Effective Date", "Effective Date")], errors="coerce")
    norm = lambda s: s.replace(".", "-").strip() if isinstance(s, str) and s.strip() else None
    rows = [(d, norm(a), norm(r)) for d, a, r in zip(dates, ch[("Added", "Ticker")], ch[("Removed", "Ticker")]) if pd.notna(d)]
    return current, sorted(rows, key=lambda x: x[0], reverse=True)

def members_at(asof, current, changes):
    m = set(current)
    for d, added, removed in changes:  # newest first; undo every change after asof
        if d <= pd.Timestamp(asof):
            break
        if added: m.discard(added)
        if removed: m.add(removed)
    return m

if __name__ == "__main__":
    current, changes = load()
    out = {a: sorted(members_at(a, current, changes)) for a in sys.argv[2:]}
    json.dump({"current": sorted(current), "members": out, "n_changes": len(changes),
               "oldest_change": str(changes[-1][0].date())}, open(sys.argv[1], "w"), indent=0)
    print({a: len(v) for a, v in out.items()}, "changes", len(changes), "oldest", changes[-1][0].date())
