#!/usr/bin/env python3
"""
v4_multipool_test.py — V4 selection rule applied to three pools (QQQ / XLK / SPY), overlap allowed (2026-11-15).
PRE-SPECIFIED before running (another test on the same 2009-2026 data -> treat gains with a multiple-testing haircut):
  SEP=ON : 1/3 per pool; each pool = 12-1 Sharpe ranking, Buy Top-2 / Hold<=5 -> each stock 1/6; same stock in several
           pools = weights add (max 50%). Pools: QQQ = PIT Nasdaq-100; XLK = PIT S&P 500 Information Technology;
           SPY = PIT S&P 500 (all sectors).
  SEP=OFF: unchanged V4 (BestSec top-2 Sharpe + 50% SGOV). No Election Reset. Costs 10bp/side, netted.
  Comparisons: V4; 3-pool dedup (overlap -> next rank so all 6 names distinct); 2-pool QQQ+SPY, QQQ+XLK.
"""
import os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "v4_multipool_20261115"); os.makedirs(OUT, exist_ok=True)
src = open(os.path.join(ROOT, "v4_robust_upgrade_research.py")).read().split("# ---------------------------------------------------------------------------- 1. baselines")[0]
v = {"__file__": os.path.join(ROOT, "v4_robust_upgrade_research.py")}; exec(src, v)
MONTHS, P_SPX, SEP, YM, pick = v["MONTHS"], v["P_SPX"], v["SEP"], v["YM"], v["pick"]
RANK = {"QQQ": {t: v["RANK_Q"][("sharpe", t)] for t in MONTHS}, "SPY": {}, "XLK": {}}
for t, g in P_SPX[P_SPX.t.isin(MONTHS)].groupby("t"):
    g = g[g.sharpe.notna()].sort_values(["sharpe", "ticker"], ascending=[False, True])
    RANK["SPY"][t] = list(g.ticker)
    RANK["XLK"][t] = list(g[g.clean_sector == "Information Technology"].ticker)
RANK_B = {t: v["RANK_B"][("sharpe", t)] for t in MONTHS}

def targets(pools, dedup=False, n=2, k=5):
    held = {p: [] for p in pools}; hb = []; out = {}; overlap = []
    for t in MONTHS:
        taken = set()
        for p in pools:
            cands = [x for x in RANK[p][t] if not (dedup and x in taken)]
            held[p] = pick(cands, [x for x in held[p] if not (dedup and x in taken)], k, n)
            taken |= set(held[p])
        hb = pick(RANK_B[t], hb, k, n)
        if SEP[t]:
            w = {}
            for p in pools:
                for x in held[p]:
                    w[x] = w.get(x, 0) + 1 / (len(pools) * n)
            overlap.append(max(w.values()))
        else:
            w = {x: 0.5 / n for x in hb}; w["CASH"] = 0.5
        out[t] = w
    return out, overlap

rows, ledgers = [], {}
for name, pools, dd in [("V4 (QQQ only)", ["QQQ"], False), ("3-pool QQQ+XLK+SPY, overlap allowed", ["QQQ", "XLK", "SPY"], False),
                        ("3-pool, dedup (6 distinct)", ["QQQ", "XLK", "SPY"], True), ("2-pool QQQ+SPY, overlap", ["QQQ", "SPY"], False),
                        ("2-pool QQQ+XLK, overlap", ["QQQ", "XLK"], False), ("SPY pool only", ["SPY"], False), ("XLK pool only", ["XLK"], False)]:
    tg, ov = targets(pools, dd)
    L, miss = v["simulate"](tg)
    ym = [YM[t] for t in MONTHS]
    c, s, d, top10 = v["stats"](L.net, ym)
    sub = {lab: v["stats"](L.net, ym, a, b)[:2] for lab, a, b in (("09-14", "2009-01", "2014-12"), ("15-20", "2015-01", "2020-12"), ("21-26", "2021-01", "2026-10"))}
    on = [i for i, t in enumerate(MONTHS) if SEP[t]]
    rows.append({"variant": name, "CAGR": c, "Sharpe": s, "MonthlyMDD": d, "best10_share": top10,
                 "CAGR_09-14": sub["09-14"][0], "CAGR_15-20": sub["15-20"][0], "CAGR_21-26": sub["21-26"][0],
                 "Sharpe_09-14": sub["09-14"][1], "Sharpe_21-26": sub["21-26"][1],
                 "avg_names_ON": np.mean([L.n_names[i] for i in on]), "avg_max_weight_ON": np.mean(ov), "max_weight_ON": max(ov),
                 "months_with_overlap": int(sum(1 for x in ov if x > 1 / (len(pools) * 2) + 1e-9)), "missing": miss})
    ledgers[name] = L
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, "multipool_summary.csv"), index=False)
pd.set_option("display.width", 260)
print(R.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
# year-by-year main vs V4
y = pd.DataFrame({"ym": ledgers["V4 (QQQ only)"].ym, "V4": ledgers["V4 (QQQ only)"].net, "3pool": ledgers["3-pool QQQ+XLK+SPY, overlap allowed"].net})
yr = y.groupby(y.ym.str[:4])[["V4", "3pool"]].apply(lambda g: (1 + g).prod() - 1)
print("\nCalendar years:\n" + yr.to_string(float_format=lambda x: f"{x:+.1%}"))
