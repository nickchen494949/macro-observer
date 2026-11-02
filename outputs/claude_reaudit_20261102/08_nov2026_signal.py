#!/usr/bin/env python3
"""
08 — INDEPENDENT recomputation of the November-2026 live signal (formation = 2026-10-30).

Data provenance (every number is traceable):
  * Daily closes through 2026-10-29 : research/.../data/raw_open/<T>.json ('close'/'adjclose').
    CAVEAT: the 10-29 bar looks like an intraday capture (SPY 768.25 in file vs 769.36 official close).
  * 2026-10-30 closes NOT in the dataset -> external, recorded here:
      SNDK 1150.89, MRNA 221.72, LITE 840.70, MU 884.74 : Yahoo spark API (fetch_yahoo_spark.py) response,
          quote timestamp 1793390400 (= 2026-10-30 16:00 ET), captured 2026-11-02 14:31 +08:00.
      SPY 755.72 : stockanalysis.com historical table (two independent web lookups agree; single provider).
  * Membership: last snapshot in sp500_hist_components.csv (2026-08-18).
  * 12-1 = C[2026-09-30]/C[2025-10-31]-1 (adjclose month-end) ; RS(6-0) = C[10-30]/C[04-30]-1 ;
    SMA200 = mean of last 200 daily closes incl. 10-30.
Output: results/08_nov2026_signal.csv, results/08_nov2026_decisions.csv
"""
import json, os
import numpy as np, pandas as pd
from _paths import DATA, RESULTS

EXT_1030 = {"SNDK": 1150.89, "MRNA": 221.72, "LITE": 840.70, "MU": 884.74, "SPY": 755.72}
print("[08] Yahoo quote ts 1793390400 =", pd.Timestamp(1793390400, unit="s", tz="UTC").tz_convert("America/New_York"))

def series(tk, field):
    p = f"{DATA}/raw_open/{tk}.json"
    if not os.path.exists(p):
        return None
    j = json.load(open(p))
    return pd.Series(j[field], index=pd.to_datetime(j["dates"]), dtype=float).dropna()

h = pd.read_csv(f"{DATA}/sp500_hist_components.csv", parse_dates=["date"]).sort_values("date")
mem = sorted({t.strip().replace(".", "-") for t in h.iloc[-1]["tickers"].split(",")})
rows = []
for tk in mem:
    a = series(tk, "adjclose")
    if a is None or a.index[0] > pd.Timestamp("2025-10-31"):
        continue
    me = a.resample("ME").last()
    if pd.Timestamp("2025-10-31") not in me.index or pd.Timestamp("2026-09-30") not in me.index:
        continue
    rows.append(dict(ticker=tk, mom_12_1=me["2026-09-30"] / me["2025-10-31"] - 1))
R = pd.DataFrame(rows).sort_values("mom_12_1", ascending=False).head(8).reset_index(drop=True)
R.index += 1

spy_c, spy_a = series("SPY", "close"), series("SPY", "adjclose")
spy_rs_price = EXT_1030["SPY"] / spy_c[:"2026-04-30"].iloc[-1] - 1
spy_rs_tr = EXT_1030["SPY"] / spy_a[:"2026-04-30"].iloc[-1] - 1
spy_rs_stale = spy_c[:"2026-10-27"].iloc[-1] / spy_c[:"2026-04-30"].iloc[-1] - 1   # what Gemini used (10-27, price-only)
out = []
for rank, r in R.iterrows():
    tk = r.ticker; c = series(tk, "close"); a = series(tk, "adjclose")
    has_ext = tk in EXT_1030
    px = EXT_1030.get(tk, c.iloc[-1])
    cc = c.copy()
    if has_ext:
        cc.loc[pd.Timestamp("2026-10-30")] = px
    cc = cc.sort_index()
    sma = cc.iloc[-200:].mean()
    rs = px / c[:"2026-04-30"].iloc[-1] - 1
    out.append(dict(rank_12_1=rank, ticker=tk, mom_12_1_pct=round(r.mom_12_1 * 100, 2),
                    close_used=round(px, 2), close_date="2026-10-30 (external)" if has_ext else f"{c.index[-1].date()} (raw, NOT 10-30)",
                    rs_6_0_pct=round(rs * 100, 2), sma200=round(sma, 2), above_sma200=bool(px > sma),
                    pass_rs_vs_spy_price=bool(rs > spy_rs_price), pass_rs_vs_spy_tr=bool(rs > spy_rs_tr),
                    margin_vs_spy_price_pp=round((rs - spy_rs_price) * 100, 2),
                    margin_vs_spy_tr_pp=round((rs - spy_rs_tr) * 100, 2)))
O = pd.DataFrame(out)
O.to_csv(f"{RESULTS}/08_nov2026_signal.csv", index=False)
print(f"[08] SPY RS(6-0): price-only {spy_rs_price*100:.2f}% | total-return {spy_rs_tr*100:.2f}% | "
      f"stale 10-27 (as in Gemini report) {spy_rs_stale*100:.2f}%")
print(O.to_string(index=False))

def pick(k, sma=None, rs=None):
    g = O.copy()
    if sma == "pass":
        g = g[g.above_sma200]
    slots = []
    for r in g.head(k).itertuples():
        ok = (sma != "gate" or r.above_sma200) and (rs is None or getattr(r, rs))
        slots.append(r.ticker if ok else "CASH")
    return "|".join(slots)
dec = pd.DataFrame([
    dict(strategy="Top-3 + RS(6-0)>SPY (price-only SPY)", allocation=pick(3, rs="pass_rs_vs_spy_price")),
    dict(strategy="Top-3 + RS(6-0)>SPY (total-return SPY)", allocation=pick(3, rs="pass_rs_vs_spy_tr")),
    dict(strategy="Top-1 + RS(6-0)>SPY", allocation=pick(1, rs="pass_rs_vs_spy_tr")),
    dict(strategy="Top-1 + SMA200 pass-down", allocation=pick(1, sma="pass")),
    dict(strategy="Top-1 + SMA200 gate-to-cash", allocation=pick(1, sma="gate")),
    dict(strategy="Top-3 (no filter)", allocation=pick(3)),
])
dec.to_csv(f"{RESULTS}/08_nov2026_decisions.csv", index=False)
print(dec.to_string(index=False))
