#!/usr/bin/env python3
"""
06 — FORMAL multiple-testing analysis of the overlay filters, on TWO engines.

FAMILY (explicit, 60 hypotheses; S&P 500, next-day open, drifted weights, 10bp/side):
  ranking horizon  : 12-1, 6-1, 3-1                                   (3)
  Top-K            : 1, 3                                             (2)
  filter           : RS_w > SPY_w for w in {12-1, 6-1, 3-1, 12-0, 6-0, 3-0}   (6)
                     SMA200 pass-down, SMA200 gate-to-cash,
                     SMA200 pass-down + RS(6-0), SMA200 gate + RS(6-0)        (4)
  H0_j : filter j does NOT raise mean monthly log return vs the unfiltered strategy with the same
         horizon and K.  d_jt = log(1+net_filter) - log(1+net_base).
  NOTE: the real search in this project was LARGER (tech universe, XLK / sector benchmarks,
        close-vs-open engines, two windows), so these family-wise p-values are OPTIMISTIC.

TESTS (stationary bootstrap, Politis-Romano, mean block 6 months, B=10,000, seed 20261102):
  per-hypothesis one-sided bootstrap p ; Bonferroni ; Holm step-down ;
  White (2000) Reality Check (max of sqrt(n)*mean) ; Hansen (2005) SPA_c (studentised, consistent).

ENGINES:
  "claude"  — independent engine (claude_engine.simulate on 01's panel; imports no Gemini code)
  "gemini"  — the audited engine (v2_07.simulate_mece_cell), already validated by 02/03/04.
Output: results/06_family_tests.csv, results/06_family_summary.csv, _work/06_series_*.pkl
"""
import os, sys, math
import numpy as np, pandas as pd
from _paths import REPO, GEMINI, WORK, RESULTS

B, L_BLOCK, SEED = 10_000, 6, 20261102
RANKS = [("12-1", "r121", "mom_12_1"), ("6-1", "r61", "mom_6_1"), ("3-1", "r31", "mom_3_1")]
KS = [1, 3]
RSW = ["121", "61", "31", "120", "60", "30"]
FILTERS = ([(f"RS{w}>SPY", None, f"r{w}", f"spy{w}") for w in RSW] +
           [("SMA200 pass", "pass", None, None), ("SMA200 gate", "gate", None, None),
            ("SMA200 pass+RS60", "pass", "r60", "spy60"), ("SMA200 gate+RS60", "gate", "r60", "spy60")])
WINDOWS = [("2010-01", "2026-09"), ("2015-01", "2026-09")]


# ---------------------------------------------------------------- engines
def run_claude():
    from claude_engine import simulate
    P = pd.read_parquet(f"{WORK}/claude_panel.parquet")
    S = {}
    for hl, rc, _ in RANKS:
        for k in KS:
            S[(hl, k, "base")] = simulate(P, k=k, rank=rc)["net"]
            for name, sma, rs, bench in FILTERS:
                S[(hl, k, name)] = simulate(P, k=k, rank=rc, sma=sma, rs=rs, bench=bench)["net"]
    return S


def run_gemini():
    sys.path.insert(0, GEMINI)
    import v2_07_mece_24_grid_cleanroom_auditor as G      # engine-dependent by design
    from v2_cleanroom_lib import CleanRoomEquityStore
    ssm = os.path.join(REPO, G.ORIG_SSM_REL); dd = os.path.join(ssm, "data")
    store = CleanRoomEquityStore(REPO, ssm_rel=G.ORIG_SSM_REL, include_ndx=False)
    cmap, aliases = G.cleanroom_reconstruct_cik_map_and_aliases(ssm, store)
    bad = G.cleanroom_untrusted_and_excluded_spells(dd, store)
    me = store.P.index
    mem = G.cleanroom_load_pit_membership(dd, me, bad)
    sec = G.cleanroom_build_pit_sector_panel(dd, store, aliases, cmap, me)
    fd = me[(me >= "2009-12-31") & (me <= "2026-08-31")]
    panel = G.build_mece_panel(store, mem, sec, fd)
    # add the extra RS windows with the SAME segment-continuity convention as the engine
    Pm, seg = store.P, store.seg_m
    def win(a, b):
        x = (Pm.shift(a) / Pm.shift(b) - 1.0)
        ok = seg == seg.shift(b)
        if a:
            ok &= seg == seg.shift(a)
        return x.where(ok)
    key = pd.MultiIndex.from_arrays([panel["t"], panel["ticker"]])
    for w, (a, b) in {"121": (1, 12), "61": (1, 6), "31": (1, 3), "120": (0, 12), "60": (0, 6), "30": (0, 3)}.items():
        X = win(a, b)
        st = X.stack()
        panel["r" + w] = st.reindex(key).values
        panel["spy" + w] = X["SPY"].reindex(panel["t"]).values
    S = {}
    for hl, _, gc in RANKS:
        for k in KS:
            base = G.simulate_mece_cell(panel, store, fd, rank_col=gc, k=k, exec_mode="open", weight_mode="drifted")
            S[(hl, k, "base")] = base["net"]
            for name, sma, rs, bench in FILTERS:
                mode = {"pass": "pass_down", "gate": "gate_cash", None: "none"}[sma]
                S[(hl, k, name)] = G.simulate_mece_cell(panel, store, fd, rank_col=gc, k=k, sma200_mode=mode,
                                                        rs_col=rs, bench_col=bench, exec_mode="open",
                                                        weight_mode="drifted")["net"]
    return S


# ---------------------------------------------------------------- statistics
def stationary_idx(rng, b, n, L):
    idx = np.empty((b, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, b)
    p = 1.0 / L
    for t in range(1, n):
        jump = rng.random(b) < p
        idx[:, t] = np.where(jump, rng.integers(0, n, b), (idx[:, t - 1] + 1) % n)
    return idx


def holm(p):
    p = np.asarray(p); m = len(p); o = np.argsort(p); adj = np.empty(m); run = 0.0
    for r, j in enumerate(o):
        run = max(run, min(1.0, (m - r) * p[j])); adj[j] = run
    return adj


def family_tests(S, start, end):
    names = [k for k in S if k[2] != "base"]
    D = np.column_stack([(np.log1p(S[k].loc[start:end]) - np.log1p(S[(k[0], k[1], "base")].loc[start:end])).values
                         for k in names])
    n, J = D.shape
    dbar = D.mean(0)
    rng = np.random.default_rng(SEED)
    means = np.empty((B, J))
    for c0 in range(0, B, 1000):
        idx = stationary_idx(rng, min(1000, B - c0), n, L_BLOCK)
        means[c0:c0 + len(idx)] = D[idx].mean(1)
    cen = means - dbar                                      # centred bootstrap
    p_ind = (cen >= dbar).mean(0)                           # one-sided H0: mean <= 0
    p_ind = np.where(np.abs(D).sum(0) < 1e-12, 1.0, p_ind)  # identical to base -> no evidence
    omega = np.sqrt(n) * means.std(0, ddof=1)
    # White Reality Check (non-studentised)
    V = np.sqrt(n) * dbar.max()
    Vs = (np.sqrt(n) * cen).max(1)
    p_rc = float((Vs >= V).mean())
    # Hansen SPA_c (studentised, consistent recentring)
    act = omega > 1e-12
    z = np.where(act, np.sqrt(n) * dbar / np.where(act, omega, 1), -np.inf)
    T = max(0.0, float(z.max()))
    thr = -np.sqrt(omega ** 2 / n * 2 * math.log(math.log(n)))
    g = np.where(dbar >= thr, dbar, 0.0)
    Zs = np.where(act, np.sqrt(n) * (means - g) / np.where(act, omega, 1), -np.inf)
    Ts = np.maximum(0.0, Zs.max(1))
    p_spa = float((Ts >= T).mean())
    rows = []
    for j, k in enumerate(names):
        d = D[:, j]; srt = np.sort(d)[::-1]
        rows.append(dict(rank=k[0], K=k[1], filter=k[2], months=n,
                         ann_gain_pct=round((math.exp(d.sum() * 12 / n) - 1) * 100, 2),
                         ann_gain_ex_best2_pct=round((math.exp((d.sum() - srt[:2].sum()) * 12 / n) - 1) * 100, 2),
                         months_differ=int((np.abs(d) > 1e-12).sum()),
                         t_iid=round(float(d.mean() / (d.std(ddof=1) / np.sqrt(n))) if d.std() > 0 else 0.0, 2),
                         p_boot=round(float(p_ind[j]), 4)))
    R = pd.DataFrame(rows)
    R["p_bonferroni"] = np.minimum(1.0, R["p_boot"] * J).round(4)
    R["p_holm"] = holm(R["p_boot"].values).round(4)
    return R, dict(hypotheses=J, months=n, p_reality_check=round(p_rc, 4), p_spa_c=round(p_spa, 4),
                   best=" / ".join(map(str, names[int(np.argmax(z))])), best_t_studentised=round(T, 2),
                   min_p_boot=float(R["p_boot"].min()), min_p_holm=float(R["p_holm"].min()))


def main():
    allR, allS = [], []
    for eng, fn in [("claude", run_claude), ("gemini", run_gemini)]:
        print(f"[06] simulating 66 strategies on {eng} engine ...", flush=True)
        S = fn()
        pd.to_pickle(S, f"{WORK}/06_series_{eng}.pkl")
        for a, b in WINDOWS:
            R, s = family_tests(S, a, b)
            R.insert(0, "window", f"{a[:4]}-{b[:4]}"); R.insert(0, "engine", eng)
            allR.append(R)
            s.update(engine=eng, window=f"{a[:4]}-{b[:4]}"); allS.append(s)
            print(f"[06] {eng} {a[:4]}-{b[:4]}: J={s['hypotheses']} | min raw p={s['min_p_boot']:.3f} | "
                  f"min Holm p={s['min_p_holm']:.3f} | Reality Check p={s['p_reality_check']:.3f} | "
                  f"SPA_c p={s['p_spa_c']:.3f} | best={s['best']}", flush=True)
    pd.concat(allR).to_csv(f"{RESULTS}/06_family_tests.csv", index=False)
    pd.DataFrame(allS).to_csv(f"{RESULTS}/06_family_summary.csv", index=False)


if __name__ == "__main__":
    main()
