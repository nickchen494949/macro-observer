#!/usr/bin/env python3
"""
07 — Does 12-1 momentum beat SPY, and how much of it is the 2023-2026 boom?  (both engines)
Benchmark: SPY adj_open first session of month m -> first session of m+1 (same execution clock as
the strategies), from raw_open/SPY.json. Excess = log(1+net) - log(1+spy).
Uses the series saved by 06 (_work/06_series_{claude,gemini}.pkl).
Output: results/07_spy_excess_regime.csv
"""
import json, math
import numpy as np, pandas as pd
from _paths import DATA, WORK, RESULTS

j = json.load(open(f"{DATA}/raw_open/SPY.json"))
o = pd.Series(j["adj_open"], index=pd.to_datetime(j["dates"])).dropna()
first = o.groupby(o.index.to_period("M")).head(1)
first.index = first.index.to_period("M").to_timestamp("M")
SPY = first.shift(-1) / first - 1           # holding month m

rng = np.random.default_rng(20261102)
def p_boot(x, B=10000, L=6):
    n = len(x); m = x.mean(); hits = 0
    for c in range(0, B, 1000):
        b = min(1000, B - c)
        idx = np.empty((b, n), dtype=np.int64); idx[:, 0] = rng.integers(0, n, b)
        for t in range(1, n):
            jmp = rng.random(b) < 1 / L
            idx[:, t] = np.where(jmp, rng.integers(0, n, b), (idx[:, t - 1] + 1) % n)
        hits += ((x[idx].mean(1) - m) >= m).sum()
    return hits / B

c = lambda r: ((1 + r).prod() ** (12 / len(r)) - 1) * 100
CASES = [("12-1", 3, "base"), ("12-1", 3, "RS60>SPY"), ("12-1", 1, "base"), ("12-1", 1, "SMA200 pass"), ("12-1", 1, "RS60>SPY")]
rows = []
for eng in ["claude", "gemini"]:
    S = pd.read_pickle(f"{WORK}/06_series_{eng}.pkl")
    for key in CASES:
        r_all = S[key]
        for a, b in [("2010-01", "2026-09"), ("2015-01", "2026-09")]:
            r = r_all.loc[a:b]; s = SPY.reindex(r.index)
            ex = (np.log1p(r) - np.log1p(s)).values; n = len(ex); srt = np.sort(ex)[::-1]
            ann = lambda x: (math.exp(x.sum() * 12 / n) - 1) * 100
            rows.append(dict(engine=eng, strategy=f"{key[0]} Top-{key[1]} {key[2]}", window=f"{a[:4]}-{b[:4]}",
                             cagr=round(c(r), 2), spy_cagr=round(c(s), 2), excess_ann=round(ann(ex), 2),
                             t_iid=round(ex.mean() / (ex.std(ddof=1) / math.sqrt(n)), 2),
                             p_boot_excess_le_0=round(p_boot(ex), 4),
                             excess_ex_best5=round(ann(srt[5:]), 2), excess_ex_best10=round(ann(srt[10:]), 2),
                             cagr_2010_2022=round(c(r_all.loc["2010":"2022"]), 2),
                             spy_2010_2022=round(c(SPY.reindex(r_all.loc["2010":"2022"].index)), 2),
                             cagr_2023_2026=round(c(r_all.loc["2023":"2026-09"]), 2),
                             spy_2023_2026=round(c(SPY.reindex(r_all.loc["2023":"2026-09"].index)), 2)))
R = pd.DataFrame(rows)
R.to_csv(f"{RESULTS}/07_spy_excess_regime.csv", index=False)
print(R[["engine", "strategy", "window", "cagr", "spy_cagr", "excess_ann", "t_iid", "p_boot_excess_le_0",
         "excess_ex_best10", "cagr_2010_2022", "spy_2010_2022", "cagr_2023_2026"]].to_string(index=False))
