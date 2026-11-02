#!/usr/bin/env python3
"""
02 — INDEPENDENT engine vs Gemini ledgers (Gemini ledgers are the COMPARISON TARGET only).
rf comes from raw FRED DGS3MO (not from the Gemini ledger). Also checks that the ledger's rf column
equals raw FRED rf.
Output: results/02_compare_summary.csv, results/02_mismatch_months.csv
"""
import pandas as pd, numpy as np
from _paths import WORK, RESULTS, gemini_ledger, raw_rf_monthly
from claude_engine import simulate, cagr, mdd

P = pd.read_parquet(f"{WORK}/claude_panel.parquet")
rf = raw_rf_monthly()

CASES = [
    ("Top-1 + SMA200 pass-down, next-day open", dict(k=1, sma="pass"), "v2_06_ledger_sp500_top1_sma200_oo.csv", False),
    ("Top-3 + RS(6-0)>SPY, next-day open", dict(k=3, rs="r60", bench="spy60"), "v2_06_ledger_sp500_top3_oo_rs60.csv", True),
    ("Top-1 + SMA200 pass-down, close-close", dict(k=1, sma="pass", ret="rcc", drift=False), "v2_06_ledger_sp500_top1_sma200_cc.csv", False),
    ("Top-3 + RS(6-0)>SPY, close-close", dict(k=3, rs="r60", bench="spy60", ret="rcc", drift=False), "v2_06_ledger_sp500_top3_cc_rs60.csv", True),
]
summ, mism = [], []
for name, kw, f, setwise in CASES:
    mine = simulate(P, **kw)
    L = pd.read_csv(gemini_ledger(f), parse_dates=["month"]).set_index("month")
    idx = L.index.intersection(mine.index)
    rf_diff = float((rf.reindex(idx) - L.loc[idx, "rf"]).abs().max())
    if setwise:
        eq = pd.Series([set(mine.at[i, "picks"].split("|")) == set(L.at[i, "picks"].split("|")) for i in idx], index=idx)
    else:
        eq = pd.Series([mine.at[i, "picks"] == L.at[i, "picks"] for i in idx], index=idx)
    gd = (mine.loc[idx, "gross"] - L.loc[idx, "gross"]).abs()
    row = dict(case=name, months=len(idx), pick_match=int(eq.sum()), gross_diff_gt_50bp=int((gd > 0.005).sum()),
               rf_max_abs_diff_vs_raw_fred=rf_diff)
    for a in ["2010", "2015"]:
        row[f"cagr_{a}_claude"] = round(cagr(mine.loc[a:"2026-09", "net"]) * 100, 2)
        row[f"cagr_{a}_gemini"] = round(cagr(L.loc[a:"2026-09", "net"]) * 100, 2)
        row[f"mdd_{a}_claude"] = round(mdd(mine.loc[a:"2026-09", "net"]) * 100, 2)
        row[f"mdd_{a}_gemini"] = round(mdd(L.loc[a:"2026-09", "net"]) * 100, 2)
    summ.append(row)
    print(f"[02] {name}: picks {eq.sum()}/{len(idx)} | rf diff vs raw FRED {rf_diff:.1e} | "
          f"CAGR10 C={row['cagr_2010_claude']} G={row['cagr_2010_gemini']} | CAGR15 C={row['cagr_2015_claude']} G={row['cagr_2015_gemini']}")
    for i in idx[(~eq.values) | (gd.values > 0.005)]:
        mism.append(dict(case=name, month=i.date(), formation=(i - pd.offsets.MonthEnd(1)).date(),
                         claude=mine.at[i, "picks"], gemini=L.at[i, "picks"],
                         gross_claude=round(mine.at[i, "gross"], 4), gross_gemini=round(L.at[i, "gross"], 4)))
pd.DataFrame(summ).to_csv(f"{RESULTS}/02_compare_summary.csv", index=False)
pd.DataFrame(mism).to_csv(f"{RESULTS}/02_mismatch_months.csv", index=False)
