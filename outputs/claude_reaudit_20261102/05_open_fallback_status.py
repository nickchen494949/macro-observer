#!/usr/bin/env python3
"""
05 — How often does the 'next-day open' engine actually use a close price?

  Part A (ENGINE-DEPENDENT, by design): asks Gemini's own CleanRoomEquityStore.open_return which
          status it assigned to every held stock-month (we are auditing what THEIR code did).
  Part B (INDEPENDENT): from raw files only — for every held (ticker, month), does
          raw_open/<ticker>.json contain adj_open on BOTH the entry and exit session?
          (Aliased tickers whose opens live under a successor symbol are reported separately.)
Output: results/05_open_fallback.csv
"""
import json, os, sys, collections
import pandas as pd
from _paths import REPO, DATA, GEMINI, RESULTS, gemini_ledger

LEDGERS = ["v2_06_ledger_sp500_top1_sma200_oo.csv", "v2_06_ledger_sp500_top3_oo_rs60.csv"]
spy = json.load(open(f"{DATA}/raw/SPY.json")); sessions = pd.to_datetime(spy["dates"])
def nxt(d):
    i = sessions.searchsorted(d, side="right"); return sessions[i] if i < len(sessions) else None
_cache = {}
def opens(tk):
    if tk not in _cache:
        p = f"{DATA}/raw_open/{tk}.json"
        _cache[tk] = (pd.Series(json.load(open(p))["adj_open"], index=pd.to_datetime(json.load(open(p))["dates"])).dropna()
                      if os.path.exists(p) else None)
    return _cache[tk]

# ---- Part B: independent ----
rows = []
for f in LEDGERS:
    L = pd.read_csv(gemini_ledger(f), parse_dates=["month"]).set_index("month")
    for m, r in L.iterrows():
        t = pd.Timestamp(r["formation"]); d0, d1 = nxt(t), nxt(m)
        for tk in str(r["invested_picks"]).split("|"):
            if tk == "CASH": continue
            o = opens(tk)
            st = ("no_raw_open_file" if o is None else
                  "open_both_legs" if (d0 in o.index and d1 in o.index) else "open_missing_on_a_leg")
            rows.append(dict(ledger=f, month=m.date(), ticker=tk, indep_status=st))
D = pd.DataFrame(rows)

# ---- Part A: Gemini engine's own status ----
sys.path.insert(0, GEMINI)
from v2_cleanroom_lib import CleanRoomEquityStore   # noqa: E402  (engine-dependent by design)
store = CleanRoomEquityStore(REPO, ssm_rel="research/sector_stock_momentum", include_ndx=False)
D["gemini_engine_status"] = [store.open_return(pd.Timestamp(r.month) - pd.offsets.MonthEnd(1), r.ticker)[1]
                             for r in D.itertuples()]
D.to_csv(f"{RESULTS}/05_open_fallback.csv", index=False)
for f, g in D.groupby("ledger"):
    n = len(g)
    a = (g["gemini_engine_status"] != "ok_open").sum()
    b = (g["indep_status"] != "open_both_legs").sum()
    print(f"[05] {f}: held stock-months={n} | Gemini engine non-open={a} ({100*a/n:.1f}%) | "
          f"independent: no open on both legs under same symbol={b} ({100*b/n:.1f}%)")
    print("      gemini status:", dict(collections.Counter(g["gemini_engine_status"])))
    print("      indep status :", dict(collections.Counter(g["indep_status"])))
    print("      years of fallback:", dict(collections.Counter(pd.to_datetime(g[g.gemini_engine_status != 'ok_open'].month).dt.year)))
