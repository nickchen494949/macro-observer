import sys, os, pandas as pd, numpy as np, collections
sys.path.insert(0, "/Users/happygolucky/Desktop/宏观观察器/outputs/gemini_full_data_audit_20261031/v2_standalone")
from v2_cleanroom_lib import CleanRoomEquityStore
REPO = "/Users/happygolucky/Desktop/宏观观察器"
D = REPO + "/outputs/gemini_full_data_audit_20261031/v2_standalone/"
store = CleanRoomEquityStore(REPO, ssm_rel="research/sector_stock_momentum", include_ndx=False)

for f in ["v2_06_ledger_sp500_top1_sma200_oo.csv", "v2_06_ledger_sp500_top3_oo_rs60.csv"]:
    L = pd.read_csv(D + f, parse_dates=["month"]).set_index("month")
    cnt = collections.Counter(); fb = []
    for m, r in L.iterrows():
        t = pd.Timestamp(r["formation"])
        for tk in str(r["invested_picks"]).split("|"):
            if tk == "CASH": continue
            v, st = store.open_return(t, tk)
            cnt[st] += 1
            if st != "ok_open": fb.append((str(m.date()), tk, st, None if v is None else round(v, 4)))
    tot = sum(cnt.values())
    print(f"\n{f}: stock-months={tot}  status={dict(cnt)}  non-open share={100*(tot-cnt['ok_open'])/tot:.1f}%")
    for x in fb[:60]: print("   ", x)

# provenance of opens: which tickers have NO raw_open file at all
od = REPO + "/research/sector_stock_momentum/data/raw_open"
have = {f[:-5] for f in os.listdir(od) if f.endswith(".json")}
print("\nP columns:", len(store.P.columns), " with any open data:", int(store.O.notna().any().sum()))

# split sanity: adj_open vs adjclose ratio jumps
import json
bad = []
for f in sorted(have):
    d = json.load(open(f"{od}/{f}.json"))
    if not d.get("adj_open") or not d.get("adjclose"): continue
    s = pd.DataFrame({"o": d["adj_open"], "c": d["adjclose"]}, index=pd.to_datetime(d["dates"])).dropna()
    s = s[s.index >= "2009-01-01"]
    if len(s) < 50: continue
    ratio = (s["o"] / s["c"].shift(1))  # open vs prior close
    j = ratio[(ratio > 1.6) | (ratio < 0.6)]
    if len(j): bad.append((f, len(j), str(j.index[0].date()), round(float(j.iloc[0]), 3)))
print(f"tickers with adj_open/prev adjclose gap >60% or <-40%: {len(bad)}")
for b in bad[:40]: print("   ", b)
