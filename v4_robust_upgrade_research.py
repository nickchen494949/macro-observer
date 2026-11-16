#!/usr/bin/env python3
"""
v4_robust_upgrade_research.py — Robustness upgrade research for V4 (2026-11-15)

PRE-REGISTERED PROTOCOL (written before any result in this file was computed)
-----------------------------------------------------------------------------
Goal: estimate what V4-style momentum could realistically deliver, and define a version whose
rules depend less on hindsight. Nothing here is tuned on its own output.

1. Candidate V4.1 (fixed before running):
   - Selection: equal-weight ensemble of 12 sleeves = 12-1 Sharpe ranking x top-n in {2,3} x hold<=k in {3,4,5,6,7,8}.
     Same two-pool structure as V4 (SEP=ON -> Nasdaq-100 pool, 100% stocks; SEP=OFF -> #1 non-IT sector by
     equal-weight 12-1 raw momentum, Sharpe ranking inside it, 50% stocks + 50% SGOV/BIL).
     Sleeve target weights are averaged into ONE portfolio, so turnover/costs are netted (10bp/side).
   - Regime: existing ALFRED SEP rule, unchanged (no re-tuning).
   - Election Reset: OFF.
2. Walk-forward estimate of real-time achievable return (removes parameter-selection bias):
   each December from 2011 onward, choose the config with the best trailing (expanding-window, from 2009-01)
   monthly Sharpe among 42 configs = metric {sharpe, raw} x n {1,2,3} x k {n..8}; hold it for the next 12 months.
   Out-of-sample window 2012-01..2026-10. Two variants: with SEP overlay and without.
3. Regime alternatives, reported regardless of result: none / SEP / QQQ below 10-month SMA (Faber 2007, untuned) /
   SEP OR trend. Purpose: show how much depends on the single-cycle SEP rule.
4. Report everything; no variant is dropped from the output.
"""
import json
import os
from itertools import product
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
INP = os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs")
ETF = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
OUT = os.path.join(ROOT, "outputs", "v4_robust_upgrade_20261115")
os.makedirs(OUT, exist_ok=True)
COST = 0.0010
LOG = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


P_SPX = pd.read_parquet(os.path.join(INP, "v3_spx_panel_214m.parquet"))
P_NDX = pd.read_parquet(os.path.join(INP, "v3_ndx_panel_214m.parquet"))
REG = pd.read_csv(os.path.join(INP, "v3_regime_and_cash_214m.csv"))
for p in (P_SPX, P_NDX):
    p["t"] = pd.to_datetime(p["t"])
REG["t"] = pd.to_datetime(REG["t"])
MONTHS = [t for t in sorted(P_SPX["t"].unique()) if pd.Timestamp("2008-12-31") <= t <= pd.Timestamp("2026-09-30")]
YM = {t: (t + pd.offsets.MonthBegin(1)).strftime("%Y-%m") for t in MONTHS}
SEP = dict(zip(REG["t"], REG["sep_on"].astype(bool)))
CASH = dict(zip(REG["t"], REG["ret_sgov_actual"].astype(float)))
RF = dict(zip(REG["t"], REG["rf_tbill"].astype(float)))
DEC_RESET = {t for t in MONTHS if YM[t] in ("2010-12", "2018-12", "2022-12")}
JAN_RESET = {t for t in MONTHS if YM[t] in ("2011-01", "2019-01", "2023-01")}

# return lookup (NDX first, then SPX)
RET = {}
for df in (P_SPX, P_NDX):
    for r in df[["t", "ticker", "hold_ret"]].itertuples(index=False):
        if pd.notna(r.hold_ret):
            RET[(r.t, r.ticker)] = float(r.hold_ret)

# pre-sorted candidate lists
RANK_Q, RANK_B, BSEC = {}, {}, {}
for metric in ("sharpe", "mom"):
    for t, g in P_NDX[P_NDX["t"].isin(MONTHS)].groupby("t"):
        g = g[g[metric].notna()].sort_values([metric, "ticker"], ascending=[False, True])
        RANK_Q[(metric, t)] = list(g["ticker"])
    for t, g in P_SPX[P_SPX["t"].isin(MONTHS)].groupby("t"):
        g = g[(g["clean_sector"] != "Information Technology") & g["mom"].notna() & g["sharpe"].notna()]
        sec = g.groupby("clean_sector")["mom"].mean().sort_index().idxmax()
        BSEC[t] = sec
        gs = g[g["clean_sector"] == sec].sort_values([metric, "ticker"], ascending=[False, True])
        RANK_B[(metric, t)] = list(gs["ticker"])

# regimes
q = pd.DataFrame(json.load(open(os.path.join(ETF, "QQQ.json"))))
q["date"] = pd.to_datetime(q["date"].str[:10])
qc = q.set_index("date")["adjClose"].astype(float).sort_index()
qm = qc.resample("ME").last()
sma10 = qm.rolling(10).mean()
TREND_ON = {t: bool(qm.loc[:t].iloc[-1] >= sma10.loc[:t].iloc[-1]) for t in MONTHS}
REGIMES = {
    "none": {t: True for t in MONTHS},
    "SEP": SEP,
    "trend10m": TREND_ON,
    "SEP_or_trend": {t: SEP[t] and TREND_ON[t] for t in MONTHS},
}


def pick(cands, held, k, n):
    rk = {tk: i + 1 for i, tk in enumerate(cands)}
    keep = [tk for tk in held if rk.get(tk, 10 ** 9) <= k]
    for tk in cands:
        if len(keep) >= n:
            break
        if tk not in keep:
            keep.append(tk)
    return keep[:n]


def sleeve_targets(metric, n, k, regime, election=False):
    hq, hb = [], []
    out = {}
    for t in MONTHS:
        if election and t in JAN_RESET:
            hq, hb = [], []
        hq = pick(RANK_Q[(metric, t)], hq, k, n)
        hb = pick(RANK_B[(metric, t)], hb, k, n)
        if election and t in DEC_RESET:
            w = {"CASH": 1.0}
        elif regime[t]:
            w = {tk: 1.0 / n for tk in hq}
        else:
            w = {tk: 0.5 / n for tk in hb}
            w["CASH"] = 0.5
        out[t] = w
    return out


def combine(list_of_targets):
    out = {}
    m = len(list_of_targets)
    for t in MONTHS:
        w = {}
        for tg in list_of_targets:
            for k_, v in tg[t].items():
                w[k_] = w.get(k_, 0.0) + v / m
        out[t] = w
    return out


def simulate(targets, cost=COST):
    prev = {}
    nets, names, tos = [], [], []
    missing = 0
    for t in MONTHS:
        w = targets[t]
        rl = {}
        for k_ in w:
            if k_ == "CASH":
                rl[k_] = CASH[t]
            else:
                if (t, k_) not in RET:
                    missing += 1
                    raise ValueError(f"Missing hold_ret for invested stock {k_} at {t}")
                rl[k_] = RET[(t, k_)]
        gross = sum(w[k_] * rl[k_] for k_ in w)
        keys = set(w) | set(prev)
        to = sum(abs(w.get(k_, 0) - prev.get(k_, 0)) for k_ in keys) if prev else sum(w.values())
        nets.append((1 + gross) * (1 - cost * to) - 1)
        tos.append(to)
        names.append(sum(1 for k_ in w if k_ != "CASH"))
        eq = 1 + gross
        prev = {k_: w[k_] * (1 + rl[k_]) / eq for k_ in w}
    return pd.DataFrame({"t": MONTHS, "ym": [YM[t] for t in MONTHS], "net": nets, "to": tos, "n_names": names}), missing


def stats(r, ym=None, start=None, end=None):
    df = pd.DataFrame({"r": np.asarray(r, float), "ym": ym, "rf": [RF[t] for t in MONTHS]})
    if start:
        df = df[df.ym >= start]
    if end:
        df = df[df.ym <= end]
    w = np.cumprod(1 + df.r.values)
    n = len(df)
    cagr = w[-1] ** (12 / n) - 1
    sh = (df.r - df.rf).mean() / df.r.std(ddof=1) * np.sqrt(12)
    ww = np.concatenate([[1], w])
    mdd = (ww / np.maximum.accumulate(ww) - 1).min()
    lw = np.log1p(df.r.values)
    top10 = np.sort(lw)[-10:].sum() / lw.sum()
    return cagr, sh, mdd, top10


YMS = [YM[t] for t in MONTHS]
rows = []


def report(label, targets, note=""):
    L, miss = simulate(targets)
    c, s, d, t10 = stats(L.net, YMS)
    c12, s12, d12, _ = stats(L.net, YMS, "2012-01")
    c09, s09, _, _ = stats(L.net, YMS, "2009-01", "2020-12")
    c21, s21, _, _ = stats(L.net, YMS, "2021-01")
    rows.append({"variant": label, "CAGR_214M": c, "Sharpe": s, "MonthlyMDD": d, "best10_share": t10,
                 "CAGR_2012+": c12, "Sharpe_2012+": s12, "CAGR_09_20": c09, "Sharpe_09_20": s09,
                 "CAGR_21_26": c21, "Sharpe_21_26": s21, "avg_names": L.n_names.mean(), "ann_turnover": L.to.mean() * 12,
                 "missing_ret": miss, "note": note})
    return L


# ---------------------------------------------------------------------------- 1. baselines + V4.1 candidate
say("=== 1. Baselines and pre-registered V4.1 candidate ===")
v4 = sleeve_targets("sharpe", 2, 5, SEP)
L_v4 = report("V4 (top2/hold5, SEP, no ER)", v4)
report("V4 + Election Reset", sleeve_targets("sharpe", 2, 5, SEP, election=True))
ENS = [(n, k) for n in (2, 3) for k in (3, 4, 5, 6, 7, 8)]
ens_targets = {name: combine([sleeve_targets("sharpe", n, k, reg) for n, k in ENS]) for name, reg in REGIMES.items()}
L_41 = report("V4.1 candidate: 12-sleeve Sharpe ensemble, SEP", ens_targets["SEP"], "pre-registered")
# sensitivity of ensemble composition
report("Ensemble incl. raw-momentum sleeves (24), SEP",
       combine([sleeve_targets(m, n, k, SEP) for m in ("sharpe", "mom") for n, k in ENS]), "sensitivity")
report("Ensemble top-n {2,3,4} x hold {n..8}, SEP",
       combine([sleeve_targets("sharpe", n, k, SEP) for n in (2, 3, 4) for k in range(n, 9)]), "sensitivity")

# ---------------------------------------------------------------------------- 3. regime alternatives
say("=== 3. Regime alternatives (V4 single config and V4.1 ensemble) ===")
for name, reg in REGIMES.items():
    if name != "SEP":
        report(f"V4 single config, regime={name}", sleeve_targets("sharpe", 2, 5, reg))
        report(f"V4.1 ensemble, regime={name}", ens_targets[name])
say("Months OFF by regime: " + ", ".join(f"{k}={sum(not v[t] for t in MONTHS)}" for k, v in REGIMES.items()))
say("trend10m OFF months by year: " + str(pd.Series([YM[t][:4] for t in MONTHS if not TREND_ON[t]]).value_counts().sort_index().to_dict()))

# ---------------------------------------------------------------------------- 2. walk-forward (stateful single-account + spliced comparison)
say("=== 2. Walk-forward parameter selection (expanding window, re-chosen each December) ===")
CANDS = [(m, n, k) for m in ("sharpe", "mom") for n in (1, 2, 3) for k in range(n, 9)]
say(f"candidate configs: {len(CANDS)}")


def simulate_stateful_wf(chosen_by_year, reg, init_mode="cold_cash_2012", carry_buffers=True):
    """
    True stateful single-account walk-forward simulation (2012-01..2026-10) with ZERO look-ahead in initialization:
    - init_mode="cold_cash_2012":
        Account starts from 100% Cash at 2012-01 open (`hq=[], hb=[], prev_w={}`), buys fresh Top-n picks under
        `chosen_by_year["2012"]` (selected at 2011-12-31), and pays the full 10bp initial entry cost (`to=1.0`).
    - init_mode="strict_pit_warmup":
        Account starts from 100% Cash at 2009-01 open with uninformative prior `("sharpe", 2, 5)`, then re-selects
        at 2009-12-31 (`chosen_by_year["2010"]`), 2010-12-31 (`chosen_by_year["2011"]`), and 2011-12-31 (`chosen_by_year["2012"]`)
        strictly using past returns available at each year-end.
    """
    hq, hb = [], []
    prev_w = {}
    pre_targets = {c: sleeve_targets(*c, reg) for c in set(chosen_by_year.values())}
    rows_wf = []
    for t in MONTHS:
        ym = YM[t]
        year = ym[:4]
        if ym < "2012-01":
            if init_mode == "cold_cash_2012":
                continue
            m, n, k = chosen_by_year.get(year, ("sharpe", 2, 5))
        else:
            m, n, k = chosen_by_year[year]
        hq = pick(RANK_Q[(m, t)], hq, k, n)
        hb = pick(RANK_B[(m, t)], hb, k, n)
        if carry_buffers or ym < "2012-01":
            if reg[t]:
                w = {tk: 1.0 / n for tk in hq}
            else:
                w = {tk: 0.5 / n for tk in hb}
                w["CASH"] = 0.5
        else:
            w = pre_targets[(m, n, k)][t]
        rl = {}
        for k_ in w:
            if k_ == "CASH":
                rl[k_] = CASH[t]
            else:
                if (t, k_) not in RET:
                    raise ValueError(f"Missing hold_ret for invested stock {k_} at {t}")
                rl[k_] = RET[(t, k_)]
        gross = sum(w[k_] * rl[k_] for k_ in w)
        keys = set(w) | set(prev_w)
        to = sum(abs(w.get(k_, 0) - prev_w.get(k_, 0)) for k_ in keys) if prev_w else sum(w.values())
        net = (1 + gross) * (1 - COST * to) - 1
        eq = 1 + gross
        prev_w = {k_: w[k_] * (1 + rl[k_]) / eq for k_ in w}
        if ym >= "2012-01":
            rows_wf.append({"t": t, "ym": ym, "year": year, "cfg": f"{m}_top{n}_hold{k}",
                            "gross": gross, "net": net, "to": to, "w": json.dumps(w)})
    return pd.DataFrame(rows_wf)


wf_rows = []
wf_ledgers = {}
for reg_name in ("SEP", "none"):
    reg = REGIMES[reg_name]
    sims = {c: simulate(sleeve_targets(*c, reg))[0].net.values for c in CANDS}
    rf = np.array([RF[t] for t in MONTHS])
    chosen = {"2009": ("sharpe", 2, 5)}
    for yr_w in ("2010", "2011"):
        past_w = [j for j, tt in enumerate(MONTHS) if YM[tt] < f"{yr_w}-01"]
        chosen[yr_w] = max(CANDS, key=lambda c: (sims[c][past_w] - rf[past_w]).mean() / sims[c][past_w].std(ddof=1))
    wf_ret_spliced = np.full(len(MONTHS), np.nan)
    for i, t in enumerate(MONTHS):
        ym = YM[t]
        if ym < "2012-01":
            continue
        year = ym[:4]
        if year not in chosen:
            past = [j for j, tt in enumerate(MONTHS) if YM[tt] < f"{year}-01"]
            best = max(CANDS, key=lambda c: (sims[c][past] - rf[past]).mean() / sims[c][past].std(ddof=1))
            chosen[year] = best
            wf_rows.append({"regime": reg_name, "year": year, "metric": best[0], "top_n": best[1], "hold_k": best[2]})
        wf_ret_spliced[i] = sims[chosen[year]][i]
    mask = ~np.isnan(wf_ret_spliced)
    rr = rf[mask]

    # 1. Cold-Start Cash at 2012-01 Open (hq=[], hb=[], prev_w={}, pays full 10bp initial entry cost, continuous buffers)
    df_wf_cold = simulate_stateful_wf(chosen, reg, init_mode="cold_cash_2012", carry_buffers=True)
    r_cold = df_wf_cold["net"].values
    w_cold = np.cumprod(1 + r_cold)
    c_cold = w_cold[-1] ** (12 / len(r_cold)) - 1
    s_cold = (r_cold - rr).mean() / r_cold.std(ddof=1) * np.sqrt(12)
    ww_cold = np.concatenate([[1], w_cold])
    d_cold = (ww_cold / np.maximum.accumulate(ww_cold) - 1).min()
    wf_ledgers[f"{reg_name}_cold_cash_2012"] = df_wf_cold

    # 2. Strict Point-in-Time Annual Warmup from 2009-01 (no look-ahead in 2009-2011 warmup, continuous buffers)
    df_wf_pit = simulate_stateful_wf(chosen, reg, init_mode="strict_pit_warmup", carry_buffers=True)
    r_pit = df_wf_pit["net"].values
    w_pit = np.cumprod(1 + r_pit)
    c_pit = w_pit[-1] ** (12 / len(r_pit)) - 1
    s_pit = (r_pit - rr).mean() / r_pit.std(ddof=1) * np.sqrt(12)
    ww_pit = np.concatenate([[1], w_pit])
    d_pit = (ww_pit / np.maximum.accumulate(ww_pit) - 1).min()
    wf_ledgers[f"{reg_name}_pit_warmup"] = df_wf_pit

    # 3. Cold-Start Cash at 2012-01 Open + Adopt Target Sleeve at Year-Start (pays full initial + switch turnover costs)
    df_wf_adopt = simulate_stateful_wf(chosen, reg, init_mode="cold_cash_2012", carry_buffers=False)
    r_adopt = df_wf_adopt["net"].values
    w_adopt = np.cumprod(1 + r_adopt)
    c_adopt = w_adopt[-1] ** (12 / len(r_adopt)) - 1
    s_adopt = (r_adopt - rr).mean() / r_adopt.std(ddof=1) * np.sqrt(12)
    ww_adopt = np.concatenate([[1], w_adopt])
    d_adopt = (ww_adopt / np.maximum.accumulate(ww_adopt) - 1).min()

    # 4. Spliced approximation (for reference)
    r_sp = wf_ret_spliced[mask]
    w_sp = np.cumprod(1 + r_sp)
    c_sp = w_sp[-1] ** (12 / len(r_sp)) - 1
    s_sp = (r_sp - rr).mean() / r_sp.std(ddof=1) * np.sqrt(12)
    ww_sp = np.concatenate([[1], w_sp])
    d_sp = (ww_sp / np.maximum.accumulate(ww_sp) - 1).min()

    fixed = sims[("sharpe", 2, 5)][mask]
    cf = np.prod(1 + fixed) ** (12 / len(fixed)) - 1
    ens = simulate(ens_targets[reg_name])[0].net.values[mask]
    ce = np.prod(1 + ens) ** (12 / len(ens)) - 1
    se = (ens - rr).mean() / ens.std(ddof=1) * np.sqrt(12)
    allc = sorted(np.prod(1 + sims[cc][mask]) ** (12 / mask.sum()) - 1 for cc in CANDS)
    say(f"[regime={reg_name}] 2012-01..2026-10 ({mask.sum()}m): "
        f"STATEFUL WF (2012 Cold-Cash Start, to[0]=1.0) CAGR={c_cold:.2%} Sharpe={s_cold:.3f} MDD={d_cold:.2%} | "
        f"STATEFUL WF (Strict PIT 2009-2011 Warmup) CAGR={c_pit:.2%} Sharpe={s_pit:.3f} MDD={d_pit:.2%} | "
        f"STATEFUL WF (Cold-Cash + Adopt Sleeve) CAGR={c_adopt:.2%} Sharpe={s_adopt:.3f} MDD={d_adopt:.2%} | "
        f"Spliced approx CAGR={c_sp:.2%} Sharpe={s_sp:.3f} MDD={d_sp:.2%} | "
        f"fixed V4 config (hindsight) CAGR={cf:.2%} | V4.1 ensemble CAGR={ce:.2%} Sharpe={se:.3f}")
WF = pd.DataFrame(wf_rows)
WF.to_csv(os.path.join(OUT, "walk_forward_choices.csv"), index=False)
wf_ledgers["SEP_cold_cash_2012"].to_csv(os.path.join(OUT, "walk_forward_stateful_sep_ledger.csv"), index=False)
wf_ledgers["SEP_pit_warmup"].to_csv(os.path.join(OUT, "walk_forward_stateful_sep_pit_warmup_ledger.csv"), index=False)
say("Walk-forward chosen configs:\n" + WF.to_string(index=False))

# ---------------------------------------------------------------------------- outputs
RES = pd.DataFrame(rows)
RES.to_csv(os.path.join(OUT, "variants_summary.csv"), index=False)
pd.set_option("display.width", 250)
say("\n" + RES.drop(columns=["note"]).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

# live holdings for 2026-11 under V4.1 (formation t = 2026-10-31 needs the extra panel month)
t_live = pd.Timestamp("2026-10-31")
live_parts = []
for n, k in ENS:
    hq, hb = [], []
    for t in MONTHS + [t_live]:
        rq = P_NDX[(P_NDX.t == t) & P_NDX.sharpe.notna()].sort_values(["sharpe", "ticker"], ascending=[False, True]).ticker.tolist()
        g = P_SPX[(P_SPX.t == t) & (P_SPX.clean_sector != "Information Technology") & P_SPX["mom"].notna() & P_SPX.sharpe.notna()]
        sec = g.groupby("clean_sector")["mom"].mean().sort_index().idxmax()
        rb = g[g.clean_sector == sec].sort_values(["sharpe", "ticker"], ascending=[False, True]).ticker.tolist()
        hq, hb = pick(rq, hq, k, n), pick(rb, hb, k, n)
    sep_live = bool(REG.loc[REG.t == t_live, "sep_on"].iloc[0])
    live_parts.append({tk: 1.0 / n for tk in hq} if sep_live else {**{tk: 0.5 / n for tk in hb}, "SGOV": 0.5})
live = {}
for w in live_parts:
    for k_, v in w.items():
        live[k_] = live.get(k_, 0) + v / len(live_parts)
say(f"\n2026-11 V4.1 holdings (SEP_on={sep_live}, BestSec={sec}): " + ", ".join(f"{k_} {v:.1%}" for k_, v in sorted(live.items(), key=lambda x: -x[1])))
L_41.to_csv(os.path.join(OUT, "v41_ensemble_ledger.csv"), index=False)
with open(os.path.join(OUT, "research_log.txt"), "w") as f:
    f.write("\n".join(LOG))

# ---------------------------------------------------------------------------- reproducibility assertions
_r = RES.set_index("variant")
assert abs(_r.loc["V4 (top2/hold5, SEP, no ER)", "CAGR_214M"] - 0.5965) < 1e-4
assert abs(_r.loc["V4 + Election Reset", "CAGR_214M"] - 0.6078) < 1e-4
assert abs(_r.loc["V4.1 candidate: 12-sleeve Sharpe ensemble, SEP", "CAGR_214M"] - 0.5410) < 5e-4
say("PASS: v4_robust_upgrade_research.py assertions (V4 59.65%, V4+ER 60.78%, V4.1 ~54.1%)")
