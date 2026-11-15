#!/usr/bin/env python3
"""
vrp_realized_minus_vix_test.py — Clean, zero-tuning empirical test of
(Realized Volatility - Implied Volatility [VIX / VXN]) across 1990-2026 (36.8 years).

Tests all standard economic definitions without threshold tuning:
  1. Direct predictive power of (RV21 - VIX) & (RV21_NDX - VXN) on next-month index & 3x returns:
     - Sign split: RV21 > VIX (VRP < 0) vs RV21 <= VIX (VRP >= 0)
     - 5 Quintiles of (RV21 - VIX) from 1990-01 to 2026-10 (441 months), plus 1990-2009 vs 2010-2026 subperiods
  2. Binary timing rules (standalone & combined with SEP + VM):
     - H1: Exit / de-leverage when RV21 > VIX (realized turbulence > implied vol)
     - H2: Exit / de-leverage when VIX - RV21 is in top quintile (extreme option fear premium)
     - H3: Earlier project rule (BAA-10Y 21d widening > 10bp & VIX > RV21_QQQ) tested back to 1990!
  3. Using VIX / VXN inside Volatility Management (VM):
     - Baseline B5 (Backward RV21 variance scaling: w = min(1, med_RV21^2 / RV21^2))
     - V1: Pure Implied Vol scaling (w = min(1, med_VIX^2 / VIX^2))
     - V2: 50/50 Blend of RV21 and VIX variance scaling
     - V3: Conservative Max(RV21, VIX) variance scaling
     - V4: Asymmetric VRP-aware VM: when RV21 > VIX (crash already happened & VIX is subsiding),
           use forward-looking VIX^2 instead of backward-looking lagged RV21^2!
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "vrp_realized_minus_vix_20261115")
os.makedirs(OUT, exist_ok=True)

# Load base series from break_signals_test.py
bsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bsrc, bs)
fred, yahoo, sig = bs["fred"], bs["yahoo"], bs["sig"]

# Load SEP real regime (2015-11-30+)
REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

# Load VIX (1990-01-02+) and VXN (2001-01-23+) from FRED
vix = fred("VIXCLS")
vxn = fred("VXNCLS")
spx = yahoo("_GSPC")
ixic = yahoo("_IXIC")
baa = fred("DBAA")
g10 = fred("DGS10")
baa_sp_d = (baa - g10.reindex(baa.index)).dropna()

# Compute daily 21-day annualized realized volatility (in % points to match VIX)
r_spx = spx.pct_change().dropna()
r_ixic = ixic.pct_change().dropna()
rv21_spx = r_spx.rolling(21).std(ddof=1) * np.sqrt(252) * 100.0
rv21_ixic = r_ixic.rolling(21).std(ddof=1) * np.sqrt(252) * 100.0

# Expanding medians (for zero-look-ahead Volatility Management, using full 1971+ history for SPX/NDX)
med_rv21_spx = rv21_spx.expanding(min_periods=252).median()
med_rv21_ixic = rv21_ixic.expanding(min_periods=252).median()
med_vix = vix.expanding(min_periods=252).median()
med_vxn = vxn.expanding(min_periods=252).median()

# Evaluation months: 1990-01-31 .. 2026-09-30 (441 months where VIX exists)
T_all = [t for t in bs["T"] if pd.Timestamp("1990-01-31") <= t <= pd.Timestamp("2026-09-30")]

# Synthetic monthly 1x / 3x / Cash returns (Nasdaq Composite)
rf_d = (fred("DGS3MO") / 100.0).reindex(r_ixic.index).ffill().bfill() / 252.0
borrow_spread = 0.005 / 252.0
synth_m = {0: {}, 1: {}, 3: {}}
for t in T_all:
    days = r_ixic.loc[(r_ixic.index > t) & (r_ixic.index <= t + pd.offsets.MonthEnd(1))].index
    synth_m[0][t] = float((1.0 + rf_d.loc[days]).prod() - 1.0)
    for L, er in ((1, 0.0020), (3, 0.0095)):
        d_lev = L * r_ixic.loc[days] - (L - 1) * (rf_d.loc[days] + borrow_spread) - er / 252.0
        synth_m[L][t] = float((1.0 + d_lev).prod() - 1.0)

# Actual ETFs (2010-04..2026-10)
ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
def load_etf_close(sym):
    d = json.load(open(os.path.join(ETF_DIR, f"{sym}.json")))
    s = pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]

qqq_p = load_etf_close("QQQ")
tqqq_p = load_etf_close("TQQQ")
bil_p = load_etf_close("BIL")
sgov_p = load_etf_close("SGOV")
rv21_qqq = qqq_p.pct_change().dropna().rolling(21).std(ddof=1) * np.sqrt(252) * 100.0
med_rv21_qqq = rv21_qqq.expanding(min_periods=252).median()

T_etf = [t for t in T_all if t >= pd.Timestamp("2010-03-31")]
actual_m = {0: {}, 1: {}, 3: {}}
actual_d = {0: {}, 1: {}, 3: {}}
for t in T_etf:
    t1 = t + pd.offsets.MonthEnd(1)
    cp = sgov_p if t >= pd.Timestamp("2020-06-30") else bil_p
    actual_m[0][t] = float(cp.loc[:t1].iloc[-1] / cp.loc[:t].iloc[-1] - 1.0)
    days = qqq_p.loc[(qqq_p.index > t) & (qqq_p.index <= t1)].index
    actual_d[0][t] = cp.pct_change().reindex(days).fillna(0.0)
    for L, ser in ((1, qqq_p), (3, tqqq_p)):
        actual_m[L][t] = float(ser.loc[:t1].iloc[-1] / ser.loc[:t].iloc[-1] - 1.0)
        actual_d[L][t] = ser.pct_change().reindex(days).fillna(0.0)

# Build monthly panel of RV, VIX, VXN, and RV - VIX spreads at each month-end t
rows = []
for t in T_all:
    sep_on = bool(real_sep[t]) if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t])
    vix_t = float(vix.loc[:t].iloc[-1])
    rv_spx_t = float(rv21_spx.loc[:t].iloc[-1])
    rv_ndx_t = float(rv21_ixic.loc[:t].iloc[-1])
    vxn_sub = vxn.loc[:t]
    vxn_t = float(vxn_sub.iloc[-1]) if len(vxn_sub) else np.nan

    # Medians as of t (fallback to initial 252d median in 1990)
    m_rv_ndx = float(med_rv21_ixic.loc[:t].iloc[-1]) if len(med_rv21_ixic.loc[:t]) else float(rv21_ixic.loc[:"1990-12-31"].median())
    m_vix = float(med_vix.loc[:t].iloc[-1]) if len(med_vix.loc[:t]) else float(vix.loc[:"1990-12-31"].median())
    m_vxn = float(med_vxn.loc[:t].iloc[-1]) if len(med_vxn.loc[:t]) else m_rv_ndx

    # BAA-10Y 21-day change in bp (with 1-day publication lag)
    b_sub = baa_sp_d.loc[:t - pd.Timedelta(days=1)]
    baa_21d_bp = float((b_sub.iloc[-1] - b_sub.iloc[-22]) * 100.0) if len(b_sub) >= 22 else 0.0

    rows.append({
        "t": t,
        "sep_on": sep_on,
        "vix": vix_t,
        "vxn": vxn_t,
        "rv_spx": rv_spx_t,
        "rv_ndx": rv_ndx_t,
        "rv_minus_vix_spx": rv_spx_t - vix_t,          # SPX Realized - VIX
        "rv_minus_vxn_ndx": rv_ndx_t - vxn_t if np.isfinite(vxn_t) else (rv_ndx_t - vix_t),
        "rv_ndx_minus_vix": rv_ndx_t - vix_t,          # NDX Realized - VIX
        "m_rv_ndx": m_rv_ndx,
        "m_vix": m_vix,
        "m_vxn": m_vxn,
        "baa_21d_bp": baa_21d_bp,
        "ret_1x_next": synth_m[1][t],
        "ret_3x_next": synth_m[3][t],
        "ret_cash_next": synth_m[0][t],
    })

P = pd.DataFrame(rows).set_index("t")

# =============================================================================
# PART 1: Direct Return Anatomy by Sign & Quintile of (RV21 - VIX)
# =============================================================================
print("==========================================================================================")
print("PART 1: WHAT DOES (REALIZED VOL - VIX) PREDICT FOR NEXT-MONTH RETURNS? (1990-01..2026-10)")
print("==========================================================================================")

for period_label, sub in [
    ("Full 36.8 Years (1990-01..2026-10, N=441m)", P),
    ("Pre-ETF Era (1990-01..2009-12, N=240m)", P.loc[:"2009-12-31"]),
    ("Modern ETF Era (2010-01..2026-10, N=201m)", P.loc["2010-01-01":]),
]:
    print(f"\n--- {period_label} [Using SPX Matched Pair: RV21_SPX - VIX] ---")
    for cond_name, mask in [
        ("RV21_SPX > VIX  (Realized > Implied, VRP < 0)", sub["rv_minus_vix_spx"] > 0),
        ("RV21_SPX <= VIX (Normal: Implied >= Realized)", sub["rv_minus_vix_spx"] <= 0),
        ("  of which: VIX - RV21 > +6.0 (High Implied Fear)", sub["rv_minus_vix_spx"] < -6.0),
        ("  of which: RV21 - VIX > +5.0 (Extreme Realized Crash)", sub["rv_minus_vix_spx"] > 5.0),
    ]:
        s = sub[mask]
        if not len(s):
            continue
        r1_ann = (1.0 + s["ret_1x_next"]).prod() ** (12.0 / len(s)) - 1.0
        r3_ann = (1.0 + s["ret_3x_next"]).prod() ** (12.0 / len(s)) - 1.0
        r1_avg = s["ret_1x_next"].mean()
        win1 = (s["ret_1x_next"] > 0).mean()
        print(f"  {cond_name:<52} | N={len(s):3d}m | Next-1M Avg(1x): {r1_avg:+6.2%} | Win%: {win1:5.1%} | Ann(1x): {r1_ann:+6.1%} | Ann(3x): {r3_ann:+6.1%}")

print("\n--- 5 Quintiles of (RV21_SPX - VIX) across Full 1990-2026 (Q1 = VIX >> RV21, Q5 = RV21 >> VIX) ---")
P["q_spread"] = pd.qcut(P["rv_minus_vix_spx"], 5, labels=["Q1 (VIX>>RV, High VRP)", "Q2", "Q3", "Q4", "Q5 (RV>>VIX, Neg VRP)"])
for q, g in P.groupby("q_spread", observed=False):
    r1_ann = (1.0 + g["ret_1x_next"]).prod() ** (12.0 / len(g)) - 1.0
    r3_ann = (1.0 + g["ret_3x_next"]).prod() ** (12.0 / len(g)) - 1.0
    print(f"  {str(q):<26} | Range: [{g['rv_minus_vix_spx'].min():+5.1f}, {g['rv_minus_vix_spx'].max():+5.1f}] | N={len(g):3d}m | Next-1M Avg(1x): {g['ret_1x_next'].mean():+6.2%} | Ann(1x): {r1_ann:+6.1%} | Ann(3x): {r3_ann:+6.1%}")

# =============================================================================
# PART 2: Backtesting (RV21 - VIX) Strategies in 1990-2026 & 2010-2026 (Actual TQQQ)
# =============================================================================
COST = 0.0010

def sim(weight_fn, t_list, ret_dict, is_etf=False, daily_dict=None):
    m_rets = {}
    d_rets = []
    prev_w = 0.0
    for t in t_list:
        row = P.loc[t]
        if is_etf:
            rv_cur = float(rv21_qqq.loc[:t].iloc[-1])
            m_rv = float(med_rv21_qqq.loc[:t].iloc[-1])
        else:
            rv_cur = float(row["rv_ndx"])
            m_rv = float(row["m_rv_ndx"])
        w = float(np.clip(weight_fn(row, rv_cur, m_rv), 0.0, 1.0)) if row["sep_on"] else 0.0
        cost = abs(w - prev_w) * COST
        prev_w = w
        gross = w * ret_dict[3][t] + (1.0 - w) * ret_dict[0][t]
        m_rets[t + pd.offsets.MonthEnd(1)] = (1.0 + gross) * (1.0 - cost) - 1.0
        if daily_dict is not None:
            rd = w * daily_dict[3][t] + (1.0 - w) * daily_dict[0][t]
            if len(rd):
                rd = rd.copy()
                rd.iloc[0] = (1.0 + rd.iloc[0]) * (1.0 - cost) - 1.0
                d_rets.append(rd)
    return pd.Series(m_rets).sort_index(), (pd.concat(d_rets).sort_index() if d_rets else None)

def metrics(s_m, rf_ser, s_d=None):
    w = (1.0 + s_m).cumprod()
    w0 = pd.concat([pd.Series([1.0], index=[s_m.index[0] - pd.offsets.MonthEnd(1)]), w])
    cagr = float(w.iloc[-1] ** (12.0 / len(s_m)) - 1.0)
    mdd = float((w0 / w0.cummax() - 1.0).min())
    ex = s_m - rf_ser.reindex(s_m.index).fillna(0.0)
    sh = float(ex.mean() / s_m.std(ddof=1) * np.sqrt(12.0))
    cal = cagr / abs(mdd) if mdd < 0 else 0.0
    mdd_d = np.nan
    if s_d is not None:
        wd = (1.0 + s_d).cumprod()
        wd0 = pd.concat([pd.Series([1.0], index=[s_d.index[0] - pd.Timedelta(days=1)]), wd])
        mdd_d = float((wd0 / wd0.cummax() - 1.0).min())
    return {"CAGR": cagr, "Sharpe": sh, "Calmar": cal, "MaxDD_M": mdd, "MaxDD_D": mdd_d}

rf_synth_ser = pd.Series({t + pd.offsets.MonthEnd(1): synth_m[0][t] for t in T_all})
rf_etf_ser = pd.Series({t + pd.offsets.MonthEnd(1): actual_m[0][t] for t in T_etf})

candidates = {
    "0a. B3 Raw: SEP Only (100% 3x when SEP=ON, No VM)":
        lambda r, rv, m_rv: 1.0,

    "0b. B3 + Exit to Cash when RV21_SPX > VIX (No VM, Only RV>VIX switch)":
        lambda r, rv, m_rv: 0.0 if (r["rv_minus_vix_spx"] > 0) else 1.0,

    "0. B5 Baseline: SEP + RV21 Variance VM (med_RV^2 / RV^2)":
        lambda r, rv, m_rv: min(1.0, (m_rv / rv) ** 2),

    "1. V1: SEP + Pure VIX Implied Variance VM (med_VIX^2 / VIX^2)":
        lambda r, rv, m_rv: min(1.0, (r["m_vix"] / r["vix"]) ** 2),

    "2. V2: SEP + 50/50 Blend of RV21_VM and VIX_VM":
        lambda r, rv, m_rv: 0.5 * min(1.0, (m_rv / rv) ** 2) + 0.5 * min(1.0, (r["m_vix"] / r["vix"]) ** 2),

    "3. V3: SEP + Conservative min(RV21_VM, VIX_VM) [De-risks on whichever is higher]":
        lambda r, rv, m_rv: min(1.0, (m_rv / rv) ** 2, (r["m_vix"] / r["vix"]) ** 2),

    "4. V4: SEP + Max(RV21_VM, VIX_VM) [Uses VIX when VIX subsides faster than lagged RV21]":
        lambda r, rv, m_rv: max(min(1.0, (m_rv / rv) ** 2), min(1.0, (r["m_vix"] / r["vix"]) ** 2)),

    "5. H1a: SEP + RV21_VM, but 0% Cash when RV21_SPX > VIX (Negative VRP exit)":
        lambda r, rv, m_rv: 0.0 if (r["rv_minus_vix_spx"] > 0) else min(1.0, (m_rv / rv) ** 2),

    "6. H1b: SEP + RV21_VM, but Halve weight when RV21_SPX > VIX":
        lambda r, rv, m_rv: (0.5 if (r["rv_minus_vix_spx"] > 0) else 1.0) * min(1.0, (m_rv / rv) ** 2),

    "7. H2: SEP + RV21_VM, but 0% Cash when VIX - RV21_SPX > +6.0 (High Implied Fear exit)":
        lambda r, rv, m_rv: 0.0 if (r["rv_minus_vix_spx"] < -6.0) else min(1.0, (m_rv / rv) ** 2),

    "8. H3 (Earlier Combo 1): SEP + RV21_VM, Cut when BAA_21d > 10bp & VIX > RV21":
        lambda r, rv, m_rv: (0.33 if (r["baa_21d_bp"] > 10.0 and r["rv_minus_vix_spx"] < 0) else 1.0) * min(1.0, (m_rv / rv) ** 2),
}

b5_all, _ = sim(candidates["0. B5 Baseline: SEP + RV21 Variance VM (med_RV^2 / RV^2)"], T_all, synth_m, is_etf=False)
b5_etf, _ = sim(candidates["0. B5 Baseline: SEP + RV21 Variance VM (med_RV^2 / RV^2)"], T_etf, actual_m, is_etf=True)

out_rows = []
for name, fn in candidates.items():
    sm_all, _ = sim(fn, T_all, synth_m, is_etf=False)
    sm_90_09 = sm_all.loc[:"2009-12-31"]
    sm_etf, sd_etf = sim(fn, T_etf, actual_m, is_etf=True, daily_dict=actual_d)

    m_all = metrics(sm_all, rf_synth_ser)
    m_90 = metrics(sm_90_09, rf_synth_ser)
    m_etf = metrics(sm_etf, rf_etf_ser, s_d=sd_etf)

    # Paired t-stat vs B5 in 1990-2026
    if name.startswith("0. B5"):
        t_all, t_etf = 0.0, 0.0
    else:
        d_all = (sm_all - b5_all).dropna()
        t_all = float(d_all.mean() / d_all.std(ddof=1) * np.sqrt(len(d_all))) if d_all.std(ddof=1) > 0 else 0.0
        d_etf = (sm_etf - b5_etf).dropna()
        t_etf = float(d_etf.mean() / d_etf.std(ddof=1) * np.sqrt(len(d_etf))) if d_etf.std(ddof=1) > 0 else 0.0

    out_rows.append({
        "Strategy": name,
        "90_26_CAGR": f"{m_all['CAGR']:.1%}",
        "90_26_Sh": f"{m_all['Sharpe']:.2f}",
        "90_26_MDD": f"{m_all['MaxDD_M']:.1%}",
        "t_vs_B5(37y)": f"{t_all:+.2f}",
        "90_09_CAGR": f"{m_90['CAGR']:.1%}",
        "90_09_Sh": f"{m_90['Sharpe']:.2f}",
        "90_09_MDD": f"{m_90['MaxDD_M']:.1%}",
        "ETF_10_26_CAGR": f"{m_etf['CAGR']:.1%}",
        "ETF_10_26_Sh": f"{m_etf['Sharpe']:.2f}",
        "ETF_MDD_M": f"{m_etf['MaxDD_M']:.1%}",
        "ETF_MDD_D": f"{m_etf['MaxDD_D']:.1%}",
        "t_vs_B5(ETF)": f"{t_etf:+.2f}",
    })

res_df = pd.DataFrame(out_rows)
res_df.to_csv(os.path.join(OUT, "vrp_strategies_1990_2026_summary.csv"), index=False)
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 20)
print("\n==========================================================================================")
print("PART 2: STRATEGY BACKTEST RESULTS (1990-2026 FULL 37Y, 1990-2009 PRE-ETF, 2010-2026 ETF)")
print("==========================================================================================")
print(res_df.to_string(index=False))
