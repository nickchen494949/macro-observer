#!/usr/bin/env python3
"""
dashboard_composite_test.py — Can a composite of the dashboard's families decide in/out of index leverage? (2026-11-15)

PRE-SPECIFIED before running (thresholds are textbook/published or the plain 1-sigma rule; nothing tuned):
Flags (True = risk), evaluated at month-end t with data public by t, applied to month t+1:
  SEP    : regime OFF (2Y/core-PCE proxy before 2015-11-30, real ALFRED SEP after)
  VAL    : Shiller CAPE > rolling-120m mean + 1 sd
  FMS    : BofA FMS cash <= 4.0%  (BofA's published 'sell signal' level), last survey dated <= t
  MARGIN : FINRA margin debt YoY (month t-1, publication lag) > rolling-36m mean + 1 sd
  CFTC   : CFTC NQ leveraged-funds net (report dated <= t-3 days) > rolling-156-week mean + 1 sd
  CREDIT : BAA-10Y monthly avg minus prior-12m min > 0.50pp
  SAHM   : real-time Sahm rule (month t-1) >= 0.50
Composite share = flags / available flags. Map: share < 0.25 -> 3x ; 0.25 <= share < 0.5 -> 1x ; share >= 0.5 -> cash.
Variants: C1 composite (SEP is one vote) | C2 SEP hard switch + composite of the other six | C3 C1 + vol management on
the 3x part (w = min(1, median var21 / var21)).
Baselines: 1x, 3x B&H, 3x+SEP, 3x+SEP+VM.
Windows: synthetic 3x Nasdaq Composite 2001-07..2026-10 (FMS starts 2001; CFTC 2006 -> fewer votes before) and
actual QQQ/TQQQ 2010-04..2026-10. Also each flag's standalone forward-return information (NASDAQ next 1M / 3M).
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "dashboard_composite_20261115")
os.makedirs(OUT, exist_ok=True)
bsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bsrc, bs)
fred, yahoo, at, sig = bs["fred"], bs["yahoo"], bs["at"], bs["sig"]


def val(name, key=None):
    j = json.load(open(os.path.join(ROOT, "data", "valuation", f"{name}.json")))
    v = j.get("values", j.get("data", j)) if isinstance(j, dict) else j
    return pd.Series({pd.Timestamp(d): float(x) for d, x in v if x is not None}).sort_index()


REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))
T = [t for t in pd.date_range("2000-12-31", "2026-09-30", freq="ME")]
cape = val("SHILLER_CAPE")
cape_m = cape.resample("ME").last().ffill()
fms = val("BOFA_FMS_CASH")
fin = val("FINRA_MARGIN_YOY")
fin.index = fin.index + pd.offsets.MonthEnd(0)
cftc = val("CFTC_NQ_LEV_NET")

F = {}
for t in T:
    f = {}
    f["SEP"] = not (real_sep[t] if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t]))
    c = cape_m.loc[:t].tail(120)
    f["VAL"] = bool(c.iloc[-1] > c.mean() + c.std()) if len(c) >= 60 else np.nan
    fx = fms.loc[:t]
    f["FMS"] = bool(fx.iloc[-1] <= 4.0) if len(fx) and (t - fx.index[-1]).days < 75 else np.nan
    m = fin.loc[:t - pd.offsets.MonthEnd(1)].tail(36)
    f["MARGIN"] = bool(m.iloc[-1] > m.mean() + m.std()) if len(m) >= 24 else np.nan
    cf = cftc.loc[:t - pd.Timedelta(days=3)].tail(156)
    f["CFTC"] = bool(cf.iloc[-1] > cf.mean() + cf.std()) if len(cf) >= 104 else np.nan
    f["CREDIT"] = not bool(sig["CREDIT"][t])
    f["SAHM"] = not bool(sig["SAHM"][t])
    F[t] = f
F = pd.DataFrame(F).T
F.index.name = "t"
F.to_csv(os.path.join(OUT, "flags_monthly.csv"))
avail = F.notna().sum(axis=1)
share_all = F.astype(float).sum(axis=1, skipna=True) / avail
others = F.drop(columns="SEP")
share_oth = others.astype(float).sum(axis=1, skipna=True) / others.notna().sum(axis=1)


def lev_from(share):
    return 3 if share < 0.25 else (1 if share < 0.5 else 0)


# ---------------------------------------------------------------- standalone information of each flag
ixic = yahoo("_IXIC")
nm = ixic.resample("ME").last()
f1 = nm.shift(-1) / nm - 1
f3 = nm.shift(-3) / nm - 1
info = []
for col in F.columns:
    s = F[col].dropna().astype(bool)
    on, off = s[s].index, s[~s].index
    info.append({"flag": col, "months_flagged": len(on), "months_avail": len(s),
                 "NASDAQ_next1M_flagged": f1.reindex(on).mean(), "NASDAQ_next1M_clear": f1.reindex(off).mean(),
                 "NASDAQ_next3M_flagged": f3.reindex(on).mean(), "NASDAQ_next3M_clear": f3.reindex(off).mean()})
I = pd.DataFrame(info)
I.to_csv(os.path.join(OUT, "flag_standalone_info.csv"), index=False)
pd.set_option("display.width", 260)
print("=== Each flag alone: NASDAQ forward returns when flagged vs clear (2001-2026) ===")
print(I.to_string(index=False, float_format=lambda v: f"{v:+.2%}"))

# ---------------------------------------------------------------- A. synthetic 3x Nasdaq Composite
r_d = ixic.pct_change().dropna()
r_d = r_d[r_d.index >= "2000-01-01"]
rf = (fred("DGS3MO") / 100).reindex(r_d.index).ffill()
LEV = {L: L * r_d - (L - 1) * (rf + 0.005) / 252 - (0.0095 / 252 if L > 1 else 0) for L in (1, 3)}
cash = rf / 252
var21 = ixic.pct_change().rolling(21).var()
medv = var21.expanding(min_periods=252).median()


def sim(levmap, vm=False):
    out, prev = {}, None
    for t in T:
        days = r_d.loc[(r_d.index > t) & (r_d.index <= t + pd.offsets.MonthEnd(1))].index
        if not len(days) or t < pd.Timestamp("2001-06-30"):
            continue
        L = levmap(t)
        w = 1.0
        if vm and L == 3:
            w = min(1.0, medv.loc[:t].iloc[-1] / var21.loc[:t].iloc[-1])
        g = (1 + LEV[L].loc[days]).prod() - 1 if L else 0.0
        c = (1 + cash.loc[days]).prod() - 1
        ret = (w * g + (1 - w) * c) if L else c
        cost = 0.002 if (prev is not None and L != prev) else 0.0
        prev = L
        out[t + pd.offsets.MonthEnd(1)] = (1 + ret) * (1 - cost) - 1
    return pd.Series(out)


def perf(r, a=None, b=None):
    r = r.loc[a:b] if a else r
    w = (1 + r).cumprod()
    return w.iloc[-1] ** (12 / len(r)) - 1, r.mean() / r.std() * np.sqrt(12), (w / w.cummax() - 1).min()


S = {"1x buy&hold": lambda t: 1, "3x buy&hold": lambda t: 3, "3x +SEP": lambda t: 0 if F.at[t, "SEP"] else 3}
strategies = {k: sim(v) for k, v in S.items()}
strategies["3x +SEP +VM"] = sim(S["3x +SEP"], vm=True)
strategies["C1 composite (SEP = 1 vote)"] = sim(lambda t: lev_from(share_all[t]))
strategies["C2 SEP switch + composite of others"] = sim(lambda t: 0 if F.at[t, "SEP"] else lev_from(share_oth[t]))
strategies["C3 C1 + vol-managed 3x"] = sim(lambda t: lev_from(share_all[t]), vm=True)
rows = []
for k, r in strategies.items():
    row = {"strategy": k}
    for a, b, lab in (("2001-07", "2026-10", "01-26"), ("2001-07", "2008-12", "01-08"), ("2009-01", "2026-10", "09-26"), ("2007-01", "2009-12", "07-09")):
        c, s, d = perf(r, a, b)
        row[f"CAGR_{lab}"], row[f"MDD_{lab}"] = c, d
        if lab == "01-26":
            row["Sharpe_01-26"] = s
    rows.append(row)
A = pd.DataFrame(rows)
A.to_csv(os.path.join(OUT, "A_synthetic_3x_nasdaq_2001_2026.csv"), index=False)
print("\n=== A. synthetic 3x Nasdaq Composite, 2001-07..2026-10 ===")
print(A.to_string(index=False, float_format=lambda v: f"{v:.1%}" if abs(v) < 5 else f"{v:.2f}"))
lv = pd.Series({t: lev_from(share_all[t]) for t in T if t >= pd.Timestamp("2001-06-30")})
print("C1 months at 3x / 1x / cash:", int((lv == 3).sum()), int((lv == 1).sum()), int((lv == 0).sum()))

# ---------------------------------------------------------------- B. actual QQQ/TQQQ
E = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")


def px(s):
    d = pd.DataFrame(json.load(open(os.path.join(E, f"{s}.json"))))
    d["date"] = pd.to_datetime(d["date"].str[:10])
    return d.set_index("date")["adjClose"].astype(float).sort_index()


P = {s: px(s) for s in ["QQQ", "TQQQ", "SGOV", "BIL"]}
R = pd.DataFrame({s: P[s].pct_change() for s in P})
R["CASH"] = np.where(R.index >= "2020-06-01", R["SGOV"], R["BIL"])
qv = P["QQQ"].pct_change().rolling(21).var()
qmed = qv.expanding(min_periods=252).median()
idx = R.loc[(R.index > "2010-03-31") & (R.index <= "2026-10-30")].index
FUND = {3: "TQQQ", 1: "QQQ"}


def actual(levmap, vm=False):
    nav, navs, prev, mret = 1.0, {}, None, {}
    for t in [t for t in T if t >= pd.Timestamp("2010-03-31")]:
        days = idx[(idx > t) & (idx <= t + pd.offsets.MonthEnd(1))]
        if not len(days):
            continue
        L = levmap(t)
        w = min(1.0, qmed.loc[:t].iloc[-1] / qv.loc[:t].iloc[-1]) if (vm and L == 3) else 1.0
        if prev is not None and L != prev:
            nav *= 0.998
        prev = L
        v0, a, c = nav, w, 1 - w
        for d in days:
            if L:
                a *= 1 + R.at[d, FUND[L]]
                c *= 1 + R.at[d, "CASH"]
            else:
                a, c = 0.0, c * (1 + R.at[d, "CASH"]) if c else (1 + R.at[d, "CASH"]) * (a + c)
            navs[d] = v0 * (a + c)
        nav = navs[days[-1]]
        mret[days[-1]] = nav / v0 - 1
    n, m = pd.Series(navs), pd.Series(mret)
    yrs = (n.index[-1] - n.index[0]).days / 365.25
    return n.iloc[-1] ** (1 / yrs) - 1, m.mean() / m.std() * np.sqrt(12), (n / n.cummax() - 1).min()


rows = []
for k, (fn, vm) in {"QQQ": (S["1x buy&hold"], False), "TQQQ": (S["3x buy&hold"], False), "TQQQ +SEP": (S["3x +SEP"], False),
                    "TQQQ +SEP +VM": (S["3x +SEP"], True), "C1 composite": (lambda t: lev_from(share_all[t]), False),
                    "C2 SEP + composite of others": (lambda t: 0 if F.at[t, "SEP"] else lev_from(share_oth[t]), False),
                    "C3 C1 + VM": (lambda t: lev_from(share_all[t]), True)}.items():
    c, s, d = actual(fn, vm)
    rows.append({"strategy": k, "CAGR": c, "Sharpe": s, "DailyMaxDD": d})
B = pd.DataFrame(rows)
B.to_csv(os.path.join(OUT, "B_actual_2010_2026.csv"), index=False)
print("\n=== B. actual QQQ/TQQQ 2010-04..2026-10 ===")
print(B.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
print("\nLatest flags (formation 2026-09-30):", F.iloc[-1].to_dict(), "share:", round(share_all.iloc[-1], 2))
