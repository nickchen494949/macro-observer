#!/usr/bin/env python3
"""
letf_universe_scan.py — Which underlyings tolerate 3x daily leverage? (2026-11-15)

PRE-SPECIFIED: mechanism first. Long-run growth of a daily-reset L-x fund ~ L*mu - (L-1)*borrow - 0.5*L^2*sigma^2,
so the growth-optimal leverage is L* = (mu - r) / sigma^2. An underlying is a good 3x candidate only if L* is
comfortably >= 3 AND its 1x drawdowns are not so deep that 3x is wiped out.
Underlyings (Tiingo adjClose unless noted): S&P 500 (^GSPC + dividends, 1985+), Nasdaq Composite (^IXIC price, 1985+),
XLK XLF XLV XLE XLU XLP XLY XLI XLB (1999+), SMH (2000-06+), TLT (2002+), GLD (2004+), IWM and IBB (Yahoo close,
price only, dividends missing -> slightly understated).
Per underlying: mu, sigma, L* over its full history; synthetic 3x (same cost model as earlier: 3r - 2(rf+0.5%)/252
- 0.95%/252) buy&hold, +SEP, +SEP+vol-managed; windows full history and 2010-04..2026-10.
Plus the well-known HFEA portfolio: 55% 3x S&P + 45% 3x TLT, quarterly rebalance, 2002-08+ (no SEP).
Real 3x ETFs on narrow sectors usually cost more (swap spreads) than this model assumes -> synthetic is optimistic.
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
run, perf, etf, yahoo, rf_full = ns["run"], ns["perf"], ns["etf"], ns["yahoo"], ns["rf_full"]
U = {"S&P 500": ns["spx_r"], "Nasdaq Composite": ns["UNDER"]["Nasdaq Comp (TQQQ-like)"]}
for s in ["XLK", "XLF", "XLV", "XLE", "XLU", "XLP", "XLY", "XLI", "XLB", "SMH", "TLT", "GLD"]:
    U[s] = etf(s).pct_change().dropna()
for s in ["IWM", "IBB"]:
    U[s + " (price only)"] = yahoo(s).pct_change().dropna()

rows = []
for name, r in U.items():
    r = r[r.index >= "1985-01-01"]
    rf = rf_full.reindex(r.index).ffill()
    mu = r.mean() * 252
    sig = r.std() * np.sqrt(252)
    lstar = (mu - rf.mean()) / sig ** 2
    one = (1 + r).cumprod()
    m1 = run(r, 1, False, False)
    b3, s3, v3 = run(r, 3, False, False), run(r, 3, True, False), run(r, 3, True, True)
    row = {"underlying": name, "start": r.index[0].strftime("%Y-%m"), "mu": mu, "sigma": sig, "L*": lstar,
           "1x CAGR": perf(m1)[0], "1x MDD": (one / one.cummax() - 1).min(),
           "3x B&H CAGR": perf(b3)[0], "3x B&H MDD": perf(b3)[2],
           "3x+SEP CAGR": perf(s3)[0], "3x+SEP MDD": perf(s3)[2],
           "3x+SEP+VM CAGR": perf(v3)[0], "3x+SEP+VM MDD": perf(v3)[2],
           "3x+SEP CAGR 2010-26": perf(s3.loc["2010-04":"2026-10"])[0], "3x+SEP MDD 2010-26": perf(s3.loc["2010-04":"2026-10"])[2]}
    rows.append(row)
D = pd.DataFrame(rows).sort_values("L*", ascending=False)
D.to_csv(os.path.join(OUT, "letf_universe_scan.csv"), index=False)
pd.set_option("display.width", 280)
print(D.to_string(index=False, float_format=lambda v: f"{v:.2f}" if abs(v) >= 1.5 else f"{v:.1%}"))

# HFEA 55/45 3x S&P / 3x TLT quarterly, 2002-08+
spx, tlt = U["S&P 500"], U["TLT"]
idx = spx.index.intersection(tlt.index)
idx = idx[idx >= "2002-08-01"]
rf = rf_full.reindex(idx).ffill()
x = lambda r: 3 * r.reindex(idx) - 2 * (rf + 0.005) / 252 - 0.0095 / 252
A, B = x(spx), x(tlt)
w = np.array([0.55, 0.45])
nav, navs = 1.0, []
qend = set(pd.Series(idx, index=idx).groupby(idx.to_period("Q")).max())
for d in idx:
    rr = np.array([A[d], B[d]])
    p = w @ rr
    nav *= 1 + p
    w = w * (1 + rr) / (1 + p)
    if d in qend:
        nav *= 1 - 0.001 * np.abs(w - [0.55, 0.45]).sum()
        w = np.array([0.55, 0.45])
    navs.append(nav)
n = pd.Series(navs, index=idx)
yrs = (idx[-1] - idx[0]).days / 365.25
yr = n.resample("YE").last().pct_change()
print(f"\nHFEA 55% 3x S&P + 45% 3x TLT (quarterly), {idx[0]:%Y-%m}..{idx[-1]:%Y-%m}: CAGR {(n.iloc[-1]) ** (1 / yrs) - 1:.1%}, "
      f"MaxDD {(n / n.cummax() - 1).min():.1%}, 2008 {yr.get(pd.Timestamp('2008-12-31'), np.nan):+.1%}, 2022 {yr.get(pd.Timestamp('2022-12-31'), np.nan):+.1%}")
