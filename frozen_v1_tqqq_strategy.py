#!/usr/bin/env python3
"""
frozen_v1_tqqq_strategy.py — Standalone Reproducible Engine & Audit for:
Frozen V1 TQQQ Strategy (2026-11-15)

Core Architecture (QQQ & TQQQ Only + Cash SGOV):
1. Macro Gate (FOMC SEP):
   - March & June (month < 9): compare current-year (YYYY) median Core PCE & Fed Funds Rate projections vs previous SEP.
   - September & December (month >= 9): compare next-year (YYYY+1) median projections vs previous SEP.
   - EXIT (SEP = OFF): (c_rate > p_rate) and (c_pce > p_pce) and (c_pce > 2.0%) -> 100% Pure Cash (SGOV), unconditionally overriding NSL.
   - ENTER (SEP = ON): (c_rate <= p_rate).
2. Volatility Scaling Layer (When SEP = ON -> switches ONLY between 3x TQQQ and 1x QQQ + NSL [Never Sell in Loss]):
   - V1-Monthly (Monthly Ratio Rebalance):
     At each month-end t, compute on QQQ daily returns:
       std_252(t) = 252-day rolling daily return std of QQQ
       std_21(t)  = 21-day rolling daily return std of QQQ
       w_target(t) = min(1.0, (k * std_252(t) / std_21(t)) ** 2)   [default k = 1.0; plateau sweet spot k = 1.1]
     Allocate w_target(t) to 3x TQQQ and (1 - w_target(t)) to 1x QQQ.
     NSL Rule: When w_target(t) < current TQQQ weight, only trim TQQQ to QQQ if the current TQQQ position is in profit
     (tqqq_bucket >= tqqq_cost_basis). If underwater, hold existing TQQQ and QQQ buckets without selling TQQQ at a loss.
   - V1-Daily (Daily 1-Year Vol_Z + NSL):
     Compute 20-day annualized volatility rvol_20 of QQQ, and its 252-day rolling mean and std:
       Vol_Z(d) = (rvol_20(d) - mean_252(d)) / std_252(d)
     When Vol_Z > Trig (default 1.5; plateau 1.2) AND in profit (equity >= entry_equity [NSL]): switch 3x TQQQ -> 1x QQQ.
     When Vol_Z < Rec  (default 0.5; plateau 0.3): switch 1x QQQ -> 3x TQQQ.
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "outputs", "v1_tqqq_strategy_20261115")
os.makedirs(OUT_DIR, exist_ok=True)
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")

# 1. Load data
bsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bsrc, bs)
fred, yahoo, sig, T = bs["fred"], bs["yahoo"], bs["sig"], bs["T"]

REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

def load_etf_close(sym):
    d = json.load(open(os.path.join(ETF_DIR, f"{sym}.json")))
    s = pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]

ixic = yahoo("_IXIC")
qqq_p = load_etf_close("QQQ")
tqqq_p = load_etf_close("TQQQ")
rf_d = (fred("DGS3MO") / 100.0).reindex(ixic.index).ffill().bfill() / 252.0

r_ixic = ixic.pct_change().dropna()
r_qqq = r_ixic.copy()
qqq_ret = qqq_p.pct_change().dropna()
c_q = r_qqq.index.intersection(qqq_ret.index)
r_qqq.loc[c_q] = qqq_ret.loc[c_q]

r_tqqq = (3.0 * r_qqq - 2.0 * (rf_d.reindex(r_qqq.index) + 0.005 / 252.0) - 0.0095 / 252.0).clip(lower=-0.99)
tqqq_ret = tqqq_p.pct_change().dropna()
c_t = r_tqqq.index.intersection(tqqq_ret.index)
r_tqqq.loc[c_t] = tqqq_ret.loc[c_t]

# Monthly schedule
T_all = [t for t in T if t >= pd.Timestamp("1989-12-31")]
d_ret_dict = {}
for i in range(len(T_all) - 1):
    t, t1 = T_all[i], T_all[i + 1]
    days = r_qqq.loc[(r_qqq.index > t) & (r_qqq.index <= t1)].index
    d_ret_dict[t] = (r_tqqq.loc[days], r_qqq.loc[days], rf_d.loc[days])

# Volatility indicators on QQQ
std_21 = r_qqq.rolling(21).std(ddof=1)
std_252 = r_qqq.rolling(252).std(ddof=1)
rvol_20 = r_qqq.rolling(20).std(ddof=1) * np.sqrt(252) * 100.0
vol_mean_252 = rvol_20.rolling(252).mean()
vol_std_252 = rvol_20.rolling(252).std(ddof=1)
vol_z = (rvol_20 - vol_mean_252) / vol_std_252

# Daily SEP map (strictly lagged from month-end t)
m_sep = sig["SEP_PROXY"].copy()
for dt, val in real_sep.items():
    if dt in m_sep.index and dt >= pd.Timestamp("2015-11-30"):
        m_sep.loc[dt] = val
m_sep_shifted = m_sep.shift(1)
m_map = {dt.to_period("M"): bool(v) for dt, v in m_sep_shifted.dropna().items()}
sep_daily = pd.Series([m_map.get(dt.to_period("M"), True) for dt in r_qqq.index], index=r_qqq.index)

def run_v1_monthly(start_t, end_t, k=1.0, power=2.0, use_sep=True, use_nsl=True, pure_sep=False):
    months = [t for t in T_all[:-1] if start_t <= t <= end_t]
    eq = 1.0
    tb = 1.0
    qb = 0.0
    tc = 1.0
    deq = []
    ledger = []
    for t in months:
        sep_on = bool(real_sep[t]) if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t])
        if not use_sep:
            sep_on = True
        s21 = float(std_21.loc[:t].iloc[-1])
        s252 = float(std_252.loc[:t].iloc[-1])
        wt = 1.0 if pure_sep else min(1.0, ((k * s252) / s21) ** power)
        d3, d1, d0 = d_ret_dict[t]
        eq_start = eq
        if not sep_on:
            eff_w = 0.0
            action = "SEP_OFF_CASH"
            for r0 in d0:
                eq *= (1.0 + r0)
                deq.append(eq)
            tb = 0.0; qb = 0.0; tc = 0.0
        else:
            if not use_nsl or pure_sep:
                eff_w = wt
                action = "REBAL"
                for r3, r1 in zip(d3, d1):
                    eq *= (1.0 + wt * r3 + (1.0 - wt) * r1)
                    deq.append(eq)
            else:
                tot = tb + qb if (tb + qb) > 0 else eq
                if tb == 0 and qb == 0:
                    tb = eq * wt
                    qb = eq * (1.0 - wt)
                    tc = tb
                    eff_w = wt
                    action = "ENTER_FROM_CASH"
                else:
                    cw = tb / tot
                    if wt > cw:
                        add = tot * wt - tb
                        tb += add
                        qb -= add
                        tc += add
                        eff_w = wt
                        action = "ADD_TQQQ"
                    elif wt < cw:
                        if tb >= tc:
                            nt = tot * wt
                            tc = tc * (nt / tb) if tb > 0 else 0.0
                            qb += (tb - nt)
                            tb = nt
                            eff_w = wt
                            action = "TRIM_PROFIT_TO_QQQ"
                        else:
                            eff_w = cw
                            action = "NSL_HOLD_UNDERWATER"
                    else:
                        eff_w = cw
                        action = "HOLD"
                for r3, r1 in zip(d3, d1):
                    tb *= (1.0 + r3)
                    qb *= (1.0 + r1)
                    eq = tb + qb
                    deq.append(eq)
        ledger.append({
            "month_end_signal": t.strftime("%Y-%m-%d"),
            "sep_on": sep_on,
            "std_252_pct": round(s252 * 100, 3),
            "std_21_pct": round(s21 * 100, 3),
            "w_target_tqqq": round(wt, 4),
            "w_effective_tqqq": round(eff_w, 4),
            "action": action,
            "month_return_pct": round((eq / eq_start - 1.0) * 100, 2),
            "equity_multiple": round(eq, 2),
        })
    s_eq = pd.Series(deq)
    mdd = float((s_eq / s_eq.cummax() - 1.0).min()) * 100.0
    yrs = len(months) / 12.0
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    rets = s_eq.pct_change().dropna()
    sh = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    return cagr, mdd, sh, eq, pd.DataFrame(ledger)

def run_v1_daily(start_dt, end_dt, trig=1.5, rec=0.5, use_sep=True, use_nsl=True):
    idx = r_qqq.loc[start_dt:end_dt].index
    eq = 1.0; peak = 1.0; max_dd = 0.0; in_3x = True; entry_eq = 1.0; prev_pos = "3x"
    eq_series = []
    for dt in idx:
        loc = r_qqq.index.get_loc(dt)
        sig_loc = loc - 1
        vz = vol_z.iloc[sig_loc]
        s_on = sep_daily.iloc[sig_loc] if use_sep else True
        if not s_on:
            pos = "0x"; in_3x = False
        else:
            if prev_pos == "0x":
                if np.isnan(vz) or vz <= trig:
                    in_3x = True; entry_eq = eq
            elif not np.isnan(vz):
                if in_3x:
                    if vz > trig and ((not use_nsl) or eq >= entry_eq):
                        in_3x = False
                else:
                    if vz < rec:
                        in_3x = True; entry_eq = eq
            pos = "3x" if in_3x else "1x"
        prev_pos = pos
        ret = r_tqqq.iloc[loc] if pos == "3x" else (r_qqq.iloc[loc] if pos == "1x" else rf_d.iloc[loc])
        eq *= (1.0 + ret)
        if eq > peak: peak = eq
        dd = eq / peak - 1.0
        if dd < max_dd: max_dd = dd
        eq_series.append(eq)
    yrs = (idx[-1] - idx[0]).days / 365.25
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    rets = pd.Series(eq_series, index=idx).pct_change().dropna()
    sh = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    return cagr, max_dd * 100.0, sh, eq

if __name__ == "__main__":
    rows = []
    # 2009-2026 & 2010-2026 evaluations
    c09_pure, m09_pure, s09_pure, eq09_pure, _ = run_v1_monthly(pd.Timestamp("2008-12-31"), pd.Timestamp("2026-09-30"), pure_sep=True)
    c10_pure, m10_pure, s10_pure, eq10_pure, _ = run_v1_monthly(pd.Timestamp("2009-12-31"), pd.Timestamp("2026-09-30"), pure_sep=True)
    rows.append(("0. Pure SEP Baseline (SEP=ON 100% TQQQ, SEP=OFF Cash)", c09_pure, m09_pure, s09_pure, eq09_pure, c10_pure, m10_pure, s10_pure, eq10_pure))

    c09_m1, m09_m1, s09_m1, eq09_m1, df_ledger = run_v1_monthly(pd.Timestamp("2008-12-31"), pd.Timestamp("2026-09-30"), k=1.0, power=2.0, use_sep=True, use_nsl=True)
    c10_m1, m10_m1, s10_m1, eq10_m1, _ = run_v1_monthly(pd.Timestamp("2009-12-31"), pd.Timestamp("2026-09-30"), k=1.0, power=2.0, use_sep=True, use_nsl=True)
    rows.append(("1. V1-Monthly Standard: SEP + (std_252/std_21)^2 + NSL", c09_m1, m09_m1, s09_m1, eq09_m1, c10_m1, m10_m1, s10_m1, eq10_m1))

    c09_m2, m09_m2, s09_m2, eq09_m2, _ = run_v1_monthly(pd.Timestamp("2008-12-31"), pd.Timestamp("2026-09-30"), k=1.1, power=2.0, use_sep=True, use_nsl=True)
    c10_m2, m10_m2, s10_m2, eq10_m2, _ = run_v1_monthly(pd.Timestamp("2009-12-31"), pd.Timestamp("2026-09-30"), k=1.1, power=2.0, use_sep=True, use_nsl=True)
    rows.append(("2. V1-Monthly Sweet-Spot: SEP + (1.1*std_252/std_21)^2 + NSL", c09_m2, m09_m2, s09_m2, eq09_m2, c10_m2, m10_m2, s10_m2, eq10_m2))

    c09_d1, m09_d1, s09_d1, eq09_d1 = run_v1_daily("2009-01-02", "2026-11-13", trig=1.5, rec=0.5, use_sep=True, use_nsl=True)
    c10_d1, m10_d1, s10_d1, eq10_d1 = run_v1_daily("2010-01-04", "2026-11-13", trig=1.5, rec=0.5, use_sep=True, use_nsl=True)
    rows.append(("3. V1-Daily Standard: SEP + 1Y Vol_Z (1.5/0.5) + NSL", c09_d1, m09_d1, s09_d1, eq09_d1, c10_d1, m10_d1, s10_d1, eq10_d1))

    c09_d2, m09_d2, s09_d2, eq09_d2 = run_v1_daily("2009-01-02", "2026-11-13", trig=1.2, rec=0.3, use_sep=True, use_nsl=True)
    c10_d2, m10_d2, s10_d2, eq10_d2 = run_v1_daily("2010-01-04", "2026-11-13", trig=1.2, rec=0.3, use_sep=True, use_nsl=True)
    rows.append(("4. V1-Daily Sweet-Spot: SEP + 1Y Vol_Z (1.2/0.3) + NSL", c09_d2, m09_d2, s09_d2, eq09_d2, c10_d2, m10_d2, s10_d2, eq10_d2))

    df_summary = pd.DataFrame(rows, columns=[
        "Strategy", "2009_2026_CAGR", "2009_2026_MaxDD", "2009_2026_Sharpe", "2009_2026_Mult",
        "2010_2026_CAGR", "2010_2026_MaxDD", "2010_2026_Sharpe", "2010_2026_Mult"
    ])
    df_summary.to_csv(os.path.join(OUT_DIR, "v1_tqqq_summary.csv"), index=False)
    df_ledger.to_csv(os.path.join(OUT_DIR, "v1_tqqq_monthly_ledger_2009_2026.csv"), index=False)

    print("=========================================================================================================")
    print("FROZEN V1 TQQQ STRATEGY SUMMARY (2009-2026 & 2010-2026)")
    print("=========================================================================================================")
    for _, r_row in df_summary.iterrows():
        print(f"{r_row['Strategy']:<60} | 09-26: {r_row['2009_2026_CAGR']:5.1f}% (MDD {r_row['2009_2026_MaxDD']:5.1f}%, Sh {r_row['2009_2026_Sharpe']:4.2f}, {r_row['2009_2026_Mult']:7.1f}x) | 10-26: {r_row['2010_2026_CAGR']:5.1f}% (MDD {r_row['2010_2026_MaxDD']:5.1f}%, Sh {r_row['2010_2026_Sharpe']:4.2f}, {r_row['2010_2026_Mult']:7.1f}x)")

    # Latest live readout
    latest_dt = r_qqq.index[-1]
    s21_now = float(std_21.iloc[-1])
    s252_now = float(std_252.iloc[-1])
    w_now = min(1.0, (s252_now / s21_now) ** 2)
    vz_now = float(vol_z.iloc[-1])
    print("\n--- LATEST LIVE READOUT ---")
    print(f"Date: {latest_dt.strftime('%Y-%m-%d')} | SEP = OFF (100% SGOV Cash)")
    print(f"QQQ 252d Daily Std: {s252_now*100:.2f}% ({s252_now*np.sqrt(252)*100:.1f}% ann) | 21d Daily Std: {s21_now*100:.2f}% ({s21_now*np.sqrt(252)*100:.1f}% ann)")
    print(f"V1-Monthly Target TQQQ Ratio (if SEP were ON): {w_now*100:.1f}% TQQQ / {(1-w_now)*100:.1f}% QQQ | Actual Position (SEP=OFF): 100% SGOV Cash")
    print(f"V1-Daily Vol_Z: {vz_now:+.2f} (> 1.5 -> VOL DANGER)")
