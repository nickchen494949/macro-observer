import os
import pandas as pd, numpy as np
D = "/Users/happygolucky/Desktop/宏观观察器/outputs/gemini_full_data_audit_20261031/v2_standalone/"

def cagr(r): return (1 + r).prod() ** (12 / len(r)) - 1
def mdd(r):
    e = (1 + r).cumprod(); return (e / e.cummax() - 1).min()

# Recompute headline numbers from saved ledgers
for f in ["v2_06_ledger_sp500_top3_oo_rs60.csv", "v2_06_ledger_sp500_top1_sma200_oo.csv",
          "v2_06_ledger_sp500_top1_sma200_cc.csv", "v2_06_ledger_sp500_top3_cc_rs60.csv"]:
    L = pd.read_csv(D + f, parse_dates=["month"]).set_index("month")
    for a in ["2010", "2015"]:
        s = L.loc[a:"2026-09", "net"]
        print(f"{f:45s} {a}-2026  n={len(s)} CAGR={cagr(s)*100:6.2f}% MDD={mdd(s)*100:6.2f}% cash={L.loc[a:'2026-09','cash_frac'].mean()*100:4.1f}%")

# Paired monthly difference RS vs baseline, from v2_07 is not saved per month -> rebuild from v2_06 summary? use v2_06 ledgers:
# Top-3 OO: baseline not saved as ledger; reconstruct baseline via v2_07 module is Gemini code. Instead use Top-1 CC rs60 ledger vs pure Top-1 ledger in project.
R = pd.read_csv(D + "v2_06_ledger_sp500_top1_cc_rs60.csv", parse_dates=["month"]).set_index("month")
B = pd.read_csv("/Users/happygolucky/Desktop/宏观观察器/research/sector_stock_momentum/results/ml/sma200_pure_momentum_top_1.csv")
B["month"] = pd.to_datetime(B["month"]) + pd.offsets.MonthEnd(0); B = B.set_index("month")
idx = R.loc["2015":"2026-09"].index
d = (R.loc[idx, "net"] - B.loc[idx, "net"])
print("\nTop-1 CC  RS vs baseline 2015-2026: months differing =", (d.abs() > 1e-9).sum())
lr = np.log1p(R.loc[idx, "net"]) - np.log1p(B.loc[idx, "net"])
top = lr.sort_values(ascending=False)
print("log-return contribution by month (top 5):"); print(top.head(5).round(4).to_string())
print("total log gain", round(lr.sum(), 4), "| excl. top-2 months", round(lr.sum() - top.head(2).sum(), 4))
print("annualised gain excl top-2:", round((np.exp((lr.sum() - top.head(2).sum()) * 12 / len(lr)) - 1) * 100, 2), "%/yr")
# sign test / bootstrap over differing months
nz = lr[lr.abs() > 1e-9]
print("differing months:", len(nz), "wins:", (nz > 0).sum(), "losses:", (nz < 0).sum())
rng = np.random.default_rng(0)
bs = [rng.choice(lr.values, len(lr), replace=True).sum() for _ in range(20000)]
print("bootstrap P(total gain<=0) =", np.mean(np.array(bs) <= 0).round(3))
