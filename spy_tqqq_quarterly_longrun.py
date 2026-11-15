#!/usr/bin/env python3
"""
spy_tqqq_quarterly_longrun.py — Does SPY + 3x Nasdaq with quarterly rebalancing survive 1985-2026? (2026-11-15)

PRE-SPECIFIED before running:
  SPY proxy = ^GSPC daily price + dividend yield (data/valuation/SP500_DIV_YIELD.json, monthly, ffilled; last value
  carried after 2025-12) / 252. 3x = synthetic daily-reset 3x ^IXIC (same formula as improvements_research.py:
  3r - 2(rf+0.5%)/252 - 0.95%/252; Composite is less volatile than NDX and has no dividends -> 3x leg is flattered
  in crashes? no: understated vol -> crash losses understated; treat 3x results as optimistic). Cash = DGS3MO.
  Mixes (SPY/Cash/3x): 100/0/0, 90/0/10, 80/0/20, 70/0/30, 50/0/50, 60/20/20, 40/40/20, 0/0/100.
  Rebalance to target at each quarter-end close (Mar/Jun/Sep/Dec); weights drift daily in between; 10bp/side.
  "+SEP": at month-end, if regime OFF (SEP proxy before 2015-11-30, real SEP after) hold 100% cash next month; on
  return to ON, re-establish targets immediately.
  Windows: 1985-2026, 1985-2008, 2009-2026, 2000-2002, 2007-2009.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "improvements_research_20261115")
src = open(os.path.join(ROOT, "improvements_research.py")).read().split("rf_m = (1 + cash_d)")[0]
ns = {"__file__": os.path.join(ROOT, "improvements_research.py")}
exec(src, ns)
yahoo, r_d, rf_d, lev, sep_on = ns["yahoo"], ns["r_d"], ns["rf_d"], ns["lev"], ns["sep_on"]
gspc = yahoo("_GSPC")
dy = json.load(open(os.path.join(ROOT, "data", "valuation", "SP500_DIV_YIELD.json")))
dy = dy.get("values", dy) if isinstance(dy, dict) else dy
dy = pd.Series({pd.Timestamp(d): float(x) for d, x in dy}).sort_index()
idx = r_d.index
spy_r = gspc.pct_change().reindex(idx).fillna(0) + dy.reindex(idx, method="ffill") / 100 / 252
x3 = lev[3].reindex(idx)
cash_r = rf_d.reindex(idx) / 252
R = pd.DataFrame({"SPY": spy_r, "CASH": cash_r, "X3": x3}).dropna()
R = R[R.index >= "1985-01-01"]
qend = set(R.index.to_series().groupby(R.index.to_period("Q")).max())
mend = R.index.to_series().groupby(R.index.to_period("M")).max()
mend_set = set(mend)


def regime_on(day):
    t = (day + pd.offsets.MonthEnd(0))
    return sep_on.get(t, True)


def sim(target, use_sep):
    tgt = np.array(target, float)
    w = tgt.copy()
    nav, navs = 1.0, []
    state_on = True
    for i, (d, row) in enumerate(R.iterrows()):
        r = row.values
        port = float(np.dot(w, r))
        nav *= 1 + port
        w = w * (1 + r) / (1 + port)
        navs.append(nav)
        new = None
        if d in mend_set and use_sep:
            on_next = sep_on.get(d + pd.offsets.MonthEnd(0), True)
            if not on_next:
                new = np.array([0, 1, 0], float)
            elif not state_on:
                new = tgt.copy()
            state_on = on_next
        if d in qend and new is None and (state_on or not use_sep):
            new = tgt.copy()
        if new is not None:
            to = np.abs(new - w).sum()
            nav *= 1 - 0.001 * to
            navs[-1] = nav
            w = new
    return pd.Series(navs, index=R.index)


def stats(nav, a, b):
    s = nav.loc[a:b]
    if len(s) < 20:
        return np.nan, np.nan
    base = nav.loc[:a].iloc[-2] if len(nav.loc[:a]) > 1 else s.iloc[0]
    yrs = (s.index[-1] - s.index[0]).days / 365.25
    cagr = (s.iloc[-1] / base) ** (1 / yrs) - 1
    path = pd.concat([pd.Series([base]), s])
    mdd = (path / path.cummax() - 1).min()
    return cagr, mdd


mixes = {"100/0/0 SPY": (1, 0, 0), "90/0/10": (.9, 0, .1), "80/0/20": (.8, 0, .2), "70/0/30": (.7, 0, .3),
         "50/0/50": (.5, 0, .5), "60/20/20": (.6, .2, .2), "40/40/20": (.4, .4, .2), "0/0/100 3x": (0, 0, 1)}
rows = []
for sep in (False, True):
    for name, m in mixes.items():
        nav = sim(m, sep)
        row = {"mix (SPY/Cash/3x)": name, "SEP": "yes" if sep else "no"}
        for a, b, lab in (("1985-01-01", "2026-10-31", "85-26"), ("1985-01-01", "2008-12-31", "85-08"), ("2009-01-01", "2026-10-31", "09-26"),
                          ("2000-01-01", "2002-12-31", "00-02"), ("2007-01-01", "2009-12-31", "07-09")):
            c, d = stats(nav, a, b)
            row[f"CAGR_{lab}"], row[f"MDD_{lab}"] = c, d
        rows.append(row)
D = pd.DataFrame(rows)
D.to_csv(os.path.join(OUT, "spy_tqqq_quarterly_1985_2026.csv"), index=False)
pd.set_option("display.width", 260)
print(D.to_string(index=False, float_format=lambda v: f"{v:.1%}"))
