#!/usr/bin/env python3
"""
letf_2x_vs_3x.py — 2x (QLD/SSO-like) vs 3x (TQQQ/UPRO-like) vs 1x, same engine and variants (2026-11-15).
PRE-SPECIFIED: Part A synthetic 1985-2026 (Nasdaq Composite price; S&P 500 + dividends), L in {1,2,3},
variants buy&hold / +SEP / +SEP+vol-managed; windows full, 1985-2008, 2009-2026, 2000-02, 2007-09.
2x cost model: 2r - (rf+0.5%)/252 - 0.95%/252 (same formula with L=2).
Part B actual ETFs 2010-04..2026-10: QQQ/QLD/TQQQ and SPY/SSO/UPRO with the same three variants.
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "improvements_research_20261115")
src = open(os.path.join(ROOT, "letf_upro_soxl_longrun.py")).read().split("rows = []")[0]
ns = {"__file__": os.path.join(ROOT, "letf_upro_soxl_longrun.py")}
exec(src, ns)
run, perf = ns["run"], ns["perf"]
U = {"Nasdaq": ns["UNDER"]["Nasdaq Comp (TQQQ-like)"], "S&P 500": ns["UNDER"]["S&P 500 (UPRO-like)"]}
rows = []
for uname, r in U.items():
    for L in (1, 2, 3):
        for vname, (s, vm) in {"buy&hold": (False, False), "+SEP": (True, False), "+SEP+VM": (True, True)}.items():
            if L == 1 and vname != "buy&hold":
                continue
            m = run(r, L, s, vm)
            row = {"index": uname, "lev": f"{L}x", "variant": vname}
            for a, b, lab in (("1985-01", "2026-10", "85-26"), ("1985-01", "2008-12", "85-08"), ("2009-01", "2026-10", "09-26"),
                              ("2000-01", "2002-12", "00-02"), ("2007-01", "2009-12", "07-09")):
                c, sh, d = perf(m.loc[a:b])
                row[f"CAGR_{lab}"], row[f"MDD_{lab}"] = c, d
                if lab == "85-26":
                    row["Sharpe_85-26"] = sh
            rows.append(row)
A = pd.DataFrame(rows)
A.to_csv(os.path.join(OUT, "letf_2x_vs_3x_synthetic.csv"), index=False)
pd.set_option("display.width", 260)
print("=== A. synthetic 1985-2026 ===")
print(A.to_string(index=False, float_format=lambda v: f"{v:.1%}"))

bsrc = open(os.path.join(ROOT, "letf_actual_post2009.py")).read().split("rows = []")[0]
b = {"__file__": os.path.join(ROOT, "letf_actual_post2009.py")}
exec(bsrc.replace('P = {s: px(s) for s in ["TQQQ", "UPRO", "SOXL", "QQQ", "SPY", "SMH", "SGOV", "BIL"]}',
                  'P = {s: px(s) for s in ["TQQQ", "UPRO", "QLD", "SSO", "QQQ", "SPY", "SGOV", "BIL"]}'), b)
rows = []
for und, levs in (("QQQ", ["QQQ", "QLD", "TQQQ"]), ("SPY", ["SPY", "SSO", "UPRO"])):
    for lev in levs:
        for vname, (s, vm) in {"buy&hold": (False, False), "+SEP": (True, False), "+SEP+VM": (True, True)}.items():
            c, sh, dd, wy, wyr, y22, y20 = b["run"](lev, und, s, vm)
            rows.append({"ETF": lev, "variant": vname, "CAGR": c, "Sharpe": sh, "DailyMaxDD": dd, "worst year": f"{wyr} {wy:+.0%}", "2020": y20, "2022": y22})
B = pd.DataFrame(rows)
B.to_csv(os.path.join(OUT, "letf_2x_vs_3x_actual_2010_2026.csv"), index=False)
print("\n=== B. actual ETFs 2010-04..2026-10 ===")
print(B.to_string(index=False, float_format=lambda v: f"{v:.2f}" if abs(v) > 5 else f"{v:.1%}"))
