#!/usr/bin/env python3
"""
frozen_v1_tqqq_strategy.py — Official Standalone Reproducible Engine & Audit for:
Frozen V1 TQQQ Strategy (V1-Daily: SEP + Daily 1-Year Vol_Z + NSL, 2026-11-16)

Official Frozen Rules (V1-Daily):
1. Macro Gate (FOMC SEP -> Pure Cash 0x):
   - March & June (month < 9): compare current-year (YYYY) median Core PCE & Fed Funds Rate projections vs previous SEP.
   - September & December (month >= 9): compare next-year (YYYY+1) median projections vs previous SEP.
   - EXIT (SEP = OFF): (c_rate > p_rate) and (c_pce > p_pce) and (c_pce > 2.0%)
     -> Switch 100% to Pure Cash (SGOV / DGS3MO), unconditionally overriding NSL.
   - ENTER (SEP = ON): (c_rate <= p_rate).
2. Daily Volatility Switch (When SEP = ON -> 3x TQQQ vs 1x QQQ with NSL [Never Sell in Loss]):
   - On QQQ daily returns r_qqq, compute:
       rvol_20(d)   = 20-day rolling std(r_qqq) * sqrt(252) * 100
       mean_252(d)  = 252-day rolling mean(rvol_20)
       std_252(d)   = 252-day rolling std(rvol_20)
       Vol_Z(d)     = (rvol_20(d) - mean_252(d)) / std_252(d)
   - Strictly lagged 1 trading day (signal at day d-1 close executes on day d):
     * TRIM TO 1x QQQ: When holding 3x TQQQ, if Vol_Z(d-1) > Trig AND eq(d-1) >= entry_eq (NSL: in profit),
       switch 100% from 3x TQQQ to 1x QQQ.
     * RE-ENTER 3x TQQQ: When holding 1x QQQ, if Vol_Z(d-1) < Rec, switch 100% from 1x QQQ to 3x TQQQ
       and record new entry_eq = eq(d-1).
     * Standard Parameters: Window = 252d, Trig = 1.5, Rec = 0.5
     * Plateau Sweet-Spot : Window = 252d, Trig = 1.2, Rec = 0.3
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

# Monthly schedule (for V1-Monthly comparison)
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
    if dt >= pd.Timestamp("2015-11-30"):
        m_sep.loc[dt] = val
m_sep = m_sep.sort_index()
m_map = {(dt + pd.offsets.MonthEnd(1)).to_period("M"): bool(v) for dt, v in m_sep.dropna().items()}
sep_daily = pd.Series([m_map.get(dt.to_period("M"), True) for dt in r_qqq.index], index=r_qqq.index)

def run_v1_daily(start_dt, end_dt, trig=1.5, rec=0.5, use_sep=True, use_nsl=True, pure_sep=False):
    idx = r_qqq.loc[start_dt:end_dt].index
    eq = 1.0; peak = 1.0; max_dd = 0.0; in_3x = True; entry_eq = 1.0; prev_pos = "3x"
    entry_dt = idx[0]
    eq_series = []
    trades = []
    for dt in idx:
        loc = r_qqq.index.get_loc(dt)
        sig_loc = loc - 1
        vz = float(vol_z.iloc[sig_loc]) if not np.isnan(vol_z.iloc[sig_loc]) else 0.0
        rv = float(rvol_20.iloc[sig_loc]) if not np.isnan(rvol_20.iloc[sig_loc]) else 0.0
        vm = float(vol_mean_252.iloc[sig_loc]) if not np.isnan(vol_mean_252.iloc[sig_loc]) else 0.0
        s_on = bool(sep_daily.iloc[sig_loc]) if use_sep else True
        reason = ""
        if not s_on:
            pos = "0x"
            in_3x = False
            if prev_pos != "0x":
                reason = "SEP_OFF_TO_CASH"
        elif pure_sep:
            pos = "3x"
            in_3x = True
            if prev_pos != "3x":
                reason = "SEP_ON_TO_3X"
        else:
            if prev_pos == "0x":
                if vz <= trig:
                    in_3x = True
                    entry_eq = eq
                    reason = "SEP_ON_TO_3X"
                else:
                    in_3x = False
                    reason = "SEP_ON_HIGH_VOL_TO_1X"
            else:
                if in_3x:
                    if vz > trig and ((not use_nsl) or eq >= entry_eq):
                        in_3x = False
                        reason = "VOL_Z_PROFIT_TRIM_TO_1X"
                else:
                    if vz < rec:
                        in_3x = True
                        entry_eq = eq
                        reason = "VOL_Z_CALM_REENTER_3X"
            pos = "3x" if in_3x else "1x"

        if pos != prev_pos:
            trades.append({
                "date": dt.strftime("%Y-%m-%d"),
                "from_pos": prev_pos,
                "to_pos": pos,
                "reason": reason,
                "vol_z": round(vz, 2),
                "rvol_20_pct": round(rv, 2),
                "mean_252_pct": round(vm, 2),
                "equity_multiple": round(eq, 2),
                "leg_return_pct": round((eq / entry_eq - 1.0) * 100.0, 2) if prev_pos == "3x" else None,
            })
            entry_dt = dt
        prev_pos = pos
        ret = r_tqqq.iloc[loc] if pos == "3x" else (r_qqq.iloc[loc] if pos == "1x" else rf_d.iloc[loc])
        eq *= (1.0 + ret)
        if eq > peak:
            peak = eq
        dd = eq / peak - 1.0
        if dd < max_dd:
            max_dd = dd
        eq_series.append(eq)

    s_eq = pd.Series(eq_series, index=idx)
    yrs = (idx[-1] - idx[0]).days / 365.25
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    rets = s_eq.pct_change().dropna()
    sh = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    return cagr, max_dd * 100.0, sh, eq, s_eq, pd.DataFrame(trades)

def run_v1_monthly(start_t, end_t, k=1.0, power=2.0, use_sep=True, use_nsl=True, pure_sep=False):
    months = [t for t in T_all[:-1] if start_t <= t <= end_t]
    eq = 1.0; tb = 1.0; qb = 0.0; tc = 1.0; deq = []
    for t in months:
        sep_on = bool(real_sep[t]) if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t])
        if not use_sep:
            sep_on = True
        s21 = float(std_21.loc[:t].iloc[-1])
        s252 = float(std_252.loc[:t].iloc[-1])
        wt = 1.0 if pure_sep else min(1.0, ((k * s252) / s21) ** power)
        d3, d1, d0 = d_ret_dict[t]
        if not sep_on:
            for r0 in d0:
                eq *= (1.0 + r0); deq.append(eq)
            tb = 0.0; qb = 0.0; tc = 0.0
        else:
            if not use_nsl or pure_sep:
                for r3, r1 in zip(d3, d1):
                    eq *= (1.0 + wt * r3 + (1.0 - wt) * r1); deq.append(eq)
            else:
                tot = tb + qb if (tb + qb) > 0 else eq
                if tb == 0 and qb == 0:
                    tb = eq * wt; qb = eq * (1.0 - wt); tc = tb
                else:
                    cw = tb / tot
                    if wt > cw:
                        add = tot * wt - tb; tb += add; qb -= add; tc += add
                    elif wt < cw and tb >= tc:
                        nt = tot * wt; tc = tc * (nt / tb) if tb > 0 else 0.0; qb += (tb - nt); tb = nt
                for r3, r1 in zip(d3, d1):
                    tb *= (1.0 + r3); qb *= (1.0 + r1); eq = tb + qb; deq.append(eq)
    s_eq = pd.Series(deq)
    mdd = float((s_eq / s_eq.cummax() - 1.0).min()) * 100.0
    yrs = len(months) / 12.0
    cagr = (eq ** (1.0 / yrs) - 1.0) * 100.0
    rets = s_eq.pct_change().dropna()
    sh = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    return cagr, mdd, sh, eq

if __name__ == "__main__":
    # 1. Summary Table
    c09_pure, m09_pure, s09_pure, eq09_pure, s_eq_pure, _ = run_v1_daily("2009-01-02", "2026-11-13", pure_sep=True)
    c10_pure, m10_pure, s10_pure, eq10_pure, _, _ = run_v1_daily("2010-01-04", "2026-11-13", pure_sep=True)

    c09_d1, m09_d1, s09_d1, eq09_d1, s_eq_d1, trades_d1 = run_v1_daily("2009-01-02", "2026-11-13", trig=1.5, rec=0.5, use_sep=True, use_nsl=True)
    c10_d1, m10_d1, s10_d1, eq10_d1, _, _ = run_v1_daily("2010-01-04", "2026-11-13", trig=1.5, rec=0.5, use_sep=True, use_nsl=True)

    c09_d2, m09_d2, s09_d2, eq09_d2, s_eq_d2, trades_d2 = run_v1_daily("2009-01-02", "2026-11-13", trig=1.2, rec=0.3, use_sep=True, use_nsl=True)
    c10_d2, m10_d2, s10_d2, eq10_d2, _, _ = run_v1_daily("2010-01-04", "2026-11-13", trig=1.2, rec=0.3, use_sep=True, use_nsl=True)

    c09_m1, m09_m1, s09_m1, eq09_m1 = run_v1_monthly(pd.Timestamp("2008-12-31"), pd.Timestamp("2026-09-30"), k=1.0, power=2.0, use_sep=True, use_nsl=True)
    c10_m1, m10_m1, s10_m1, eq10_m1 = run_v1_monthly(pd.Timestamp("2009-12-31"), pd.Timestamp("2026-09-30"), k=1.0, power=2.0, use_sep=True, use_nsl=True)

    rows = [
        ("1. V1-Daily Standard (FROZEN PRIMARY: Vol_Z 1.5/0.5 + NSL)", c09_d1, m09_d1, s09_d1, eq09_d1, c10_d1, m10_d1, s10_d1, eq10_d1),
        ("2. V1-Daily Sweet-Spot (FROZEN PLATEAU: Vol_Z 1.2/0.3 + NSL)", c09_d2, m09_d2, s09_d2, eq09_d2, c10_d2, m10_d2, s10_d2, eq10_d2),
        ("3. V1-Monthly Reference ((std_252/std_21)^2 + NSL)", c09_m1, m09_m1, s09_m1, eq09_m1, c10_m1, m10_m1, s10_m1, eq10_m1),
        ("4. Pure SEP Baseline (SEP=ON 100% TQQQ, SEP=OFF Cash)", c09_pure, m09_pure, s09_pure, eq09_pure, c10_pure, m10_pure, s10_pure, eq10_pure),
    ]
    df_summary = pd.DataFrame(rows, columns=[
        "Strategy", "2009_2026_CAGR", "2009_2026_MaxDD", "2009_2026_Sharpe", "2009_2026_Mult",
        "2010_2026_CAGR", "2010_2026_MaxDD", "2010_2026_Sharpe", "2010_2026_Mult"
    ])
    df_summary.to_csv(os.path.join(OUT_DIR, "v1_tqqq_summary.csv"), index=False)
    trades_d1.to_csv(os.path.join(OUT_DIR, "v1_daily_trade_ledger_2009_2026.csv"), index=False)
    trades_d2.to_csv(os.path.join(OUT_DIR, "v1_daily_sweetspot_trade_ledger_2009_2026.csv"), index=False)

    # 2. Annual Returns Breakdown (2009..2026)
    qqq_eq = (1.0 + r_qqq.loc["2009-01-02":"2026-11-13"]).cumprod()
    tqqq_eq = (1.0 + r_tqqq.loc["2009-01-02":"2026-11-13"]).cumprod()
    ann_rows = []
    for yr in range(2009, 2027):
        yr_str = str(yr)
        def yr_ret(ser):
            sub = ser.loc[yr_str]
            prev = ser.loc[:f"{yr-1}-12-31"]
            base = float(prev.iloc[-1]) if len(prev) > 0 else 1.0
            return round((float(sub.iloc[-1]) / base - 1.0) * 100.0, 2)
        def yr_mdd(ser):
            sub = ser.loc[yr_str]
            return round(float((sub / sub.cummax() - 1.0).min()) * 100.0, 2)
        ann_rows.append({
            "Year": yr,
            "QQQ_1x_Ret_%": yr_ret(qqq_eq),
            "TQQQ_3x_BH_Ret_%": yr_ret(tqqq_eq),
            "Pure_SEP_Ret_%": yr_ret(s_eq_pure),
            "V1_Daily_1.5_0.5_Ret_%": yr_ret(s_eq_d1),
            "V1_Daily_1.2_0.3_Ret_%": yr_ret(s_eq_d2),
            "V1_Daily_1.5_0.5_MaxDD_%": yr_mdd(s_eq_d1),
        })
    df_ann = pd.DataFrame(ann_rows)
    df_ann.to_csv(os.path.join(OUT_DIR, "v1_daily_annual_returns_2009_2026.csv"), index=False)

    # 3. Parameter Plateau Grid
    grid_rows = []
    for trig in [1.0, 1.2, 1.3, 1.5, 1.8, 2.0]:
        for rec in [0.0, 0.2, 0.3, 0.5, 0.7]:
            c09, m09, s09, eq09, _, tr_df = run_v1_daily("2009-01-02", "2026-11-13", trig=trig, rec=rec, use_sep=True, use_nsl=True)
            c10, m10, s10, eq10, _, _ = run_v1_daily("2010-01-04", "2026-11-13", trig=trig, rec=rec, use_sep=True, use_nsl=True)
            grid_rows.append({
                "Trig": trig, "Rec": rec,
                "2009_2026_CAGR_%": round(c09, 2), "2009_2026_MaxDD_%": round(m09, 2), "2009_2026_Sharpe": round(s09, 3), "2009_2026_Mult": round(eq09, 1),
                "2010_2026_CAGR_%": round(c10, 2), "2010_2026_MaxDD_%": round(m10, 2), "2010_2026_Sharpe": round(s10, 3), "2010_2026_Mult": round(eq10, 1),
                "Trades": len(tr_df),
            })
    df_grid = pd.DataFrame(grid_rows)
    df_grid.to_csv(os.path.join(OUT_DIR, "v1_daily_parameter_grid_2009_2026.csv"), index=False)

    print("=========================================================================================================")
    print("OFFICIAL FROZEN V1-DAILY TQQQ STRATEGY AUDIT SUMMARY")
    print("=========================================================================================================")
    for _, r_row in df_summary.iterrows():
        print(f"{r_row['Strategy']:<62} | 09-26: {r_row['2009_2026_CAGR']:5.1f}% (MDD {r_row['2009_2026_MaxDD']:5.1f}%, Sh {r_row['2009_2026_Sharpe']:4.2f}, {r_row['2009_2026_Mult']:7.1f}x) | 10-26: {r_row['2010_2026_CAGR']:5.1f}% (MDD {r_row['2010_2026_MaxDD']:5.1f}%, Sh {r_row['2010_2026_Sharpe']:4.2f}, {r_row['2010_2026_Mult']:7.1f}x)")
    print("\n--- V1-DAILY TRADE LEDGER (2009-2026, Trig=1.5 / Rec=0.5) ---")
    print(trades_d1.to_string(index=False))
