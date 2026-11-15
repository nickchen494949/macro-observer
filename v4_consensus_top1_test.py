#!/usr/bin/env python3
"""v4_consensus_top1_test.py — QQQ#1 + XLK#1, overlap uncapped (same stock -> 100%). Exploratory, same-data test (2026-11-15).
SEP=OFF leg unchanged (V4 BestSec top-2 + 50% SGOV). 10bp/side."""
import os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "v4_multipool_20261115")
src = open(os.path.join(ROOT, "v4_multipool_test.py")).read().split("rows, ledgers = [], {}")[0]
ns = {"__file__": os.path.join(ROOT, "v4_multipool_test.py")}; exec(src, ns)
v, MONTHS, SEP, YM, RANK, RANK_B, pick = ns["v"], ns["MONTHS"], ns["SEP"], ns["YM"], ns["RANK"], ns["RANK_B"], ns["pick"]
def tg(pools, n, k):
    held = {p: [] for p in pools}; hb = []; out = {}; mx = []
    for t in MONTHS:
        for p in pools:
            held[p] = pick(RANK[p][t], held[p], k, n)
        hb = pick(RANK_B[t], hb, 5, 2)
        if SEP[t]:
            w = {}
            for p in pools:
                for x in held[p]:
                    w[x] = w.get(x, 0) + 1 / (len(pools) * n)
            mx.append(max(w.values()))
        else:
            w = {x: 0.25 for x in hb}; w["CASH"] = 0.5
        out[t] = w
    return out, mx
rows = []
for name, pools, n, k in [("V4 (QQQ top-2, hold<=5)", ["QQQ"], 2, 5), ("QQQ top-1 only, hold<=5", ["QQQ"], 1, 5),
                          ("QQQ+XLK top-2 each (max 50%)", ["QQQ", "XLK"], 2, 5),
                          ("QQQ#1 + XLK#1, hold<=5 (max 100%)", ["QQQ", "XLK"], 1, 5), ("QQQ#1 + XLK#1, hold<=3 (max 100%)", ["QQQ", "XLK"], 1, 3),
                          ("QQQ#1 + XLK#1, hold<=1 (max 100%)", ["QQQ", "XLK"], 1, 1)]:
    t_, mx = tg(pools, n, k)
    L, _ = v["simulate"](t_)
    ym = [YM[t] for t in MONTHS]
    c, s, d, top10 = v["stats"](L.net, ym)
    on = [i for i, t in enumerate(MONTHS) if SEP[t]]
    rows.append({"variant": name, "CAGR": c, "Sharpe": s, "MonthlyMDD": d, "worst_month": L.net.min(), "best10_share": top10,
                 "CAGR_09-14": v["stats"](L.net, ym, "2009-01", "2014-12")[0], "CAGR_15-20": v["stats"](L.net, ym, "2015-01", "2020-12")[0],
                 "CAGR_21-26": v["stats"](L.net, ym, "2021-01", "2026-10")[0], "months_100pct_one_stock": int(sum(1 for x in mx if x > 0.999)),
                 "avg_max_weight_ON": np.mean(mx)})
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, "consensus_top1_summary.csv"), index=False)
pd.set_option("display.width", 250); print(R.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
