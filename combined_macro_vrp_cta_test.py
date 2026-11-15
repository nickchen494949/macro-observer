#!/usr/bin/env python3
"""
combined_macro_vrp_cta_test.py — Combining all 4 pillars across 1990-2026 (37 years) and 2010-2026 (Actual TQQQ):
  1. Macro Gate      : FOMC SEP (SEP = ON vs SEP = OFF)
  2. Dual Vol / VRP  : Realized Vol (RV21) + Implied Vol (VIX) + VRP (VIX - RV21)
  3. Institutional CTA (Man AHL / Baz 2015 + Goldman Crowding Cliff / Capitulation):
     - Overextension Trim: Baz curve psi(z) when trend Z-score z_comp > sqrt(2) (~1.41 sigma)
     - Crowded Cliff vs Capitulation Washout
  4. Credit Stress   : High-Yield / Credit Spread spike filter (from Dashboard Rates section)

Plus: Live 2026-11 diagnostic readout of all combined indicators right now!
"""
import json
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "outputs", "combined_macro_vrp_cta_20261115")
os.makedirs(OUT, exist_ok=True)

# 1. Load base data & institutional CTA features
bsrc = open(os.path.join(ROOT, "break_signals_test.py")).read().split("# ----------------------------------------------------------------------------- A. index-level timing")[0]
bs = {"__file__": os.path.join(ROOT, "break_signals_test.py")}
exec(bsrc, bs)
fred, yahoo, sig, T = bs["fred"], bs["yahoo"], bs["sig"], bs["T"]

REG = pd.read_csv(os.path.join(ROOT, "outputs", "pure_momentum_1985_2026_audit", "inputs", "v3_regime_and_cash_214m.csv"))
real_sep = dict(zip(pd.to_datetime(REG["t"]), REG["sep_on"].astype(bool)))

csrc = open(os.path.join(ROOT, "cta_institutional_deep_test.py")).read().split("ixic = yahoo(\"_IXIC\")")[0]
cs = {"__file__": os.path.join(ROOT, "cta_institutional_deep_test.py"), "np": np, "pd": pd}
exec(csrc, cs)
build_institutional_cta_features = cs["build_institutional_cta_features"]

ETF_DIR = os.path.join(ROOT, "outputs", "remediation_full_audit_20261104", "tiingo_etfs")
def load_etf_close(sym):
    d = json.load(open(os.path.join(ETF_DIR, f"{sym}.json")))
    s = pd.Series({pd.Timestamp(r["date"][:10]): float(r["adjClose"]) for r in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]

ixic = yahoo("_IXIC")
gspc = yahoo("_GSPC")
vix = fred("VIXCLS")
vxn = fred("VXNCLS")

df_ixic = build_institutional_cta_features(ixic)
qqq_p = load_etf_close("QQQ")
tqqq_p = load_etf_close("TQQQ")
qld_p = load_etf_close("QLD")
bil_p = load_etf_close("BIL")
sgov_p = load_etf_close("SGOV")
df_qqq = build_institutional_cta_features(qqq_p)

# SPX 21d realized vol (to pair apples-to-apples with VIX)
rv21_spx = gspc.pct_change().dropna().rolling(21).std(ddof=1) * np.sqrt(252) * 100.0
med_vix = vix.expanding(min_periods=252).median()
med_vxn = vxn.expanding(min_periods=252).median()

# Synthetic monthly 1x / 2x / 3x / Cash on Nasdaq (1990-01..2026-10)
T90 = [t for t in T if t >= pd.Timestamp("1990-01-31")]
rf_d = (fred("DGS3MO") / 100.0).reindex(df_ixic.index).ffill().bfill() / 252.0
borrow_spread = 0.005 / 252.0
synth_m = {0: {}, 1: {}, 2: {}, 3: {}}
synth_d = {0: {}, 1: {}, 2: {}, 3: {}}
for t in T90:
    days = df_ixic.loc[(df_ixic.index > t) & (df_ixic.index <= t + pd.offsets.MonthEnd(1))].index
    synth_m[0][t] = float((1.0 + rf_d.loc[days]).prod() - 1.0)
    synth_d[0][t] = rf_d.loc[days]
    for L, er in ((1, 0.0020), (2, 0.0095), (3, 0.0095)):
        d_lev = L * df_ixic["r"].loc[days] - (L - 1) * (rf_d.loc[days] + borrow_spread) - er / 252.0
        synth_m[L][t] = float((1.0 + d_lev).prod() - 1.0)
        synth_d[L][t] = d_lev

# Actual ETFs (2010-04..2026-10)
T_etf = [t for t in T90 if t >= pd.Timestamp("2010-03-31")]
actual_m = {0: {}, 1: {}, 2: {}, 3: {}}
actual_d = {0: {}, 1: {}, 2: {}, 3: {}}
for t in T_etf:
    t1 = t + pd.offsets.MonthEnd(1)
    cp = sgov_p if t >= pd.Timestamp("2020-06-30") else bil_p
    actual_m[0][t] = float(cp.loc[:t1].iloc[-1] / cp.loc[:t].iloc[-1] - 1.0)
    days = qqq_p.loc[(qqq_p.index > t) & (qqq_p.index <= t1)].index
    actual_d[0][t] = cp.pct_change().reindex(days).fillna(0.0)
    for L, ser in ((1, qqq_p), (2, qld_p), (3, tqqq_p)):
        actual_m[L][t] = float(ser.loc[:t1].iloc[-1] / ser.loc[:t].iloc[-1] - 1.0)
        actual_d[L][t] = ser.pct_change().reindex(days).fillna(0.0)

def get_state_at(t, is_etf=False):
    sep_on = bool(real_sep[t]) if t >= pd.Timestamp("2015-11-30") else bool(sig["SEP_PROXY"][t])
    row = (df_qqq if is_etf else df_ixic).loc[:t].iloc[-1]

    # 1. Realized Vol Variance Weight (w_rv)
    w_rv = float(row["w_var_2"])

    # 2. VIX Implied Vol Variance Weight (w_vix) & VRP
    vix_t = float(vix.loc[:t].iloc[-1])
    mvix_t = float(med_vix.loc[:t].iloc[-1]) if pd.notna(med_vix.loc[:t].iloc[-1]) else 19.0
    w_vix = min(1.0, (mvix_t / vix_t) ** 2)
    rv_spx_t = float(rv21_spx.loc[:t].iloc[-1])
    vrp_t = vix_t - rv_spx_t  # VIX minus Realized Vol

    # Dual Volatility brake: min(w_rv, w_vix) ("whichever is higher risk, actual shaking or VIX, brakes position")
    w_dual_vol = min(w_rv, w_vix)
    # Soft Blend Vol brake: 0.5 * w_rv + 0.5 * w_vix
    w_blend_vol = 0.5 * w_rv + 0.5 * w_vix

    # 3. Institutional CTA features:
    z_comp = float(row["z_comp"])
    psi_long = float(row["psi_long"])
    # Baz Overextension Trim factor: 1.0 when z_comp <= sqrt(2), else psi_long (smoothly trims when overbought > 1.41 sigma)
    baz_trim = psi_long if z_comp > np.sqrt(2.0) else 1.0
    # Crowded Cliff warning: was crowded long 5 days ago, now dropping & vol spiking
    crowded_cliff = bool(row["crowded_long_5d_ago"]) and (float(row["rv_cta"]) > float(row["med_rv21"]) * 1.15) and (float(row["dd_sigma"]) < -1.5)
    # Capitulation / Washout: CTA completely washed out (z_comp <= -1.0 and -3sigma hit) -> don't under-invest if SEP=ON!
    cta_washed_out = (z_comp <= -1.0) and (float(row["dd_sigma"]) <= -2.5)

    # 4. Dashboard Credit Stress (HY OAS / BAA spread blowout: sig["CREDIT"] is False when stressed)
    credit_stress = not bool(sig["CREDIT"][t])

    return {
        "sep_on": sep_on,
        "w_rv": w_rv,
        "w_vix": w_vix,
        "w_dual_vol": w_dual_vol,
        "w_blend_vol": w_blend_vol,
        "vrp": vrp_t,
        "z_comp": z_comp,
        "psi_long": psi_long,
        "baz_trim": baz_trim,
        "crowded_cliff": crowded_cliff,
        "cta_washed_out": cta_washed_out,
        "credit_stress": credit_stress,
    }

COST = 0.0010

def sim_comb(weight_fn, t_list, ret_dict, daily_dict, is_etf=False):
    m_rets = {}
    d_rets = []
    prev_w = 0.0
    weights_log = []
    for t in t_list:
        st = get_state_at(t, is_etf=is_etf)
        w = float(np.clip(weight_fn(st), 0.0, 1.0))
        weights_log.append(w)
        cost = abs(w - prev_w) * COST
        prev_w = w
        gross = w * ret_dict[3][t] + (1.0 - w) * ret_dict[0][t]
        m_rets[t + pd.offsets.MonthEnd(1)] = (1.0 + gross) * (1.0 - cost) - 1.0
        rd = w * daily_dict[3][t] + (1.0 - w) * daily_dict[0][t]
        if len(rd):
            rd = rd.copy()
            rd.iloc[0] = (1.0 + rd.iloc[0]) * (1.0 - cost) - 1.0
            d_rets.append(rd)
    return pd.Series(m_rets).sort_index(), pd.concat(d_rets).sort_index(), float(np.mean(weights_log))

def metrics(s_m, rf_ser, s_d):
    w = (1.0 + s_m).cumprod()
    w0 = pd.concat([pd.Series([1.0], index=[s_m.index[0] - pd.offsets.MonthEnd(1)]), w])
    cagr = float(w.iloc[-1] ** (12.0 / len(s_m)) - 1.0)
    mdd_m = float((w0 / w0.cummax() - 1.0).min())
    ex = s_m - rf_ser.reindex(s_m.index).fillna(0.0)
    sh = float(ex.mean() / s_m.std(ddof=1) * np.sqrt(12.0))
    wd = (1.0 + s_d).cumprod()
    wd0 = pd.concat([pd.Series([1.0], index=[s_d.index[0] - pd.Timedelta(days=1)]), wd])
    dd_ser = wd0 / wd0.cummax() - 1.0
    mdd_d = float(dd_ser.min())
    calmar = cagr / abs(mdd_d) if mdd_d < 0 else np.nan
    return {"CAGR": cagr, "Sharpe": sh, "MaxDD_M": mdd_m, "MaxDD_D": mdd_d, "Calmar_D": calmar}

rf_synth_ser = pd.Series({t + pd.offsets.MonthEnd(1): synth_m[0][t] for t in T90})
rf_etf_ser = pd.Series({t + pd.offsets.MonthEnd(1): actual_m[0][t] for t in T_etf})

strategies = {
    # Single & Pair Building Blocks
    "1. B5 Baseline: SEP + Realized Vol (w_rv)":
        lambda s: s["w_rv"] if s["sep_on"] else 0.0,
    "2. SEP + Dual Vol [min(RV21, VIX)]":
        lambda s: s["w_dual_vol"] if s["sep_on"] else 0.0,
    "3. SEP + RV21 + CTA Baz Overextension Trim (w_rv * baz_trim)":
        lambda s: (s["w_rv"] * s["baz_trim"]) if s["sep_on"] else 0.0,

    # Full Combinations (SEP + Vol/VIX + CTA Overextension / Cliff / Washout)
    "4. COMBO A: SEP + Dual Vol [min(RV21, VIX)] * CTA Baz Overextension Trim":
        lambda s: (s["w_dual_vol"] * s["baz_trim"]) if s["sep_on"] else 0.0,
    "5. COMBO B: SEP + Blend Vol [0.5*RV21 + 0.5*VIX] * CTA Baz Overextension Trim":
        lambda s: (s["w_blend_vol"] * s["baz_trim"]) if s["sep_on"] else 0.0,
    "6. COMBO C: COMBO A + Crowded CTA Cliff Cut (halve on cliff) + Washout Rebound Floor":
        lambda s: (
            max(0.35, s["w_dual_vol"]) if s["cta_washed_out"]
            else (0.5 * s["w_dual_vol"] * s["baz_trim"] if s["crowded_cliff"] else s["w_dual_vol"] * s["baz_trim"])
        ) if s["sep_on"] else 0.0,
    "7. COMBO D: COMBO B + VRP Panic Cut (halve if RV21 > VIX + 5) + Credit Stress Cut":
        lambda s: (
            s["w_blend_vol"] * s["baz_trim"]
            * (0.5 if s["vrp"] < -5.0 else 1.0)
            * (0.5 if s["credit_stress"] else 1.0)
        ) if s["sep_on"] else 0.0,
}

rows = []
for name, fn in strategies.items():
    sm_90, sd_90, avgw_90 = sim_comb(fn, T90, synth_m, synth_d, is_etf=False)
    sm_90_09 = sm_90.loc[:"2009-12-31"]
    sd_90_09 = sd_90.loc[:"2009-12-31"]
    sm_etf, sd_etf, avgw_etf = sim_comb(fn, T_etf, actual_m, actual_d, is_etf=True)

    m_90 = metrics(sm_90, rf_synth_ser, sd_90)
    m_pre = metrics(sm_90_09, rf_synth_ser, sd_90_09)
    m_etf = metrics(sm_etf, rf_etf_ser, sd_etf)

    rows.append({
        "Strategy": name,
        "90_26_CAGR": f"{m_90['CAGR']:.1%}",
        "90_26_Sh": f"{m_90['Sharpe']:.2f}",
        "90_26_MDD_M": f"{m_90['MaxDD_M']:.1%}",
        "90_09_CAGR": f"{m_pre['CAGR']:.1%}",
        "90_09_Sh": f"{m_pre['Sharpe']:.2f}",
        "ETF_10_26_CAGR": f"{m_etf['CAGR']:.1%}",
        "ETF_10_26_Sh": f"{m_etf['Sharpe']:.2f}",
        "ETF_MDD_M": f"{m_etf['MaxDD_M']:.1%}",
        "ETF_MDD_D": f"{m_etf['MaxDD_D']:.1%}",
        "ETF_Calmar_D": f"{m_etf['Calmar_D']:.2f}",
        "Avg_TQQQ_Wt": f"{avgw_etf:.0%}",
    })

res_df = pd.DataFrame(rows)
res_df.to_csv(os.path.join(OUT, "combined_macro_vrp_cta_summary.csv"), index=False)
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 20)
print("================================================================================================================")
print("COMBINED BACKTEST: MACRO (SEP) + VOL/VIX (VRP) + INSTITUTIONAL CTA (BAZ TRIM / CLIFF / WASHOUT) (1990-2026)")
print("================================================================================================================")
print(res_df.to_string(index=False))

# Also print the LIVE latest readout (as of latest date in data)
latest_t = T_etf[-1]
st_now = get_state_at(latest_t, is_etf=True)
# Also check very latest daily bar in df_ixic (up to Nov 2026)
latest_day = df_ixic.index[-1]
row_latest_d = df_ixic.iloc[-1]
vix_latest_d = float(vix.iloc[-1])
rv_spx_latest_d = float(rv21_spx.iloc[-1])
print("\n================================================================================================================")
print(f"LIVE CURRENT READOUT (Month-End {latest_t.strftime('%Y-%m-%d')} & Latest Daily {latest_day.strftime('%Y-%m-%d')}):")
print("================================================================================================================")
print(f"  1. Macro Gate (FOMC SEP)         : {'SEP = ON (Tailwind)' if st_now['sep_on'] else 'SEP = OFF (Hawkish Tightening -> 0% TQQQ)'}")
print(f"  2. Realized Vol vs VIX (VRP)     : SPX RV21 = {rv_spx_latest_d:.1f}% | VIX = {vix_latest_d:.1f} | VRP (VIX - RV21) = {vix_latest_d - rv_spx_latest_d:+.1f} pts")
print(f"     -> RV21 Variance Weight (w_rv): {st_now['w_rv']:.0%} | VIX Variance Weight (w_vix): {st_now['w_vix']:.0%} | Dual Vol min: {st_now['w_dual_vol']:.0%}")
print(f"  3. Institutional CTA State       : Trend Z-Score z_comp = {row_latest_d['z_comp']:+.2f} sigma (ST={row_latest_d['z_st']:+.2f}, MT={row_latest_d['z_mt']:+.2f}, LT={row_latest_d['z_lt']:+.2f})")
print(f"     -> Baz Continuous Signal      : {row_latest_d['psi_long']:.0%} | Baz Overextension Trim Factor: {st_now['baz_trim']:.0%}")
print(f"     -> 20d Drawdown in Vol Units  : {row_latest_d['dd_sigma']:+.2f} sigma | Crowded Cliff? {st_now['crowded_cliff']} | Washed Out? {st_now['cta_washed_out']}")
print(f"  4. Credit Stress (HY OAS / BAA)  : {'STRESS' if st_now['credit_stress'] else 'CALM (Normal)'}")
