#!/usr/bin/env python3
"""
04 — INDEPENDENT checks on Gemini's saved ledgers:
  (a) recompute CAGR / MaxDD / cash% from the ledger 'net' column and compare with the headline numbers
  (b) for the 15 largest |gross| months of Top-1 + SMA200 (open), recompute the return directly from
      raw_open adj_open (first session after t -> first session after t+1M)
Output: results/04_ledger_math.csv, results/04_big_months.csv
"""
import json, os
import pandas as pd, numpy as np
from _paths import DATA, RESULTS, gemini_ledger
from claude_engine import cagr, mdd

HEADLINE = {  # numbers as stated in Gemini's reports / chat
    ("v2_06_ledger_sp500_top3_oo_rs60.csv", "2015"): (30.19, -24.63),
    ("v2_06_ledger_sp500_top3_oo_rs60.csv", "2010"): (27.00, -28.73),
    ("v2_06_ledger_sp500_top1_sma200_oo.csv", "2015"): (50.18, -61.00),
    ("v2_06_ledger_sp500_top1_sma200_oo.csv", "2010"): (45.82, -61.00),
    ("v2_06_ledger_sp500_top1_sma200_cc.csv", "2015"): (52.04, -62.29),
    ("v2_06_ledger_sp500_top1_sma200_cc.csv", "2010"): (45.47, -62.29),
    ("v2_06_ledger_sp500_top3_cc_rs60.csv", "2015"): (29.87, -26.02),
}
rows = []
for (f, a), (hc, hd) in HEADLINE.items():
    L = pd.read_csv(gemini_ledger(f), parse_dates=["month"]).set_index("month").loc[a:"2026-09"]
    c, d = round(cagr(L["net"]) * 100, 2), round(mdd(L["net"]) * 100, 2)
    rows.append(dict(ledger=f, window=f"{a}-2026.09", months=len(L), cagr_recomputed=c, cagr_reported=hc,
                     mdd_recomputed=d, mdd_reported=hd, cash_pct=round(L["cash_frac"].mean() * 100, 1),
                     match=abs(c - hc) < 0.006 and abs(d - hd) < 0.006))
T = pd.DataFrame(rows); T.to_csv(f"{RESULTS}/04_ledger_math.csv", index=False)
print(T[["ledger", "window", "cagr_recomputed", "cagr_reported", "mdd_recomputed", "mdd_reported", "match"]].to_string(index=False))

spy = json.load(open(f"{DATA}/raw/SPY.json")); sessions = pd.to_datetime(spy["dates"])
def nxt(d):
    i = sessions.searchsorted(d, side="right"); return sessions[i]
L = pd.read_csv(gemini_ledger("v2_06_ledger_sp500_top1_sma200_oo.csv"), parse_dates=["month"]).set_index("month")
big = L.reindex(L["gross"].abs().sort_values(ascending=False).index).head(15)
out = []
for m, r in big.iterrows():
    t = pd.Timestamp(r["formation"]); tk = r["picks"]; d0, d1 = nxt(t), nxt(t + pd.offsets.MonthEnd(1))
    p = f"{DATA}/raw_open/{tk}.json"; mine = np.nan
    if os.path.exists(p):
        j = json.load(open(p)); o = pd.Series(j["adj_open"], index=pd.to_datetime(j["dates"]))
        if d0 in o.index and d1 in o.index:
            mine = o[d1] / o[d0] - 1
    out.append(dict(month=m.date(), ticker=tk, gemini_gross_pct=round(r["gross"] * 100, 2),
                    claude_raw_open_pct=round(mine * 100, 2) if np.isfinite(mine) else None,
                    note="" if np.isfinite(mine) else "no raw open (close fallback month)"))
B = pd.DataFrame(out); B.to_csv(f"{RESULTS}/04_big_months.csv", index=False)
print(B.to_string(index=False))
