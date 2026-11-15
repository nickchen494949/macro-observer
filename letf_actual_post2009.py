#!/usr/bin/env python3
"""letf_actual_post2009.py — actual TQQQ / UPRO / SOXL, 2010-04..2026-10, same variants as the long-run test (2026-11-15).
Month-end decisions; within a month hold weight w (no intra-month rebalance); daily NAV for drawdown. Cash = SGOV from
2020-06, BIL before (Tiingo adjClose). SEP = real ALFRED switch (proxy not needed after 2015-12; before that SEP=ON).
Vol-managed w = min(1, expanding median var21 / var21_t) of the underlying 1x ETF (QQQ / SPY / SMH)."""
import json, os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.abspath(__file__))
E = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
def px(s):
    d = pd.DataFrame(json.load(open(os.path.join(E, f"{s}.json")))); d["date"] = pd.to_datetime(d["date"].str[:10])
    return d.set_index("date")["adjClose"].astype(float).sort_index()
P = {s: px(s) for s in ["TQQQ", "UPRO", "SOXL", "QQQ", "SPY", "SMH", "SGOV", "BIL"]}
R = pd.DataFrame({s: P[s].pct_change() for s in P})
R["CASH"] = np.where(R.index >= "2020-06-01", R["SGOV"], R["BIL"])
REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
SEP = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))
start, end = pd.Timestamp("2010-03-31"), pd.Timestamp("2026-10-30")
idx = R.loc[(R.index > start) & (R.index <= end)].index
mends = [d for d in pd.date_range(start, end, freq="ME")]
def run(lev, und, use_sep, vm):
    var = R[und].rolling(21).var(); med = var.expanding(min_periods=252).median()
    nav = 1.0; navs = {}; mret = {}
    for t in mends:
        days = idx[(idx > t) & (idx <= t + pd.offsets.MonthEnd(1))]
        if not len(days): continue
        on = SEP.get(t, True) if use_sep else True
        w = (min(1.0, med.loc[:t].iloc[-1] / var.loc[:t].iloc[-1]) if vm else 1.0) if on else 0.0
        v0 = nav; a = w; c = 1 - w
        for d in days:
            a *= 1 + R.at[d, lev]; c *= 1 + R.at[d, "CASH"]
            navs[d] = v0 * (a + c)
        nav = navs[days[-1]]; mret[days[-1]] = nav / v0 - 1
    n = pd.Series(navs); m = pd.Series(mret)
    yrs = (n.index[-1] - n.index[0]).days / 365.25
    cagr = n.iloc[-1] ** (1 / yrs) - 1
    sh = m.mean() / m.std() * np.sqrt(12)
    dd = (n / n.cummax() - 1).min()
    yr = m.groupby(m.index.year).apply(lambda x: (1 + x).prod() - 1)
    return cagr, sh, dd, yr.min(), yr.idxmin(), yr.get(2022, np.nan), yr.get(2020, np.nan)
rows = []
VARIANTS = [("1x underlying", None), ("3x buy&hold", (False, False)), ("3x +SEP", (True, False)), ("3x +SEP+vol-managed", (True, True))]
for lev, und in (("TQQQ", "QQQ"), ("UPRO", "SPY"), ("SOXL", "SMH")):
    for nm, cfg in VARIANTS:
        if cfg is None:
            res = run(und, und, False, False)
        else:
            res = run(lev, und, cfg[0], cfg[1])
        c, sh, dd, wy, wyr, y22, y20 = res
        rows.append({"ETF": lev, "variant": nm, "CAGR": c, "Sharpe(monthly)": sh, "Daily MaxDD": dd,
                     "worst year": f"{wyr} {wy:+.0%}", "2020": y20, "2022": y22})
D = pd.DataFrame(rows); pd.set_option("display.width", 220)
print(D.to_string(index=False, float_format=lambda x: f"{x:.2f}" if abs(x) > 5 else f"{x:.1%}"))
D.to_csv(os.path.join(ROOT, "outputs", "improvements_research_20261115", "letf_actual_2010_2026.csv"), index=False)
