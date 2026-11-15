#!/usr/bin/env python3
"""
dip_ladder_leverage.py — "Lever up on drawdowns": 1x normally, 2x / 3x when the index is far below its high (2026-11-15)

PRE-SPECIFIED before running:
  At each month-end t, dd = index close / running max - 1 (ATH basis; variant D4 uses 252-day high).
  Main D1: dd > -10% -> 1x ; -20% < dd <= -10% -> 2x ; dd <= -20% -> 3x.  D2: -15/-30.  D3: -20/-40.  D4: D1 on 52w high.
  Leverage held for month t+1 as a daily-reset L-x fund (same cost model as earlier). Switching cost 2 x 10bp of NAV
  whenever L changes. "+SEP": regime OFF -> cash (SEP proxy pre-2015-11, real SEP after).
  Synthetic 1985-2026 on Nasdaq Composite and S&P 500 (+div); actual QQQ/QLD/TQQQ 2010-04..2026-10.
  Mechanism note (written beforehand): growth-optimal leverage L* = mu/sigma^2 falls when volatility rises, and
  drawdowns are high-volatility periods -> this rule raises leverage exactly when L* is lowest. It wins only if
  rebounds are reliable (post-2009 'Fed put'); it should fail in long busts (2000-02, 2007-09).
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "improvements_research_20261115")
src = open(os.path.join(ROOT, "letf_upro_soxl_longrun.py")).read().split("rows = []")[0]
ns = {"__file__": os.path.join(ROOT, "letf_upro_soxl_longrun.py")}
exec(src, ns)
perf, rf_full, sep_on = ns["perf"], ns["rf_full"], ns["sep_on"]
U = {"Nasdaq": ns["UNDER"]["Nasdaq Comp (TQQQ-like)"], "S&P 500": ns["UNDER"]["S&P 500 (UPRO-like)"]}
RULES = {"D1 ATH -10/-20": ("ath", -0.10, -0.20), "D2 ATH -15/-30": ("ath", -0.15, -0.30),
         "D3 ATH -20/-40": ("ath", -0.20, -0.40), "D4 52wHigh -10/-20": ("52w", -0.10, -0.20)}


def ladder(r_d, rule=None, fixed=None, use_sep=False, vm=False):
    rf = rf_full.reindex(r_d.index).ffill()
    lev = {L: L * r_d - (L - 1) * (rf + 0.005) / 252 - (0.0095 / 252 if L > 1 else 0) for L in (1, 2, 3)}
    cash = rf / 252
    lvl = (1 + r_d).cumprod()
    ath = lvl.cummax()
    h52 = lvl.rolling(252, min_periods=1).max()
    var21 = r_d.rolling(21).var()
    medv = var21.expanding(min_periods=252).median()
    me = r_d.index.to_series().groupby(r_d.index.to_period("M")).max()
    out, prevL, Ls = {}, None, {}
    for t in me.values[:-1]:
        t = pd.Timestamp(t)
        tm = t + pd.offsets.MonthEnd(0)
        if tm > pd.Timestamp("2026-09-30"):
            continue
        days = r_d.loc[(r_d.index > t) & (r_d.index <= tm + pd.offsets.MonthEnd(1))].index
        if not len(days):
            continue
        if fixed:
            L = fixed
        else:
            base, a, b = rule
            dd = lvl[t] / (ath[t] if base == "ath" else h52[t]) - 1
            L = 1 if dd > a else (2 if dd > b else 3)
        on = sep_on.get(tm, True) if use_sep else True
        w = 1.0 if on else 0.0
        if vm and on and np.isfinite(medv.loc[:t].iloc[-1]):
            w = min(1.0, medv.loc[:t].iloc[-1] / var21.loc[:t].iloc[-1])
        cost = 0.002 if (prevL is not None and (L, on) != prevL) else 0.0
        prevL = (L, on)
        ret = w * ((1 + lev[L].loc[days]).prod() - 1) + (1 - w) * ((1 + cash.loc[days]).prod() - 1)
        out[days[-1] + pd.offsets.MonthEnd(0)] = (1 + ret) * (1 - cost) - 1
        Ls[tm] = L if on else 0
    return pd.Series(out), pd.Series(Ls)


rows = []
for uname, r in U.items():
    cases = {"1x buy&hold": dict(fixed=1), "2x buy&hold": dict(fixed=2), "3x buy&hold": dict(fixed=3),
             "3x +SEP +VM (reference)": dict(fixed=3, use_sep=True, vm=True)}
    for rn, rule in RULES.items():
        cases[rn] = dict(rule=rule)
        cases[rn + " +SEP"] = dict(rule=rule, use_sep=True)
    for cname, kw in cases.items():
        m, Ls = ladder(r, **kw)
        row = {"index": uname, "strategy": cname, "months_at_3x": int((Ls == 3).sum()), "months_at_2x": int((Ls == 2).sum())}
        for a, b, lab in (("1985-01", "2026-10", "85-26"), ("1985-01", "2008-12", "85-08"), ("2009-01", "2026-10", "09-26"),
                          ("2000-01", "2002-12", "00-02"), ("2007-01", "2009-12", "07-09")):
            c, sh, d = perf(m.loc[a:b])
            row[f"CAGR_{lab}"], row[f"MDD_{lab}"] = c, d
        rows.append(row)
A = pd.DataFrame(rows)
A.to_csv(os.path.join(OUT, "dip_ladder_synthetic_1985_2026.csv"), index=False)
pd.set_option("display.width", 280)
print("=== A. synthetic 1985-2026 ===")
print(A.to_string(index=False, float_format=lambda v: f"{v:.1%}"))

# ---------------- B. actual QQQ / QLD / TQQQ, 2010-04..2026-10
E = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")


def px(s):
    d = pd.DataFrame(json.load(open(os.path.join(E, f"{s}.json"))))
    d["date"] = pd.to_datetime(d["date"].str[:10])
    return d.set_index("date")["adjClose"].astype(float).sort_index()


P = {s: px(s) for s in ["QQQ", "QLD", "TQQQ", "SGOV", "BIL"]}
R = pd.DataFrame({s: P[s].pct_change() for s in P})
R["CASH"] = np.where(R.index >= "2020-06-01", R["SGOV"], R["BIL"])
REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
SEP = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))
qlvl = P["QQQ"]
qath = qlvl.cummax()
q52 = qlvl.rolling(252, min_periods=1).max()
start, end = pd.Timestamp("2010-03-31"), pd.Timestamp("2026-10-30")
idx = R.loc[(R.index > start) & (R.index <= end)].index
FUND = {1: "QQQ", 2: "QLD", 3: "TQQQ"}


def actual(rule=None, fixed=None, use_sep=False):
    nav, navs, prev, mret = 1.0, {}, None, {}
    for t in pd.date_range(start, end, freq="ME"):
        days = idx[(idx > t) & (idx <= t + pd.offsets.MonthEnd(1))]
        if not len(days):
            continue
        tt = qlvl.index[qlvl.index <= t][-1]
        if fixed:
            L = fixed
        else:
            base, a, b = rule
            dd = qlvl[tt] / (qath[tt] if base == "ath" else q52[tt]) - 1
            L = 1 if dd > a else (2 if dd > b else 3)
        on = SEP.get(t, True) if use_sep else True
        key = (L, on)
        if prev is not None and key != prev:
            nav *= 0.998
        prev = key
        v0 = nav
        for d in days:
            nav *= 1 + (R.at[d, FUND[L]] if on else R.at[d, "CASH"])
            navs[d] = nav
        mret[days[-1]] = nav / v0 - 1
    n, m = pd.Series(navs), pd.Series(mret)
    yrs = (n.index[-1] - n.index[0]).days / 365.25
    return n.iloc[-1] ** (1 / yrs) - 1, m.mean() / m.std() * np.sqrt(12), (n / n.cummax() - 1).min()


rows = []
cases = {"QQQ": dict(fixed=1), "QLD": dict(fixed=2), "TQQQ": dict(fixed=3), "QQQ +SEP": dict(fixed=1, use_sep=True),
         "TQQQ +SEP": dict(fixed=3, use_sep=True)}
for rn, rule in RULES.items():
    cases[rn] = dict(rule=rule)
    cases[rn + " +SEP"] = dict(rule=rule, use_sep=True)
for cname, kw in cases.items():
    c, s, d = actual(**kw)
    rows.append({"strategy": cname, "CAGR": c, "Sharpe": s, "DailyMaxDD": d})
B = pd.DataFrame(rows)
B.to_csv(os.path.join(OUT, "dip_ladder_actual_2010_2026.csv"), index=False)
print("\n=== B. actual QQQ/QLD/TQQQ 2010-04..2026-10 ===")
print(B.to_string(index=False, float_format=lambda v: f"{v:.2f}" if abs(v) > 5 else f"{v:.3f}"))
